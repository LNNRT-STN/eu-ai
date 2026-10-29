"""Two things, documented in docs/ML.md (section "Retry with terrain" and "Impact forecast per town"):

1. Risk model with terrain. Same ~1 km cells, label, leave-one-EMS-area-out validation and baselines as
   build_ml.py (it reuses that script's feature cache, src/out/ml_cells.parquet), plus terrain from AWS Terrain
   Tiles (Terrarium PNG, zoom 12, ~25 m pixels at 50°N, no key; tiles cached under cache/terrarium/):
   per building, height above the lowest ground within ~500 m and ~1 km (a HAND-like "height above the valley
   floor"; no flow routing, so the lowest point may sit in a neighbouring valley), slope at the building, and the
   relief and mean slope within ~1.5 km (how steep and deep the valley is). Aggregated per cell.
   python src/build_ml2.py → outputs/data/ml2_eval.json, outputs/data/ml2_cells.csv.

2. impact_forecast(): river flow per gauge → expected share of the July 2021 impact per town (no training).
   Import it: from build_ml2 import impact_forecast, load_town_gauge.
"""
import io
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "out"
DATA_OUT = ROOT / "outputs" / "data"
TILES = ROOT / "cache" / "terrarium"
TERRAIN_CACHE = ROOT / "cache" / "ml2_terrain.parquet"
HIST_CACHE = ROOT / "cache" / "ml2_gauge_annual_max.json"
OBAT = {cc: next((ROOT / "challenge_data").glob(f"obat_{cc.lower()}/*/*.gpkg")) for cc in ("BE", "DE", "NL")}
# GHS-POP 2020 30″ grid (EPSG:4326), as in build_ml.py; origin read back from its ml_score.parquet cell bounds
POP_X0, POP_Y0, POP_RES = -180.00791593069445, 89.09958317995894, 0.008333333300299728
Z = 12
MEUSE = {"EMSR518_AOI01": "Liège/Vesdre/Ourthe (BE)", "EMSR518_AOI02": "Lesse (BE)", "EMSR520_AOI01": "Limburg (NL)",
         "EMSR517_AOI09": "Inde (DE)", "EMSR517_AOI10": "Rur (DE)"}
AHR = {"EMSR517_AOI15": "Ahr, Bad Neuenahr-Ahrweiler (DE)", "EMSR517_AOI03": "Ahr, Hönningen (DE)"}
VESDRE = {"Verviers", "Pepinster", "Chaudfontaine", "Trooz", "Limbourg", "Theux", "Dison", "Olne"}
OLD = ["wet10", "wet100", "wet500", "max100", "max500", "bwet10", "bwet100", "bwet500", "nb_wet100", "nb_wet500",
       "buildings", "res_share", "height", "residents"]
TERRAIN = ["hand1k_p10", "hand1k_med", "hand500_p10", "slope_med", "relief3k", "vslope3k"]
OLD_PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=4, min_child_samples=50, n_estimators=150,
                  verbose=-1, random_state=0)
# EFAS wetness may only raise the score (as before); height above the valley floor may only lower it
MONO_OLD = [1] * 10 + [0] * 4
MONO_NEW = MONO_OLD + [-1, -1, -1, 0, 0, 0]


# ---------------------------------------------------------------- terrain
def _tile(xy):
    x, y = xy
    f = TILES / str(Z) / f"{x}_{y}.png"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        for k in range(4):
            try:
                r = requests.get(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png", timeout=30)
                r.raise_for_status()
                f.write_bytes(r.content)
                break
            except requests.RequestException:
                time.sleep(2 * (k + 1))
        else:
            return xy, None
    from PIL import Image
    a = np.asarray(Image.open(io.BytesIO(f.read_bytes())).convert("RGB"), dtype=np.float32)
    return xy, a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def _gpx(lon, lat):  # global web-mercator pixel coordinates at zoom Z
    n = 2 ** Z * 256
    lat = np.radians(lat)
    return (np.asarray(lon) + 180) / 360 * n, (1 - np.arcsinh(np.tan(lat)) / np.pi) / 2 * n


def terrain_features(points):
    """points: DataFrame lon, lat, key (r, c). Returns per-building terrain columns."""
    from scipy import ndimage
    gx, gy = _gpx(points.lon.values, points.lat.values)
    tx, ty = (gx // 256).astype(int), (gy // 256).astype(int)
    need = {(x + dx, y + dy) for x, y in set(zip(tx, ty)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    with ThreadPoolExecutor(16) as ex:
        tiles = dict(ex.map(_tile, sorted(need)))
    x0, y0 = min(x for x, _ in need), min(y for _, y in need)
    W, H = max(x for x, _ in need) - x0 + 1, max(y for _, y in need) - y0 + 1
    dem = np.full((H * 256, W * 256), np.nan, np.float32)
    for (x, y), a in tiles.items():
        if a is not None:
            dem[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = a
    px_m = 40075016.686 * math.cos(math.radians(points.lat.mean())) / (2 ** Z * 256)
    win = lambda m: 2 * int(round(m / px_m)) + 1
    hi, lo = np.where(np.isnan(dem), np.inf, dem), np.where(np.isnan(dem), -np.inf, dem)
    min1k, min500 = ndimage.minimum_filter(hi, win(1000)), ndimage.minimum_filter(hi, win(500))
    relief = ndimage.maximum_filter(lo, win(1500)) - ndimage.minimum_filter(hi, win(1500))
    sm = ndimage.uniform_filter(np.nan_to_num(dem, nan=float(np.nanmean(dem))), 3)
    dy, dx = np.gradient(sm, px_m)
    slope = np.degrees(np.arctan(np.hypot(dx, dy))).astype(np.float32)
    vslope = ndimage.uniform_filter(slope, win(1500))
    r, c = (gy - y0 * 256).astype(int), (gx - x0 * 256).astype(int)
    e = dem[r, c]
    return pd.DataFrame({"elev": e, "hand1k": e - min1k[r, c], "hand500": e - min500[r, c], "slope": slope[r, c],
                         "relief3k": relief[r, c], "vslope3k": vslope[r, c]}, index=points.index)


def terrain_cells(cells):
    """Per cell of build_ml.py's cache: re-read the same OBAT buildings (same AOI filter), add terrain, aggregate."""
    import geopandas as gpd
    import pyogrio
    if TERRAIN_CACHE.exists():
        return pd.read_parquet(TERRAIN_CACHE)
    aois = gpd.read_file(OUT / "aoi.geojson")
    out = []
    for a in aois.itertuples():
        t0 = time.time()
        keep = cells[cells.aoi_id == a.aoi_id][["r", "c"]]
        ccs = ("BE", "DE", "NL") if a.aoi_id in MEUSE else (a.country,)
        b = pd.concat([pyogrio.read_dataframe(OBAT[cc], columns=["id"], bbox=a.geometry.bounds) for cc in ccs])
        b = gpd.GeoDataFrame(b, crs=4326).drop_duplicates("id")
        b = b[b.within(a.geometry)]
        b = pd.DataFrame({"lon": b.geometry.x.values, "lat": b.geometry.y.values})
        b["r"] = np.floor((POP_Y0 - b.lat) / POP_RES).astype(int)
        b["c"] = np.floor((b.lon - POP_X0) / POP_RES).astype(int)
        b = b.merge(keep, on=["r", "c"])
        b = b.join(terrain_features(b))
        g = b.groupby(["r", "c"]).agg(hand1k_p10=("hand1k", lambda s: s.quantile(.1)), hand1k_med=("hand1k", "median"),
                                      hand500_p10=("hand500", lambda s: s.quantile(.1)), slope_med=("slope", "median"),
                                      relief3k=("relief3k", "median"), vslope3k=("vslope3k", "median"),
                                      elev_med=("elev", "median")).reset_index()
        g["aoi_id"] = a.aoi_id
        out.append(g)
        print(f"  {a.aoi_id}: {len(b):,} buildings, {len(g):,}/{len(keep):,} cells, {time.time() - t0:.0f} s", flush=True)
    t = pd.concat(out, ignore_index=True)
    t.to_parquet(TERRAIN_CACHE, index=False)
    return t


# ---------------------------------------------------------------- evaluation
def top_capture(y, s, q=.1):  # share of water-hit cells among the top q of cells by score (as build_ml.py)
    k = max(1, int(round(len(s) * q)))
    return float(y.values[np.argsort(-s.values, kind="stable")[:k]].sum() / max(1, y.sum()))


def evaluate():
    import lightgbm as lgb
    from sklearn.metrics import average_precision_score, roc_auc_score
    df = pd.read_parquet(OUT / "ml_cells.parquet")
    df["y"] = (df.obs_buildings > 0).astype(int)
    ef = [f for f in OLD if f.startswith(("wet", "max", "bwet", "nb_"))]
    df[ef] = df[ef].fillna(0)
    t = terrain_cells(df)
    df = df.merge(t, on=["r", "c", "aoi_id"], how="left")
    print(f"{len(df):,} cells, {df.y.sum()} hit, terrain missing for {df.hand1k_p10.isna().sum()}")
    for name, feats, mono in (("old", OLD, MONO_OLD), ("new", OLD + TERRAIN, MONO_NEW),
                              ("terrain_only", ["residents", "buildings"] + TERRAIN, [0, 0, -1, -1, -1, 0, 0, 0])):
        df[name] = np.nan
        for aoi in df.aoi_id.unique():
            te = df.aoi_id == aoi
            m = lgb.LGBMClassifier(**OLD_PARAMS, monotone_constraints=mono).fit(df.loc[~te, feats], df.loc[~te, "y"])
            df.loc[te, name] = m.predict_proba(df.loc[te, feats])[:, 1]
    df["hand_rule"] = -df.hand1k_p10.fillna(df.hand1k_p10.max())  # no training: lowest buildings first
    scores_ = {"LightGBM + terrain": "new", "LightGBM old (no terrain)": "old", "EFAS 100-yr share of cell": "wet100",
               "Terrain-only LightGBM": "terrain_only", "Height above valley floor (rule)": "hand_rule"}

    def sc(d):
        o = {"cells": int(len(d)), "hit_cells": int(d.y.sum())}
        if d.y.nunique() == 2:
            for k, col in scores_.items():
                o[k] = {"roc_auc": round(roc_auc_score(d.y, d[col]), 3),
                        "avg_precision": round(average_precision_score(d.y, d[col]), 3),
                        "top10pct_capture": round(top_capture(d.y, d[col]), 3)}
        return o

    def boot(d, a, b, n=500):
        rng = np.random.default_rng(0)
        diff = []
        for _ in range(n):
            s = d.sample(len(d), replace=True, random_state=rng)
            if s.y.nunique() == 2:
                diff.append(roc_auc_score(s.y, s[a]) - roc_auc_score(s.y, s[b]))
        return [round(float(np.percentile(diff, q)), 3) for q in (2.5, 50, 97.5)]

    meuse, ahr = df[df.aoi_id.isin(MEUSE)], df[df.aoi_id.isin(AHR)]
    ev = {"all_areas_pooled": sc(df), "meuse_pooled": sc(meuse), "ahr_pooled": sc(ahr),
          "per_area": {a: sc(df[df.aoi_id == a]) for a in sorted(df.aoi_id.unique())},
          "auc_gain_new_vs_efas100_95ci": {"all": boot(df, "new", "wet100"), "meuse": boot(meuse, "new", "wet100"),
                                           "ahr": boot(ahr, "new", "wet100")},
          "auc_gain_new_vs_old_95ci": {"all": boot(df, "new", "old"), "meuse": boot(meuse, "new", "old"),
                                       "ahr": boot(ahr, "new", "old")}}
    # Vesdre: the satellite saw no water there, so no AUC is possible. Check where each score puts the Vesdre cells
    # that the EFAS 500-year zone (the app's modelled Vesdre flood) touches, as a percentile among Meuse cells.
    ms = pd.read_parquet(OUT / "meuse" / "ml_score.parquet", columns=["r", "c", "commune"]).drop_duplicates(["r", "c"])
    meuse = meuse.merge(ms, on=["r", "c"], how="left")
    for col in ("new", "old", "wet100", "hand_rule"):
        meuse[col + "_pct"] = meuse[col].rank(pct=True)
    v = meuse[meuse.commune.isin(VESDRE) & (meuse.bwet500 > 0)]
    vl = meuse[meuse.commune.isin(VESDRE)]
    ev["vesdre_modelled"] = {
        "cells_in_vesdre_communes": int(len(vl)), "satellite_hit": int(vl.y.sum()),
        "cells_with_homes_in_efas500": int(len(v)),
        "median_percentile_among_meuse_cells": {k: round(float(v[c + "_pct"].median()), 3) for k, c in
                                                (("LightGBM + terrain", "new"), ("LightGBM old", "old"),
                                                 ("EFAS 100-yr share", "wet100"), ("Height above valley floor", "hand_rule"))},
        "terrain_rule_auc_vs_modelled_label": round(roc_auc_score(vl.bwet500 > 0, vl.hand_rule), 3)}
    ev["features_added"] = TERRAIN
    ev["params"] = OLD_PARAMS | {"monotone": dict(zip(OLD + TERRAIN, MONO_NEW))}
    ev["terrain_source"] = f"AWS Terrain Tiles, Terrarium PNG, zoom {Z}"
    (DATA_OUT / "ml2_eval.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False))

    # cells file: centre, area, municipality (app towns only), out-of-area score
    import geopandas as gpd
    df["lon"] = POP_X0 + (df.c + .5) * POP_RES
    df["lat"] = POP_Y0 - (df.r + .5) * POP_RES
    mun = gpd.read_file(DATA_OUT / "municipality_outlines.geojson")[["municipality", "geometry"]]
    pts = gpd.GeoDataFrame(df[["lon", "lat"]], geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)
    j = gpd.sjoin(pts, mun.to_crs(4326), predicate="within", how="left")
    df["municipality"] = j[~j.index.duplicated()].municipality
    aoi = gpd.read_file(OUT / "aoi.geojson")[["aoi_id", "locality"]]
    df = df.merge(aoi, on="aoi_id")
    df["score"] = df.new.round(4)
    df["score_pct"] = df.new.rank(pct=True).round(3)
    df[["lon", "lat", "aoi_id", "locality", "municipality", "score", "score_pct", "hand1k_p10", "slope_med", "relief3k",
        "wet100", "residents", "y"]].rename(columns={"locality": "area", "y": "hit_2021_satellite"}).round(
        {"lon": 5, "lat": 5, "hand1k_p10": 1, "slope_med": 1, "relief3k": 0, "residents": 0}).to_csv(
        DATA_OUT / "ml2_cells.csv", index=False)
    return ev


# ---------------------------------------------------------------- impact forecast
WATCH, WARN, EVACUATE = 0.0, 0.25, 0.6  # thresholds on the expected share of the 2021 impact (see impact_forecast)


def load_town_gauge():
    """outputs/data/town_gauge.csv if it exists (needs area, municipality, gauge; optional q2, q2021), else the
    nearest forecast.GAUGES station within 15 km of the town centre (towns with none get gauge = NaN)."""
    f = DATA_OUT / "town_gauge.csv"
    if f.exists():
        return pd.read_csv(f)
    from forecast import GAUGES
    t = _towns()[["area", "municipality", "lon", "lat"]].copy()
    g = pd.DataFrame([(k, la, lo) for k, (la, lo) in GAUGES.items()], columns=["gauge", "glat", "glon"])
    d = (np.radians(t.lat.values[:, None] - g.glat.values) ** 2 + (np.radians(t.lon.values[:, None] - g.glon.values)
         * np.cos(np.radians(t.lat.values[:, None]))) ** 2) ** .5 * 6371
    i = d.argmin(1)
    t["gauge"] = np.where(d.min(1) <= 15, g.gauge.values[i], None)
    t["gauge_km"] = d.min(1).round(1)
    return t.drop(columns=["lon", "lat"])


@lru_cache(1)
def _towns():
    """2021 impact per town (worst flood): people, single-storey homes, flooded care sites (hospital / care home,
    at least 5 % of the site under water)."""
    t = pd.read_csv(DATA_OUT / "app_towns.csv", encoding="utf-8-sig")
    t = t[t.variant == "worst"][["area", "municipality", "people", "lon", "lat", "source"]]
    b = pd.read_parquet(DATA_OUT / "buildings_3d.parquet", columns=["area", "municipality", "use", "storeys"])
    ss = b[(b.use == 1) & (b.storeys == 1)].groupby(["area", "municipality"]).size().rename("single_storey")
    cs = pd.read_csv(DATA_OUT / "critical_sites.csv", encoding="utf-8-sig")
    cs = cs[cs.in_worst_flood & (cs.share_of_site_flooded >= .05) & cs.type.isin(["hospital", "care home"])]
    cs = cs.groupby(["area", "municipality"]).size().rename("care_sites")
    t = t.join(ss, on=["area", "municipality"]).join(cs, on=["area", "municipality"])
    return t.fillna({"single_storey": 0, "care_sites": 0}).reset_index(drop=True)


@lru_cache(1)
def _curves():
    """Per gauge: calibration knots (x, share), x = position of the flow between the 2-year flow (0) and the July
    2021 peak (1) on a log scale. Default knots (0,0),(1,1) = straight line in log flow. Where outputs/data/ml2_curves.json
    holds an EFAS calibration (see calibrate_curves), those knots are used instead."""
    f = DATA_OUT / "ml2_curves.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _share(q, q2, q21, knots):
    x = np.clip(np.log(np.maximum(q, 1e-9) / q2) / np.log(q21 / q2), 0, None)
    xs, ys = (np.array(knots["x"]), np.array(knots["share"])) if knots else (np.array([0., 1.]), np.array([0., 1.]))
    s = np.interp(np.minimum(x, 1), xs, ys)
    return np.where(q <= q2, 0.0, np.where(x >= 1, 1.0, s))


def impact_forecast(flows_by_gauge, town_gauge):
    """River flow per gauge → expected share of the July 2021 impact per town, and what it means.

    flows_by_gauge: {gauge name: flow in m³/s}, or {gauge: list of ensemble member flows}. Gauge names as in
        forecast.GAUGES / src/out/meuse/gauge_refs.json (GloFAS daily discharge, same model as the references).
    town_gauge: DataFrame with area, municipality, gauge (load_town_gauge()); optional q2, q2021 override the
        reference flows (for gauges not in gauge_refs.json).

    Curve (deterministic, no training): share = 0 at or below the 2-year flow q2; 1 at or above the July 2021
    peak q2021; in between, x = log(q/q2) / log(q2021/q2) is mapped through the gauge's calibration knots
    (outputs/data/ml2_curves.json, from the EFAS 10/100/500-year zones; see calibrate_curves) or, without
    calibration, share = x. Expected impact = share × the town's 2021 impact (people in the worst observed flood,
    or the EFAS-modelled Vesdre flood; single-storey homes; hospitals and care homes ≥ 5 % under water).
    With ensemble members, the share is the mean over members (an expectation) and `probability` is the share
    of members that reach `warn` or worse; with one flow it is 0 or 1.

    Status from the share: "none" (0, flow at or below the 2-year flow), "watch" (> 0 and < 0.25),
    "warn" (0.25 to < 0.6), "evacuate" (≥ 0.6); "no gauge" when the town has no gauge or no flow.
    """
    refs = json.loads((OUT / "meuse" / "gauge_refs.json").read_text())
    curves = _curves()
    t = _towns().merge(town_gauge[[c for c in ("area", "municipality", "gauge", "q2", "q2021") if c in town_gauge]],
                       on=["area", "municipality"], how="left")
    share, prob = np.full(len(t), np.nan), np.full(len(t), np.nan)
    for g, idx in t.groupby("gauge").groups.items():
        if g not in flows_by_gauge:
            continue
        q = np.atleast_1d(np.asarray(flows_by_gauge[g], dtype=float))
        row = t.loc[idx[0]]
        q2 = row.q2 if "q2" in t and pd.notna(row.q2) else refs.get(g, [np.nan])[0]
        q21 = row.q2021 if "q2021" in t and pd.notna(row.q2021) else refs.get(g, [np.nan, np.nan])[1]
        if not (q2 > 0 and q21 > q2):
            continue
        s = _share(q, q2, q21, curves.get(g))
        share[idx], prob[idx] = s.mean(), (s >= WARN).mean()
    out = t[["area", "municipality", "gauge", "source"]].copy()
    out["share_of_2021"] = share.round(3)
    out["people_expected"] = (share * t.people).round()
    out["single_storey_expected"] = (share * t.single_storey).round()
    out["care_sites_expected"] = (share * t.care_sites).round(1)
    out["probability"] = prob.round(2)
    out["status"] = np.select([np.isnan(share), share >= EVACUATE, share >= WARN, share > WATCH],
                              ["no gauge", "evacuate", "warn", "watch"], "none")
    return out


def annual_maxima():
    """GloFAS daily discharge 1991–2020 per gauge from Open-Meteo (free), annual maxima, cached in cache/."""
    from forecast import FLOOD, GAUGES
    out = json.loads(HIST_CACHE.read_text()) if HIST_CACHE.exists() else {}  # keep gauges already fetched
    for g in [g for g in GAUGES if g not in out]:
        lat, lon = GAUGES[g]
        for _ in range(6):
            r = requests.get(FLOOD, params={"latitude": lat, "longitude": lon, "daily": "river_discharge",
                                            "start_date": "1991-01-01", "end_date": "2020-12-31"}, timeout=60)
            if r.status_code != 429:
                break
            time.sleep(60)  # free tier: wait for the per-minute weight to clear
        r.raise_for_status()
        h = pd.Series(r.json()["daily"]["river_discharge"], index=pd.to_datetime(r.json()["daily"]["time"]))
        out[g] = h.groupby(h.index.year).max().dropna().tolist()
        HIST_CACHE.write_text(json.dumps(out))
        print(g, len(out[g]), flush=True)
        time.sleep(30)
    return out


def calibrate_curves():
    """Knots per gauge from EFAS: residents in the EFAS 10-, 100- and 500-year zones of the cells near the gauge's
    towns (build_ml.py cell cache: residents × share of buildings on wet EFAS pixels), relative to the zone that
    matches the 2021 return period; the flows of those return periods from a Gumbel fit (method of moments) to
    the gauge's GloFAS annual maxima 1991–2020, placed on the same log scale as the curve."""
    import geopandas as gpd
    am = annual_maxima()
    refs = json.loads((OUT / "meuse" / "gauge_refs.json").read_text())
    tg = load_town_gauge().dropna(subset=["gauge"])
    cells = pd.read_parquet(OUT / "ml_cells.parquet")
    cells[["bwet10", "bwet100", "bwet500"]] = cells[["bwet10", "bwet100", "bwet500"]].fillna(0)
    cells = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(POP_X0 + (cells.c + .5) * POP_RES,
                                                                POP_Y0 - (cells.r + .5) * POP_RES), crs=4326)
    mun = gpd.read_file(DATA_OUT / "municipality_outlines.geojson")[["municipality", "geometry"]].to_crs(4326)
    cm = gpd.sjoin(cells, mun, predicate="within").merge(tg[["municipality", "gauge"]].drop_duplicates(), on="municipality")
    curves = {}
    for g, d in cm.groupby("gauge"):
        if g not in am or g not in refs:
            continue
        a = np.array(am[g])
        beta = a.std(ddof=1) * math.sqrt(6) / math.pi
        mu = a.mean() - 0.5772 * beta
        qT = {T: mu - beta * math.log(-math.log(1 - 1 / T)) for T in (10, 100, 500)}
        q2, q21 = refs[g]
        T21 = 1 / (1 - math.exp(-math.exp(-(q21 - mu) / beta)))
        E = {T: float((d.residents * d[f"bwet{T}"]).sum()) for T in (10, 100, 500)}
        # exposure at the 2021 return period: interpolate EFAS zones on log T, capped at the 500-year zone
        lt = np.log([10, 100, 500])
        E21 = float(np.interp(math.log(min(max(T21, 10), 500)), lt, [E[10], E[100], E[500]]))
        knots = [(0.0, 0.0)]
        for T in (10, 100, 500):
            x = math.log(qT[T] / q2) / math.log(q21 / q2)
            if 0 < x < 1 and E21 > 0:
                knots.append((round(x, 3), round(min(E[T] / E21, 1), 3)))
        knots.append((1.0, 1.0))
        xs, ys = zip(*knots)
        ys = np.maximum.accumulate(ys)  # never less impact at a higher flow
        curves[g] = {"x": list(xs), "share": [round(float(v), 3) for v in ys], "T_2021_gumbel": round(T21),
                     "q_T": {T: round(v) for T, v in qT.items()}, "efas_residents": {T: round(v) for T, v in E.items()},
                     "years": len(a)}
    (DATA_OUT / "ml2_curves.json").write_text(json.dumps(curves, indent=1, ensure_ascii=False))
    _curves.cache_clear()
    return curves


if __name__ == "__main__":
    import sys
    if "--curves" in sys.argv:
        print(json.dumps(calibrate_curves(), indent=1, ensure_ascii=False))
    else:
        ev = evaluate()
        print(json.dumps({k: ev[k] for k in ("all_areas_pooled", "meuse_pooled", "ahr_pooled", "vesdre_modelled",
                                             "auc_gain_new_vs_efas100_95ci", "auc_gain_new_vs_old_95ci")}, indent=1))
