"""Street address for every candidate shelter in the 10 km shelter plan, so a resident is told the exact place to go.
Run from eu-ai/:  python -I notebooks/shelter_addresses.py   (after notebooks/addresses.py has cached the OSM reads)
In:  outputs/data/bus_plan.csv (shelter, s_lon, s_lat); cache/osm/*.addr.{points,multipolygons}.gpkg
Out: outputs/data/shelter_addresses.csv [shelter, s_lon, s_lat, street, housenumber, postcode, city, m]
Method: nearest OSM object with addr:housenumber within 100 m of the shelter point (EPSG:3035). No match -> blank;
nothing is guessed or interpolated. Licence: (c) OpenStreetMap contributors, ODbL 1.0.
"""
import time, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree

T0 = time.time()
C = Path("cache/osm"); OUT = Path("outputs/data/shelter_addresses.csv"); MAX_M = 100.0
TAGS = {"street": "addr:street", "place": "addr:place", "housenumber": "addr:housenumber",
        "postcode": "addr:postcode", "city": "addr:city"}

s = (pd.read_csv("outputs/data/bus_plan.csv").drop_duplicates(["shelter", "s_lon", "s_lat"])
     [["shelter", "s_lon", "s_lat"]].reset_index(drop=True))
box = (s.s_lon.min() - .002, s.s_lat.min() - .002, s.s_lon.max() + .002, s.s_lat.max() + .002)

def tag(g, k):
    return g["other_tags"].astype("string").str.extract(rf'"{k}"=>"((?:[^"\\]|\\.)*)"', expand=False)

frames = []
for f in sorted(C.glob("*.addr.*.gpkg")):
    g = gpd.read_file(f, bbox=box)
    if f.name.endswith("multipolygons.gpkg"):
        g["geometry"] = g.geometry.representative_point()
    for col, k in TAGS.items(): g[col] = tag(g, k)
    frames.append(g[[*TAGS, "geometry"]])
    print(f"{f.name:48s} {len(g):7d} address objects  ({time.time()-T0:.0f}s)", flush=True)

a = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)
a = a[a.housenumber.notna() & a.housenumber.str.strip().ne("")].reset_index(drop=True)
a["street"] = a.street.fillna(a.place)
pa = a.to_crs(3035).geometry
ps = gpd.points_from_xy(s.s_lon, s.s_lat, crs=4326).to_crs(3035)
d, i = cKDTree(np.c_[pa.x, pa.y]).query(np.c_[ps.x, ps.y], k=1, distance_upper_bound=MAX_M)
hit = np.isfinite(d)
for col in ("street", "housenumber", "postcode", "city"):
    s[col] = None
    s.loc[hit, col] = a[col].values[i[hit]]
s["m"] = np.where(hit, d.round(0), np.nan)
s.to_csv(OUT, index=False)
print(f"{hit.sum()} of {len(s)} shelters matched to an address within {MAX_M:.0f} m -> {OUT}  ({time.time()-T0:.0f}s)")
