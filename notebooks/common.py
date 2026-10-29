"""Shared loaders for the challenge data (local copy in challenge_data/). Metric CRS: EPSG:3035."""
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.windows import from_bounds
from shapely.validation import make_valid

D = Path("challenge_data")
M = "EPSG:3035"
POP = {y: D / f"ghs_pop/GHS_POP_E{y}_GLOBE_R2023A_4326_30ss_V1_0/GHS_POP_E{y}_GLOBE_R2023A_4326_30ss_V1_0.tif" for y in (2020, 2025)}
OBAT = {"be": D / "obat_be/GHS_OBAT_GPKG_BEL_E2020_R2024A_V1_0/GHS_OBAT_GPKG_BEL_E2020_R2024A_V1_0.gpkg",
        "nl": D / "obat_nl/GHS_OBAT_GPKG_NLD_E2020_R2024A_V1_0/GHS_OBAT_GPKG_NLD_E2020_R2024A_V1_0.gpkg",
        "de": D / "obat_de/GHS_OBAT_GPKG_DEU_E2020_R2024A_V1_0/GHS_OBAT_GPKG_DEU_E2020_R2024A_V1_0.gpkg"}
# OBAT codes, per GHS-OBAT_R2024_online_v2.pdf p.19-20
USE = {0: "outside built-up", 1: "residential", 2: "non-residential"}
EPOCH = {0: "outside built-up", 1: "<1980", 2: "1980-1990", 3: "1990-2000", 4: "2000-2010", 5: "2010-2020"}


def flood_geom(cc, key, kinds=("PRODUCT",)):
    """EMS observedEventA, riverine flood only, repaired and dissolved. Returns (geometry in EPSG:3035, n polygons)."""
    parts = []
    for prod in (D / f"ems_{cc}").iterdir():
        if prod.is_dir() and key in prod.name and any(k in prod.name for k in kinds):
            for f in prod.glob("*observedEventA*.shp"):
                g = gpd.read_file(f); g = g[g.obj_desc == "Riverine flood"]
                g["geometry"] = g.geometry.apply(make_valid); parts.append(g.to_crs(M))
    g = pd.concat(parts, ignore_index=True)
    return g.unary_union, len(g)


def read_pop(bbox, year=2020):
    with rasterio.open(POP[year]) as r:
        win = from_bounds(*bbox, transform=r.transform).round_offsets().round_lengths()
        return r.read(1, window=win), r.window_transform(win)


def read_buildings(cc, bbox):
    b = gpd.read_file(OBAT[cc], bbox=bbox, engine="pyogrio")
    b["lon"], b["lat"] = b.geometry.x, b.geometry.y
    b = b.to_crs(M); b["x"], b["y"] = b.geometry.x, b.geometry.y
    return b


def attach_people(b, arr, tr):
    """Dasymetric: each population cell's residents spread over its residential buildings, weighted by footprint area."""
    col = np.floor((b["lon"].values - tr.c) / tr.a).astype(int)
    row = np.floor((b["lat"].values - tr.f) / tr.e).astype(int)
    ok = (row >= 0) & (row < arr.shape[0]) & (col >= 0) & (col < arr.shape[1])
    b = b.assign(row=row, col=col)[ok].copy()
    b["cellpop"] = arr[b["row"].values, b["col"].values]
    w = b["area"].where(b["use"] == 1, 0.0)
    b["people"] = (b["cellpop"] * w / w.groupby([b["row"], b["col"]]).transform("sum").replace(0, np.nan)).fillna(0.0)
    return b
