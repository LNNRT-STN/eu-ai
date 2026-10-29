"""Extract shelter / critical-facility candidates from local OpenStreetMap files (Geofabrik .osm.pbf in cache/osm/)
into one small file, cache/osm/facilities.gpkg. Replaces the public Overpass server, which was at capacity.
Run from eu-ai/:  .venv/Scripts/python.exe -I notebooks/osm_extract.py
Source: OpenStreetMap contributors (ODbL), extracts from download.geofabrik.de, downloaded 2026-10-29.
"""
import re, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd, geopandas as gpd, pyogrio

SRC = sorted(Path("cache/osm").glob("*.osm.pbf")); OUT = Path("cache/osm/facilities.gpkg")
if len(sys.argv) > 1:                                    # test mode: only the named extracts, separate output
    SRC = [f for f in SRC if any(a in f.name for a in sys.argv[1:])]; OUT = Path("cache/osm/_test_facilities.gpkg")
WANT = {"amenity": ["school", "college", "university", "kindergarten", "community_centre", "townhall", "events_venue",
                    "hospital", "nursing_home", "social_facility"],
        "leisure": ["sports_hall", "sports_centre"],
        "building": ["school", "sports_hall", "civic", "public", "hospital", "college", "university", "kindergarten"],
        "healthcare": ["hospital"], "social_facility": ["nursing_home", "assisted_living"]}

def like(key, val): return f"other_tags LIKE '%\"{key}\"=>\"{val}\"%'"
def where(columns):
    parts = []
    for k, vals in WANT.items():
        for v in vals:
            parts.append(f"{k} = '{v}'" if k in columns else like(k, v))
    return " OR ".join(parts)
def tag(g, k):
    """Tag value from its own column when GDAL has one, else from the other_tags text (empty -> None)."""
    from_other = g["other_tags"].astype("string").str.extract(rf'"{k}"=>"([^"]*)"', expand=False) if "other_tags" in g else None
    if k in g.columns: return g[k].where(g[k].notna(), from_other) if from_other is not None else g[k]
    return from_other

frames = []
for f in SRC:
    for layer in ("points", "multipolygons"):
        raw_cache = f.with_suffix(f".{layer}.gpkg")           # raw read saved: a later bug never forces a re-parse
        if raw_cache.exists(): g = gpd.read_file(raw_cache)
        else:
            cols = pyogrio.read_info(f, layer=layer)["fields"].tolist()
            g = pyogrio.read_dataframe(f, layer=layer, where=where(cols)); g.to_file(raw_cache, driver="GPKG")
        for k in WANT: g[k] = tag(g, k)
        if "osm_way_id" in g.columns: g["osm_id"] = g["osm_id"].fillna("w" + g["osm_way_id"].astype(str))   # closed ways
        g["src"] = f.name
        frames.append(g[["osm_id", "name", *WANT, "src", "geometry"]])
        print(f"{f.name:32s} {layer:14s} {len(g):6d} features", flush=True)
allf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)
n0 = len(allf)
allf = allf.drop_duplicates(subset=["osm_id", "src"]).copy()             # same object twice in one file
allf["k"] = allf.geometry.representative_point().apply(lambda p: (round(p.x, 5), round(p.y, 5)))
allf = allf.drop_duplicates(subset=["k", "name"]).drop(columns="k")      # same object in two overlapping extracts
allf.to_file(OUT, driver="GPKG")
print(f"saved {OUT}: {len(allf)} features ({n0 - len(allf)} duplicates removed)")
