"""Test whether a LightGBM model adds anything to the EFAS 100-year zone and the hand-made priority score.
Run after build.py, build_meuse.py and build_priority.py: python src/build_ml.py → out/ml_cells.parquet (cache),
out/meuse/ml_score.parquet, out/meuse/ml_communes.parquet, out/meuse/ml_eval.json. Method and verdict: docs/ML.md.

Unit: GHS-POP ~1 km cell with at least one OBAT building inside a mapped EMS area (all 19 AOIs, BE/NL/DE).
Label: the satellite saw at least one of the cell's buildings in the July 2021 water (build.py buildings) — a floor.
Features, challenge data only: EFAS RP10/100/500 depth (share of the cell's ~90 m pixels that are wet, max depth,
share of buildings on a wet pixel, wettest neighbouring cell), OBAT (buildings, residential share, height),
GHS-POP 2020 residents. No terrain, rain or river data: none is in the challenge set.
Validation: leave one EMS area out (never a random split), against the EFAS zones used alone as a score."""
import json
from pathlib import Path

import geopandas as gpd
import lightgbm as lgb
import numpy as np
import pandas as pd
import pyogrio
import rasterio
from rasterio.windows import from_bounds
from sklearn.metrics import average_precision_score, roc_auc_score

DATA = Path(__file__).resolve().parents[1] / "data" / "working_data"
OUT = Path(__file__).resolve().parent / "out"
DST = OUT / "meuse"
CACHE = OUT / "ml_cells.parquet"
OBAT = {cc: next(DATA.glob(f"obat_{cc.lower()}/*/*.gpkg")) for cc in ("BE", "DE", "NL")}
POP = next(DATA.glob("ghs_pop/*E2020*/*.tif"))
EFAS = {rp: DATA / f"cems-efas/Europe_RP{rp}_filled_depth.tif" for rp in (10, 100, 500)}
MEUSE = {"EMSR518_AOI01": "Liège/Vesdre/Ourthe (BE)", "EMSR518_AOI02": "Lesse (BE)", "EMSR520_AOI01": "Limburg (NL)",
         "EMSR517_AOI09": "Inde (DE)", "EMSR517_AOI10": "Rur (DE)"}
UNDER_DETECTED = {"Pepinster", "Verviers", "Chaudfontaine", "Trooz", "Liège"}  # as build_regions.py
FEATURES = ["wet10", "wet100", "wet500", "max100", "max500", "bwet10", "bwet100", "bwet500", "nb_wet100", "nb_wet500",
            "buildings", "res_share", "height", "residents"]
PLAIN = {"wet10": "river zone floods even in a 10-year flood", "wet100": "large part inside the EFAS 100-year zone",
         "wet500": "large part inside the EFAS 500-year zone", "max100": "deep water modelled in a 100-year flood",
         "max500": "deep water modelled in a 500-year flood", "bwet10": "homes on 10-year flood ground",
         "bwet100": "homes inside the 100-year zone", "bwet500": "homes inside the 500-year zone",
         "nb_wet100": "next to a 100-year flood zone", "nb_wet500": "next to a 500-year flood zone",
         "buildings": "many buildings", "res_share": "mostly homes", "height": "building height",
         "residents": "many residents"}
# Small trees; score may only rise with EFAS wetness (monotone), so the model cannot learn "wetter = safer" from the
# satellite's blind spots. Best of three variants tried (docs/ML.md); a 15-leaf, 300-tree model did worse.
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=4, min_child_samples=50, n_estimators=150,
              monotone_constraints=[1] * 10 + [0] * 4, verbose=-1, random_state=0)


def cell_features():
    """One row per (AOI, ~1 km cell) with buildings; cells shared by overlapping AOIs go to the first AOI."""
    aois = gpd.read_file(OUT / "aoi.geojson")
    flooded = pd.read_parquet(OUT / "buildings.parquet", columns=["id", "aoi_id"])
    with rasterio.open(POP) as src:
        pt = src.transform
    rows = []
    for a in aois.itertuples():
        bbox = a.geometry.bounds
        ccs = ("BE", "DE", "NL") if a.aoi_id in MEUSE else (a.country,)
        b = pd.concat([pyogrio.read_dataframe(OBAT[cc], columns=["id", "use", "height"], bbox=bbox) for cc in ccs])
        b = gpd.GeoDataFrame(b, crs=4326).drop_duplicates("id")
        b = b[b.within(a.geometry)]
        lon, lat = b.geometry.x.values, b.geometry.y.values
        col, row = ~pt * (lon, lat)
        b = pd.DataFrame({"id": b.id.values, "res": (b.use == 1).values, "height": b.height.values,
                          "r": np.floor(row).astype(int), "c": np.floor(col).astype(int)})
        b["obs"] = b.id.isin(set(flooded[flooded.aoi_id == a.aoi_id].id))
        for rp, f in EFAS.items():  # depth under each building point, and per-cell block stats of ~90 m pixels
            with rasterio.open(f) as src:
                win = from_bounds(*bbox, transform=src.transform).round_offsets().round_lengths()
                d = src.read(1, window=win, boundless=True, fill_value=src.nodata)
                d = np.where((d == src.nodata) | (d < 0), 0, d)
                wt = src.window_transform(win)
            rr, cc_ = rasterio.transform.rowcol(wt, lon, lat)
            b[f"d{rp}"] = d[np.clip(rr, 0, d.shape[0] - 1), np.clip(cc_, 0, d.shape[1] - 1)] > 0
            yy, xx = np.mgrid[0:d.shape[0], 0:d.shape[1]]
            px, py = wt * (xx + .5, yy + .5)
            pc, pr = ~pt * (px, py)
            blk = pd.DataFrame({"r": np.floor(pr).ravel().astype(int), "c": np.floor(pc).ravel().astype(int),
                                "d": d.ravel(), "w": d.ravel() > 0}).groupby(["r", "c"])
            blk = pd.DataFrame({f"wet{rp}": blk.w.mean(), f"max{rp}": blk.d.max()})
            rows_rp = blk if rp == 10 else rows_rp.join(blk)
        g = b.groupby(["r", "c"]).agg(buildings=("id", "size"), res_share=("res", "mean"), height=("height", "mean"),
                                      bwet10=("d10", "mean"), bwet100=("d100", "mean"), bwet500=("d500", "mean"),
                                      obs_buildings=("obs", "sum")).reset_index()
        g = g.merge(rows_rp.reset_index(), on=["r", "c"], how="left")
        for rp in (100, 500):  # wettest of the 8 neighbouring cells
            m = rows_rp[f"wet{rp}"]
            shifted = [m.set_axis(pd.MultiIndex.from_arrays([m.index.get_level_values(0) + dr,
                                                             m.index.get_level_values(1) + dc])) for dr in (-1, 0, 1)
                       for dc in (-1, 0, 1) if dr or dc]
            nbmax = pd.concat(shifted, axis=1).max(axis=1)
            g[f"nb_wet{rp}"] = nbmax.reindex(pd.MultiIndex.from_frame(g[["r", "c"]])).fillna(0).values
        with rasterio.open(POP) as src:
            g["residents"] = [v[0] for v in src.sample([pt * (c + .5, r + .5) for r, c in zip(g.r, g.c)])]
        g["aoi_id"], g["country"] = a.aoi_id, a.country
        rows.append(g)
        print(f"  {a.aoi_id}: {len(b):,} buildings, {len(g):,} cells, {int((g.obs_buildings > 0).sum())} with water")
    df = pd.concat(rows, ignore_index=True)
    df = df.sort_values("obs_buildings", ascending=False).drop_duplicates(["r", "c"]).sort_values(["aoi_id", "r", "c"])
    df["residents"] = df.residents.clip(lower=0)
    return df.reset_index(drop=True)


df = pd.read_parquet(CACHE) if CACHE.exists() else cell_features()
df.to_parquet(CACHE, index=False)
df["y"] = (df.obs_buildings > 0).astype(int)
EF = [f for f in FEATURES if f.startswith(("wet", "max", "bwet", "nb_"))]
df[EF] = df[EF].fillna(0)  # no EFAS pixel = dry
print(f"{len(df):,} cells, {df.y.sum()} with homes in the 2021 water")
print(df.groupby("aoi_id").agg(cells=("y", "size"), pos=("y", "sum")).to_string())

# Leave one EMS area out: every cell is scored by a model that never saw its area
df["ml"] = np.nan
contrib = np.zeros((len(df), len(FEATURES) + 1))
for aoi in df.aoi_id.unique():
    te = df.aoi_id == aoi
    m = lgb.LGBMClassifier(**PARAMS).fit(df.loc[~te, FEATURES], df.loc[~te, "y"])
    df.loc[te, "ml"] = m.predict_proba(df.loc[te, FEATURES])[:, 1]
    contrib[te.values] = m.predict(df.loc[te, FEATURES], pred_contrib=True)

BASE = {"EFAS 100-yr share of cell": "wet100", "EFAS 100-yr share of buildings": "bwet100",
        "EFAS 500-yr share of cell": "wet500", "EFAS 10-yr share of cell": "wet10"}


def top_capture(y, s, q=.1):  # share of water-hit cells among the top q of cells by score
    k = max(1, int(round(len(s) * q)))
    return float(y.values[np.argsort(-s.values, kind="stable")[:k]].sum() / max(1, y.sum()))


def scores(d):
    out = {"cells": int(len(d)), "hit_cells": int(d.y.sum())}
    if d.y.nunique() < 2:
        return out
    for name, col in {"LightGBM": "ml", **BASE}.items():
        out[name] = {"roc_auc": round(roc_auc_score(d.y, d[col]), 3), "avg_precision": round(average_precision_score(d.y, d[col]), 3),
                     "top10pct_capture": round(top_capture(d.y, d[col]), 3)}
    return out


ev = {"all_areas_pooled": scores(df), "meuse_pooled": scores(df[df.aoi_id.isin(MEUSE)]),
      "per_meuse_area": {f"{k} {v}": scores(df[df.aoi_id == k]) for k, v in MEUSE.items()}}
mm = df[df.aoi_id.isin(MEUSE)]
rng = np.random.default_rng(0)  # bootstrap over cells: is the model's AUC gain over the EFAS 100-yr share real?
diff = [roc_auc_score(b.y, b.ml) - roc_auc_score(b.y, b.wet100) for b in (mm.sample(len(mm), replace=True, random_state=rng) for _ in range(500))]
ev["meuse_auc_gain_vs_efas100_95ci"] = [round(float(np.percentile(diff, q)), 3) for q in (2.5, 50, 97.5)]

# Meuse communes: cell centre → LAU commune, compare with the hand-made score and the EFAS zone
pr = gpd.read_file(DST / "priority.geojson")
with rasterio.open(POP) as src:
    pt = src.transform
mz = df[df.aoi_id.isin(MEUSE)].copy()
mz["lon0"], mz["lat1"] = pt * (mz.c.values, mz.r.values)
mz["lon1"], mz["lat0"] = pt * (mz.c.values + 1, mz.r.values + 1)
ctr = gpd.GeoDataFrame(mz, geometry=gpd.points_from_xy((mz.lon0 + mz.lon1) / 2, (mz.lat0 + mz.lat1) / 2), crs=4326)
mz = gpd.sjoin(ctr, pr[["lau_id", "commune", "geometry"]], predicate="within", how="left").drop(columns=["index_right", "geometry"])
mz = pd.DataFrame(mz).drop_duplicates(["r", "c"])
C = pd.DataFrame(contrib[df.aoi_id.isin(MEUSE).values][:, :-1], columns=FEATURES, index=df.index[df.aoi_id.isin(MEUSE)])
mz["driver1"], mz["driver2"] = [[PLAIN[FEATURES[i]] for i in np.argsort(-C.loc[mz.index].values, axis=1)[:, k]] for k in (0, 1)]
mz["ml_pct"] = mz.ml.rank(pct=True).round(3)
mz[["r", "c", "aoi_id", "lau_id", "commune", "lon0", "lat0", "lon1", "lat1", "residents", "buildings", "wet100", "y",
    "ml", "ml_pct", "driver1", "driver2"]].rename(columns={"y": "hit_2021_satellite"}).to_parquet(DST / "ml_score.parquet", index=False)

# commune score: residents in a cell weighted by the cell's model probability (expected residents in hit cells)
mz["exp_res"] = mz.ml * mz.residents
cm = mz.dropna(subset=["lau_id"]).groupby("lau_id").agg(ml_exp_residents=("exp_res", "sum"), ml_max=("ml", "max")).reset_index()
Cc = C.loc[mz.dropna(subset=["lau_id"]).index].mul(mz.dropna(subset=["lau_id"]).residents, axis=0)
Cc["lau_id"] = mz.dropna(subset=["lau_id"]).lau_id
drv = Cc.groupby("lau_id")[FEATURES].sum()
top = np.argsort(-drv.values, axis=1)
cm = cm.merge(pd.DataFrame({"lau_id": drv.index, "ml_driver1": [PLAIN[FEATURES[i]] for i in top[:, 0]],
                            "ml_driver2": [PLAIN[FEATURES[i]] for i in top[:, 1]]}), on="lau_id")
cm = pr[["lau_id", "commune", "country", "people", "score", "level"]].merge(cm, on="lau_id", how="left").fillna({"ml_exp_residents": 0, "ml_max": 0})
cm["ml_score"] = (cm.ml_exp_residents.rank(pct=True) * 10).round().astype(int)  # relative: decile among the 70 communes
cm.to_parquet(DST / "ml_communes.parquet", index=False)

rk = lambda s: s.rank(ascending=False, method="min").astype(int)
cm["rank_hand"], cm["rank_ml"], cm["rank_efas_people"] = rk(cm.score), rk(cm.ml_exp_residents), rk(cm.people)
ud = cm[cm.commune.isin(UNDER_DETECTED)]
cell_ud = mz[mz.commune.isin(UNDER_DETECTED)]
ev["communes"] = {
    "n": int(len(cm)),
    "spearman_ml_vs_hand_score": round(cm.ml_exp_residents.corr(cm.score, method="spearman"), 3),
    "spearman_ml_vs_efas_people": round(cm.ml_exp_residents.corr(cm.people, method="spearman"), 3),
    "spearman_hand_vs_efas_people": round(cm.score.corr(cm.people, method="spearman"), 3),
    "under_detected_ranks": ud[["commune", "rank_hand", "rank_ml", "rank_efas_people"]].to_dict("records"),
    "under_detected_cells": {"cells": int(len(cell_ud)), "satellite_hit": int(cell_ud.y.sum()),
                             "in_efas_100yr_zone": int((cell_ud.wet100 > 0).sum()),
                             "median_ml_percentile": round(float(cell_ud.ml_pct.median()), 3)}}
ev["params"] = {k: v for k, v in PARAMS.items() if k != "monotone_constraints"} | {"monotone_on": FEATURES[:10]}
(DST / "ml_eval.json").write_text(json.dumps(ev, indent=1))
print(json.dumps({k: ev[k] for k in ("all_areas_pooled", "meuse_pooled", "communes")}, indent=1))
print(cm.sort_values("ml_exp_residents", ascending=False).head(12)[["commune", "score", "ml_score", "people", "ml_exp_residents", "ml_driver1", "ml_driver2"]].to_string())
