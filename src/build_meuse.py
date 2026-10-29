"""Meuse–Vesdre baseline for the coordinator dashboard (dashboard.py). Run build.py first.

For every OBAT building in the Meuse-basin mapped areas (BE Liège/Vesdre, BE Lesse, NL Limburg,
DE Rur/Inde) it flags two lenses:
  obs   = inside the observed July 2021 flood extent (same buildings as build.py)
  rp100 = inside the EFAS modelled 100-year flood zone (cell under the building point)
Residents are GHS-POP 2020 cells spread equally over the residential buildings in each cell
(dasymetric; floor-area weights let a few huge, likely misclassified footprints absorb whole cells), then summed per commune (GISCO LAU 2021) and per ~1 km cell.
Writes src/out/meuse/.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import rasterio.features
import shapely
import requests
from rasterio.windows import from_bounds

DATA = Path(__file__).resolve().parents[1] / "data" / "working_data"
OUT = Path(__file__).resolve().parent / "out"
DST = OUT / "meuse"
DST.mkdir(exist_ok=True)

# EMS areas that drain to the Meuse: Meuse/Vesdre/Ourthe (Liège), Lesse (Rochefort),
# Meuse in Limburg (Venlo), Inde and Rur (Eschweiler, Wassenberg)
MEUSE_AOIS = ["EMSR518_AOI01", "EMSR518_AOI02", "EMSR520_AOI01", "EMSR517_AOI09", "EMSR517_AOI10"]
OBAT = {cc: next(DATA.glob(f"obat_{cc.lower()}/*/*.gpkg")) for cc in ("BE", "DE", "NL")}
POP = next(DATA.glob("ghs_pop/*E2020*/*.tif"))
EFAS100 = DATA / "cems-efas/Europe_RP100_filled_depth.tif"
LAU_URL = "https://gisco-services.ec.europa.eu/distribution/v2/lau/parquet/LAU_RG_01M_2021_4326.parquet"
LAU_RAW = OUT / "raw" / "LAU_RG_01M_2021_4326.parquet"
# GISCO lists some Walloon communes under their Dutch exonym; use the local (French) name
LOCAL_NAME = {"Luik": "Liège", "Wezet": "Visé", "Limburg": "Limbourg", "Bitsingen": "Bassenge",
              "Saint-Nicolas (Luik)": "Saint-Nicolas", "Hoei": "Huy", "Namen": "Namur", "Borgworm": "Waremme"}
NOT_MEUSE = ("BE_71",)  # Hasselt arrondissement drains to the Demer (Scheldt basin) though inside the Liège AOI

aoi = gpd.read_file(OUT / "aoi.geojson")
aoi = aoi[aoi.aoi_id.isin(MEUSE_AOIS)]
bbox = tuple(aoi.total_bounds)
flooded = pd.read_parquet(OUT / "buildings.parquet", columns=["id", "aoi_id"])
flooded_ids = set(flooded[flooded.aoi_id.isin(MEUSE_AOIS)].id)

# 1. All OBAT buildings in the region (spatial-index read), clipped to the mapped areas
frames = []
for cc, path in OBAT.items():
    df = pyogrio.read_dataframe(path, columns=["id", "use"], bbox=bbox)
    frames.append(df.assign(country=cc))
    print(f"  {cc}: {len(df):,} OBAT points in region bbox")
b = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)
b = gpd.sjoin(b, aoi[["aoi_id", "geometry"]], predicate="within").drop(columns="index_right").drop_duplicates("id")
b["lon"], b["lat"] = b.geometry.x.values, b.geometry.y.values

# 2. Communes (LAU 2021)
if not LAU_RAW.exists():
    r = requests.get(LAU_URL, timeout=300)
    r.raise_for_status()
    LAU_RAW.write_bytes(r.content)
lau = gpd.read_parquet(LAU_RAW).rename_geometry("geometry").set_crs(4326, allow_override=True)
lau = lau[lau.CNTR_CODE.isin(["BE", "DE", "NL"])].cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
lau = lau.rename(columns={"GISCO_ID": "lau_id", "LAU_NAME": "commune"})
lau["commune"] = lau.commune.replace(LOCAL_NAME)
b = gpd.sjoin(b.drop(columns="country"), lau[["lau_id", "commune", "geometry"]], predicate="within").drop(columns="index_right")
b = b.drop_duplicates("id")
b["country"] = b.lau_id.str[:2]  # commune decides the country (OBAT files overlap at borders)
b = b[~b.lau_id.str.startswith(NOT_MEUSE)]

# 3. Lenses
b["obs"] = b.id.isin(flooded_ids)
with rasterio.open(EFAS100) as src:
    win = from_bounds(*bbox, transform=src.transform).round_offsets().round_lengths()
    d = src.read(1, window=win, boundless=True, fill_value=src.nodata)
    r_, c_ = rasterio.transform.rowcol(src.window_transform(win), b.lon.values, b.lat.values)
    r_, c_ = np.clip(r_, 0, d.shape[0] - 1), np.clip(c_, 0, d.shape[1] - 1)
    wet = (d != src.nodata) & (d > 0)
    b["rp100"] = wet[r_, c_]
    zone = [shapely.geometry.shape(g) for g, _ in rasterio.features.shapes(
        wet.astype("uint8"), mask=wet, transform=src.window_transform(win))]
zone = shapely.intersection(shapely.union_all(zone), aoi.union_all())  # map layer: zone inside the mapped areas

# 4. Residents: each GHS-POP cell spread equally over its residential buildings
with rasterio.open(POP) as src:
    win = from_bounds(*bbox, transform=src.transform).round_offsets().round_lengths()
    pop = src.read(1, window=win, boundless=True, fill_value=0)
    wt = src.window_transform(win)
    r_, c_ = rasterio.transform.rowcol(wt, b.lon.values, b.lat.values)
r_, c_ = np.clip(r_, 0, pop.shape[0] - 1), np.clip(c_, 0, pop.shape[1] - 1)
b["cell"] = r_ * pop.shape[1] + c_
res = b.use == 1
w = res.astype(float).values
cell_w = pd.Series(w).groupby(b.cell.values).transform("sum").values
b["residents"] = np.where(w > 0, pop.ravel()[b.cell.values] * w / np.where(cell_w > 0, cell_w, 1), 0.0)
b["residential"] = res

# 5. Aggregates per lens
out = {"bbox": list(bbox), "lenses": {}}
cells_all, communes_all = [], []
for lens in ("obs", "rp100"):
    s = b[b[lens]]
    g = s.groupby(["lau_id", "commune", "country"]).agg(
        buildings=("id", "size"), residential=("residential", "sum"), residents=("residents", "sum"),
        lon=("lon", "mean"), lat=("lat", "mean")).reset_index()
    communes_all.append(g.assign(lens=lens))
    c = s.groupby("cell").agg(residents=("residents", "sum"), buildings=("id", "size")).reset_index()
    rows, cols = np.divmod(c.cell.values, pop.shape[1])
    c["lon0"], c["lat1"] = wt * (cols, rows)          # top-left corner of each ~1 km cell
    c["lon1"], c["lat0"] = wt * (cols + 1, rows + 1)
    cells_all.append(c.assign(lens=lens))
    out["lenses"][lens] = {
        "buildings": int(len(s)), "residential": int(s.residential.sum()), "residents": round(float(s.residents.sum())),
        "communes": int(len(g)),
        "by_country": {cc: {"buildings": int((s.country == cc).sum()), "residents": round(float(s[s.country == cc].residents.sum()))}
                       for cc in ("BE", "NL", "DE")}}
    print(lens, json.dumps(out["lenses"][lens]))

pd.concat(communes_all).to_parquet(DST / "communes.parquet", index=False)
pd.concat(cells_all).to_parquet(DST / "cells.parquet", index=False)
flood = gpd.read_file(OUT / "flood.geojson")
flood[flood.aoi_id.isin(MEUSE_AOIS)].to_file(DST / "flood.geojson")
aoi.to_file(DST / "aoi.geojson")
gpd.GeoDataFrame(geometry=[shapely.simplify(zone, 0.0002)], crs=4326).to_file(DST / "rp100.geojson")
(DST / "summary.json").write_text(json.dumps(out, indent=1))
