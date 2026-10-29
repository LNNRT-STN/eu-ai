"""Build data: per EMS area of interest (AOI), buildings and residents inside the
observed 2021 flood extent, and whether EFAS hazard maps expected water there.

Reads only what intersects the flood polygons (spatial index on OBAT, raster windows).
Writes small outputs to src/out/.
"""
import json, re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
from exactextract import exact_extract
from PIL import Image
from rasterio.windows import from_bounds

DATA = Path(__file__).resolve().parents[1] / "data" / "working_data"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

COUNTRY = {"EMSR517": "DE", "EMSR518": "BE", "EMSR520": "NL"}
OBAT = {cc: next(DATA.glob(f"obat_{cc.lower()}/*/*.gpkg")) for cc in ("BE", "DE", "NL")}
EFAS = {rp: DATA / f"cems-efas/Europe_RP{rp}_filled_depth.tif" for rp in (10, 100, 500)}
POP = next(DATA.glob("ghs_pop/*E2020*/*.tif"))  # E2020 matches the 2021 event; E2025 is a projection
NAME_RE = re.compile(r"(EMSR\d+)_(AOI\d+)_(DEL|GRA)_(PRODUCT|MONIT\d+)_(\w+?)_r\d+_v\d+")
FLOOD_NOTATION = {"Flooded area", "Flood trace"}  # excludes '6-Mass Movement'
EQUAL_AREA = 3035  # ETRS89-LAEA Europe, for km²


def ems_layer(layer):
    """All shapefiles of one EMS layer, tagged with activation, AOI and product."""
    frames = []
    for shp in DATA.glob(f"ems_*/*/*_{layer}_*.shp"):
        m = NAME_RE.search(shp.name)
        df = pyogrio.read_dataframe(shp)
        frames.append(df.assign(emsr=m[1], aoi=m[2], ptype=m[3], version=m[4]))
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs).to_crs(4326)


# 1. AOIs and observed flood extent (union of first product and monitoring updates)
aois = ems_layer("areaOfInterestA")
floods = ems_layer("observedEventA")
floods = floods[floods.notation.isin(FLOOD_NOTATION)]
floods["geometry"] = shapely.make_valid(floods.geometry.values)

keys = ["emsr", "aoi"]
aoi_gdf = aois.dissolve(by=keys, aggfunc={"locality": "first", "ptype": "first"}).reset_index()
flood_gdf = floods.dissolve(by=keys).reset_index()[keys + ["geometry"]]
aoi_gdf = aoi_gdf.merge(flood_gdf.rename(columns={"geometry": "flood"}), on=keys)
aoi_gdf["country"] = aoi_gdf.emsr.map(COUNTRY)
aoi_gdf["aoi_id"] = aoi_gdf.emsr + "_" + aoi_gdf.aoi
print(f"{len(aoi_gdf)} AOIs with flood polygons")

# 2. Buildings inside the flood extent, with EFAS modelled depth at each point
efas_src = {rp: rasterio.open(p) for rp, p in EFAS.items()}


def efas_depth(src, x, y, bounds):
    win = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
    arr = src.read(1, window=win, boundless=True, fill_value=src.nodata)
    rows, cols = rasterio.transform.rowcol(src.window_transform(win), x, y)
    rows, cols = np.clip(rows, 0, arr.shape[0] - 1), np.clip(cols, 0, arr.shape[1] - 1)
    arr = np.where(arr == src.nodata, 0, arr).astype("float32")  # nodata = not modelled / dry
    pad = np.pad(arr, 1)
    nb = np.max([pad[1 + dr:1 + dr + arr.shape[0], 1 + dc:1 + dc + arr.shape[1]]
                 for dr in (-1, 0, 1) for dc in (-1, 0, 1)], axis=0)  # wettest of the 3x3 cells (~90 m)
    return arr[rows, cols], nb[rows, cols]


buildings = []
for r in aoi_gdf.itertuples():
    pts = pyogrio.read_dataframe(OBAT[r.country], columns=["id", "use", "epoch", "height"], mask=r.flood)
    if pts.empty:
        continue
    x, y = pts.geometry.x.values, pts.geometry.y.values
    shapely.prepare(r.flood)
    keep = shapely.contains_xy(r.flood, x, y)  # exact point-in-polygon check
    pts, x, y = pts[keep], x[keep], y[keep]
    df = pd.DataFrame({"id": pts.id.values, "aoi_id": r.aoi_id, "lon": x, "lat": y,
                       "use": pts.use.values, "epoch": pts.epoch.values, "height": pts.height.values})
    for rp, src in efas_src.items():
        df[f"rp{rp}"], df[f"rp{rp}_nb"] = efas_depth(src, x, y, r.flood.bounds)
    buildings.append(df)
    print(f"  {r.aoi_id} {r.locality}: {len(df):,} buildings in flood extent")

b = pd.concat(buildings, ignore_index=True)
for sfx in ("", "_nb"):  # "_nb": a building counts as in a zone if any neighbouring EFAS cell is wet
    b[f"hazard{sfx}"] = np.select([b[f"rp10{sfx}"] > 0, b[f"rp100{sfx}"] > 0, b[f"rp500{sfx}"] > 0],
                                  ["RP10", "RP100", "RP500"], "none")
b.to_parquet(OUT / "buildings.parquet", index=False)

# 3. Residents in the flood extent, weighting partly flooded cells by flooded share
flood_only = gpd.GeoDataFrame(aoi_gdf[["aoi_id"]], geometry=aoi_gdf.flood, crs=4326)
pop = exact_extract(str(POP), flood_only, "sum", include_cols=["aoi_id"], output="pandas")
aoi_gdf = aoi_gdf.merge(pop.rename(columns={"sum": "residents"}), on="aoi_id")
all_flood = gpd.GeoDataFrame(geometry=[shapely.union_all(aoi_gdf.flood.values)], crs=4326)
residents_total = float(exact_extract(str(POP), all_flood, "sum", output="pandas")["sum"][0])

# 4. Summaries (overall totals dedupe buildings that sit in overlapping AOIs)
def stats(df):
    return {
        "buildings": int(len(df)),
        "residential": int((df.use == 1).sum()),
        **{f"by_hazard{sfx}": {h: {"residential": int(((df[f"hazard{sfx}"] == h) & (df.use == 1)).sum()),
                                   "other": int(((df[f"hazard{sfx}"] == h) & (df.use != 1)).sum())}
                               for h in ["RP10", "RP100", "RP500", "none"]} for sfx in ("", "_nb")},
    }

aoi_gdf["flood_km2"] = gpd.GeoSeries(aoi_gdf.flood, crs=4326).to_crs(EQUAL_AREA).area / 1e6
summary = {"total": {**stats(b.drop_duplicates("id")), "residents": round(residents_total),
                     "flood_km2": round(float(all_flood.to_crs(EQUAL_AREA).area.iloc[0] / 1e6), 1)},
           "aois": {}}
for r in aoi_gdf.itertuples():
    summary["aois"][r.aoi_id] = {"locality": r.locality, "country": r.country, "product": r.ptype,
                                 "residents": round(float(r.residents)), "flood_km2": round(r.flood_km2, 1),
                                 "bounds": list(r.geometry.bounds), **stats(b[b.aoi_id == r.aoi_id])}

# 5. Geometry for the map (simplified, ~5 m tolerance) and EFAS overlays as PNG
simp = lambda g: shapely.simplify(g, 0.00005, preserve_topology=True)
gpd.GeoDataFrame(aoi_gdf[["aoi_id", "locality", "country"]], geometry=aoi_gdf.geometry.map(simp), crs=4326).to_file(OUT / "aoi.geojson")
gpd.GeoDataFrame(aoi_gdf[["aoi_id"]], geometry=aoi_gdf.flood.map(simp), crs=4326).to_file(OUT / "flood.geojson")

xmin, ymin, xmax, ymax = aoi_gdf.total_bounds
summary["efas_bounds"] = [[ymin, xmin], [ymax, xmax]]
for rp, colour in [(100, (42, 120, 214)), (500, (141, 184, 236))]:
    src = efas_src[rp]
    win = from_bounds(xmin, ymin, xmax, ymax, transform=src.transform).round_offsets().round_lengths()
    d = src.read(1, window=win, boundless=True, fill_value=src.nodata)
    wet = (d != src.nodata) & (d > 0)
    alpha = np.where(wet, np.clip(90 + 40 * d, 90, 220), 0).astype("uint8")  # deeper = more opaque
    rgba = np.dstack([np.full(d.shape, c, "uint8") for c in colour] + [alpha])
    Image.fromarray(rgba, "RGBA").save(OUT / f"efas_rp{rp}.png", optimize=True)

(OUT / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary["total"], indent=1))
