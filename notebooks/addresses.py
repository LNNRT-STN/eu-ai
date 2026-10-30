"""Street address for every OBAT building in the 2021 water, for a resident check-in ("evacuated, I'm safe") by
street + house number and a fire-crew door-knock list of homes with no check-in.
Run from eu-ai/:  python -I notebooks/addresses.py
In:  outputs/data/buildings_3d.parquet (row order = building identity, bid = f"{area}-{row index}")
     cache/osm/*-latest.osm.pbf (Geofabrik extracts, downloaded 2026-10-29)
Out: outputs/data/addresses.parquet; raw OSM address read cached in cache/osm/<extract>.addr.gpkg
Method: every OSM object with addr:housenumber (nodes; building ways/relations by representative point) inside the
areas' bounding boxes (+150 m); each OBAT point gets the nearest one within 30 m (EPSG:3035). One address may serve
several OBAT points. No match -> no address; nothing is guessed or interpolated.
OUT_DIR=outputs/rp: the return-period buildings (flags in_rp10 / in_rp100 / in_rp500 kept); OSM reads cached as
<extract>.addr.rp.<layer>.gpkg, since the zones reach beyond the 2021 boxes.
Licence: address data (c) OpenStreetMap contributors, ODbL 1.0 (attribution and share-alike apply to the output).
"""
import os, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd, pyogrio
from scipy.spatial import cKDTree

T0 = time.time()
D = Path(os.environ.get("OUT_DIR", "outputs/data")); TAG = "" if D.name == "data" else f".{D.name}"
C = Path("cache/osm"); OUT = D / "addresses.parquet"; MAX_M = 30.0; PAD = 0.002   # ~150 m
TAGS = {"street": "addr:street", "place": "addr:place", "housenumber": "addr:housenumber",
        "postcode": "addr:postcode", "city": "addr:city"}

b = pd.read_parquet(D / "buildings_3d.parquet").reset_index(drop=True)
b.insert(0, "bid", b["area"] + "-" + b.index.astype(str))
boxes = b.groupby("area").agg(x0=("lon", "min"), x1=("lon", "max"), y0=("lat", "min"), y1=("lat", "max"))
boxes[["x0", "y0"]] -= PAD; boxes[["x1", "y1"]] += PAD
full = (boxes.x0.min(), boxes.y0.min(), boxes.x1.max(), boxes.y1.max())

def tag(g, k):
    return g["other_tags"].astype("string").str.extract(rf'"{k}"=>"((?:[^"\\]|\\.)*)"', expand=False)

frames = []
for f in sorted(C.glob("*-latest.osm.pbf")):
    for layer in ("points", "multipolygons"):
        cache = C / f.name.replace(".osm.pbf", f".addr{TAG}.{layer}.gpkg")
        if cache.exists(): g = gpd.read_file(cache)
        else:
            g = pyogrio.read_dataframe(f, layer=layer, bbox=full, where="other_tags LIKE '%\"addr:housenumber\"%'")
            g.to_file(cache, driver="GPKG")
        if layer == "multipolygons":
            g["oid"] = np.where(g["osm_way_id"].notna(), "w" + g["osm_way_id"].astype(str), "r" + g["osm_id"].astype(str))
            g["geometry"] = g.geometry.representative_point()
        else: g["oid"] = "n" + g["osm_id"].astype(str)
        for col, k in TAGS.items(): g[col] = tag(g, k)
        frames.append(g[["oid", *TAGS, "geometry"]])
        print(f"{f.name:32s} {layer:14s} {len(g):7d} address objects  ({time.time()-T0:.0f}s)", flush=True)

a = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326).drop_duplicates("oid")   # overlapping extracts
a = a[a["housenumber"].notna() & a["housenumber"].str.strip().ne("")]
a["street"] = a["street"].fillna(a["place"])                     # villages addressed by place name, not street
inbox = np.zeros(len(a), bool)
for _, r in boxes.iterrows():
    inbox |= ((a.geometry.x >= r.x0) & (a.geometry.x <= r.x1) & (a.geometry.y >= r.y0) & (a.geometry.y <= r.y1)).values
a = a[inbox].reset_index(drop=True)
print(f"{len(a)} OSM address points in the areas' boxes")

pa = a.to_crs(3035).geometry; tree = cKDTree(np.c_[pa.x, pa.y])
pb = gpd.points_from_xy(b.lon, b.lat, crs=4326).to_crs(3035)
d, i = tree.query(np.c_[pb.x, pb.y], k=1, distance_upper_bound=MAX_M)
hit = np.isfinite(d)
for col in ("street", "housenumber", "postcode", "city"):
    vals = np.full(len(b), None, object); vals[hit] = a[col].values[i[hit]]; b[col] = vals
b["match_m"] = np.where(hit, np.round(d, 1), np.nan)
b["label"] = np.where(hit, (b["street"].fillna("") + " " + b["housenumber"].fillna("")).str.strip(), "")
b["country"] = b["municipality"].str.extract(r"\((\w\w)\)\s*$", expand=False)

cols = ["bid", "area", "municipality", "lon", "lat", "use", "storeys", "height_m",
        "street", "housenumber", "postcode", "city", "match_m", "label", *[c for c in b if c.startswith("in_rp")]]
b[cols].to_parquet(OUT, index=False)

b["matched"] = hit; b["res"] = b["use"] == 1
def rates(by):
    g = b.groupby(by)
    return pd.DataFrame({"buildings": g.size(), "match_all": g["matched"].mean().round(3),
                         "match_res": b[b.res].groupby(by)["matched"].mean().round(3),
                         "over_15m": b[b.matched].groupby(by)["match_m"].apply(lambda s: (s > 15).mean()).round(3)})
print(rates("area").to_string()); print(rates("country").to_string())
print(f"total match {hit.mean():.3f}, residential {b.loc[b.res, 'matched'].mean():.3f}, "
      f"match_m > 15 m: {(b.loc[hit, 'match_m'] > 15).mean():.3f} of matched; "
      f"addresses used by >1 building: {(pd.Series(i[hit]).value_counts() > 1).sum()}")
print(b.loc[hit, ["bid", "municipality", "label", "postcode", "city", "match_m"]].sample(6, random_state=1).to_string())
print(f"saved {OUT} ({len(b)} rows) in {time.time()-T0:.0f}s")
