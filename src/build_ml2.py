"""Documented in docs/ML.md (section "Retry with terrain"):

Risk model with terrain. Same ~1 km cells, label, leave-one-EMS-area-out validation and baselines as
   build_ml.py (it reuses that script's feature cache, src/out/ml_cells.parquet), plus terrain from AWS Terrain
   Tiles (Terrarium PNG, zoom 12, ~25 m pixels at 50°N, no key; tiles cached under cache/terrarium/):
   per building, height above the lowest ground within ~500 m and ~1 km (a HAND-like "height above the valley
   floor"; no flow routing, so the lowest point may sit in a neighbouring valley), slope at the building, and the
   relief and mean slope within ~1.5 km (how steep and deep the valley is). Aggregated per cell.
   python src/build_ml2.py → outputs/data/ml2_eval.json, outputs/data/ml2_cells.csv.

The impact forecast per town (river flow → status) moved to impact.py: it is not a trained model.
"""
import io
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "out"
DATA_OUT = ROOT / "outputs" / "data"
TILES = ROOT / "cache" / "terrarium"
TERRAIN_CACHE = ROOT / "cache" / "ml2_terrain.parquet"
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


if __name__ == "__main__":
    ev = evaluate()
    print(json.dumps({k: ev[k] for k in ("all_areas_pooled", "meuse_pooled", "ahr_pooled", "vesdre_modelled",
                                         "auc_gain_new_vs_efas100_95ci", "auc_gain_new_vs_old_95ci")}, indent=1))
