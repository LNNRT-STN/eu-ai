"""Impact forecast per town from return periods: river flow → how rare it is at the town's river point → who lives
in the EFAS flood zone of that return period → status. No training, and no use of the July 2021 flood: the same
rule serves the live forecast.

    python src/impact.py             → outputs/data/town_efas.csv (residents per town in the EFAS 10/100/500-year
                                       zones)

Exposure: residents in the EFAS zones ignore dikes and flood walls (the Meuse numbers in Dutch Limburg and Liège are
an upper bound) and skip small streams (Kall, Bad Münstereifel and Kelmis have no zone, so 0 there means "no data",
not "safe"). Between the zones, exposure is interpolated on log return period, 0 at the 2-year flood.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

import forecast

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "out"
DATA_OUT = ROOT / "outputs" / "data"
EXPOSURE = DATA_OUT / "town_efas.csv"
STATUS = ["none", "watch", "warn", "evacuate"]  # = level 0-3: above the 2-, 5-, 20-year flow
ZONES = (10, 100, 500)
# GHS-POP 2020 30″ grid (EPSG:4326), as in build_ml.py
POP_X0, POP_Y0, POP_RES = -180.00791593069445, 89.09958317995894, 0.008333333300299728


def load_town_gauge():
    """outputs/data/town_gauge.csv if it exists (area, municipality, gauge), else the nearest forecast.GAUGES
    point within 15 km of the town centre (towns with none get gauge = NaN)."""
    f = DATA_OUT / "town_gauge.csv"
    if f.exists():
        return pd.read_csv(f)
    t = _towns()[["area", "municipality", "lon", "lat"]].copy()
    g = pd.DataFrame([(k, la, lo) for k, (la, lo) in forecast.GAUGES.items()], columns=["gauge", "glat", "glon"])
    d = (np.radians(t.lat.values[:, None] - g.glat.values) ** 2 + (np.radians(t.lon.values[:, None] - g.glon.values)
         * np.cos(np.radians(t.lat.values[:, None]))) ** 2) ** .5 * 6371
    t["gauge"] = np.where(d.min(1) <= 15, g.gauge.values[d.argmin(1)], None)
    t["gauge_km"] = d.min(1).round(1)
    return t.drop(columns=["lon", "lat"])


@lru_cache(1)
def _towns():
    """Towns of the worst-case map with their 2021 people (context) and EFAS zone residents."""
    t = pd.read_csv(DATA_OUT / "app_towns.csv", encoding="utf-8-sig")
    t = t[t.variant == "worst"][["area", "municipality", "people", "lon", "lat"]]
    return t.merge(exposure(), on="municipality", how="left").fillna({f"efas{T}": 0 for T in ZONES}) \
        .reset_index(drop=True)


@lru_cache(1)
def exposure():
    """municipality, efas10, efas100, efas500: residents on a wet pixel of each EFAS zone (build_ml.py cell cache:
    GHS-POP residents × share of the cell's buildings on wet pixels), summed per municipality."""
    if EXPOSURE.exists():
        return pd.read_csv(EXPOSURE)
    import geopandas as gpd
    c = pd.read_parquet(OUT / "ml_cells.parquet")
    c = gpd.GeoDataFrame(c, geometry=gpd.points_from_xy(POP_X0 + (c.c + .5) * POP_RES,
                                                         POP_Y0 - (c.r + .5) * POP_RES), crs=4326)
    mun = gpd.read_file(DATA_OUT / "municipality_outlines.geojson")[["municipality", "geometry"]].to_crs(4326)
    j = gpd.sjoin(c, mun, predicate="within")
    e = pd.DataFrame({f"efas{T}": (j.residents * j[f"bwet{T}"].fillna(0)).groupby(j.municipality).sum().round()
                      for T in ZONES}).astype(int).rename_axis("municipality").reset_index()
    e.to_csv(EXPOSURE, index=False)
    return e


def people_at(T, row):
    """Residents in the flood zone of a T-year flood: 0 up to the 2-year flood, then the EFAS zones interpolated on
    log T, held at the 500-year zone beyond it."""
    xs = np.log([2, *ZONES])
    ys = [0, *(row[f"efas{z}"] for z in ZONES)]
    return np.interp(np.log(np.clip(T, 2, 500)), xs, ys)


def impact_forecast(flows_by_gauge, town_gauge, upto=None):
    """River flow per gauge → status and expected people per town.

    flows_by_gauge: {gauge: flow in m³/s}, or {gauge: list of ensemble run peaks}. Gauge names as in
        forecast.GAUGES (GloFAS daily discharge, the same model as the thresholds).
    town_gauge: DataFrame with area, municipality, gauge (load_town_gauge()).
    upto: last year of the record the thresholds are fitted on (forecast.thresholds); None = the whole record.

    Status: "none" / "watch" / "warn" / "evacuate" when the flow reaches the 2- / 5- / 20-year flood at the
    town's river point; with ensemble runs, when at least forecast.PROB of the runs reach it. "no gauge" when the
    town has no river point or no flow. probability: share of runs at the 5-year flow or above (0 or 1 for one
    flow). return_period: of the flow (the median run). people_expected: residents in the EFAS zone of that
    return period, averaged over the runs.
    """
    thr = forecast.thresholds(upto)
    t = _towns().merge(town_gauge[["area", "municipality", "gauge"]], on=["area", "municipality"], how="left")
    out = t[["area", "municipality", "gauge"]].copy()
    lvl, prob, rp, pe = (np.full(len(t), np.nan) for _ in range(4))
    for g, idx in t.groupby("gauge").groups.items():
        if g not in flows_by_gauge or g not in thr:
            continue
        q = np.atleast_1d(np.asarray(flows_by_gauge[g], dtype=float))
        if np.isnan(q).all():
            continue
        Tq = forecast.period_of(thr[g]["fit"], q)
        lv, p = forecast.ensemble_level(q, thr[g])
        lvl[idx], prob[idx], rp[idx] = lv, p[5], float(np.median(Tq))
        pe[idx] = [people_at(Tq, t.loc[i]).mean() for i in idx]
    out["level"] = lvl
    out["status"] = [STATUS[int(v)] if v == v else "no gauge" for v in lvl]
    out["probability"] = prob.round(2)
    out["return_period"] = rp.round(1)
    out["people_expected"] = pe.round()  # NaN where the town has no flow
    out["people_2021"] = t.people
    out["no_efas_zone"] = t.efas500 == 0
    return out


if __name__ == "__main__":
    print(exposure().head(25).to_string(index=False))
