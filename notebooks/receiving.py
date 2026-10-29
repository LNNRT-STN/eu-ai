"""Where do evacuated patients and residents go? For each hospital / care home in the 2021 water, the nearest DRY sites
of the same kind (hospital -> hospital, care home -> care home), from OpenStreetMap. Dry = outside the 2021 satellite
flood (all passes) and not wet in the EFAS 100-year model at the site. Locations only: free beds are not in any dataset.
Run from eu-ai/ after pipeline.py:  .venv/Scripts/python.exe -I notebooks/receiving.py
"""
import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from common import D, M

OUT = Path("outputs/data"); K, MAX_KM = 3, 30
crit = pd.read_csv(OUT / "critical_sites.csv")
need = crit[(crit.share_of_site_flooded >= .05) & crit.in_worst_flood.astype(bool) & crit.type.isin(["hospital", "care home"])]

f = gpd.read_file("cache/osm/facilities.gpkg")
def kind(r):
    if r.amenity == "hospital" or r.healthcare == "hospital" or r.building == "hospital": return "hospital"
    if r.amenity == "nursing_home" or r.social_facility in ("nursing_home", "assisted_living"): return "care home"
    return None
f["kind"] = f.apply(kind, axis=1)        # not "type": on a GeoDataFrame .type is the geometry type
f = f[f["kind"].notna()].copy()
pt = f.to_crs(M).geometry.representative_point()
f["x"], f["y"] = pt.x.values, pt.y.values
ll = pt.to_crs(4326); f["lon"], f["lat"] = ll.x.values, ll.y.values
# one row per facility: same type and name within 300 m is the same site (campus buildings)
f = f.sort_values("name").assign(gx=lambda d: (d.x // 300).astype(int), gy=lambda d: (d.y // 300).astype(int))
f = f.drop_duplicates(["kind", "name", "gx", "gy"])

flood = shapely.unary_union([gpd.read_file(p).to_crs(M).union_all() for p in OUT.glob("flood_*_worst.geojson")])
f["in_2021"] = shapely.contains_xy(flood, f.x.values, f.y.values)
with rasterio.open(D / "cems-efas/Europe_RP100_filled_depth.tif") as r:
    depth = np.array([v[0] for v in r.sample(zip(f.lon, f.lat))])
f["in_efas100"] = depth > 0.1
dry = f[~f.in_2021 & ~f.in_efas100]
print(f"OSM hospitals and care homes: {len(f)} | dry: {len(dry)} "
      f"(wet in 2021: {int(f.in_2021.sum())}, wet in the 100-year model only: {int((~f.in_2021 & f.in_efas100).sum())})")

rows = []
for s in need.itertuples():
    p = gpd.GeoSeries(gpd.points_from_xy([s.lon], [s.lat]), crs=4326).to_crs(M).iloc[0]
    c = dry[dry["kind"] == s.type].assign(km=lambda d: np.hypot(d.x - p.x, d.y - p.y) / 1000)
    c = c[(c.km <= MAX_KM) & (c.km > .3)].nsmallest(K, "km")
    if c.empty: print("  no dry receiving site within", MAX_KM, "km for", s.name)
    for r in c.itertuples():
        rows.append(dict(from_name=s.name, from_town=s.municipality, from_area=s.area, type=s.type,
                         to_name=r.name if isinstance(r.name, str) else f"Unnamed {r.kind}",
                         km=round(r.km, 1), lon=round(r.lon, 5), lat=round(r.lat, 5)))
out = pd.DataFrame(rows)
out.to_csv(OUT / "receiving_sites.csv", index=False, encoding="utf-8-sig")
print(f"{len(need)} flooded sites -> {len(out)} receiving options; median distance {out.km.median():.1f} km")
print(out.groupby("from_name").km.min().describe().round(1).to_string())
