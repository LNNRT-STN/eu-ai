"""Enrich the data with open external data: OSM critical facilities inside the EMS AOIs
(with observed flood and EFAS hazard flags), OSM rivers and streams clipped to the AOIs,
and the NUTS3 regions the AOIs touch.

Raw downloads are cached in src/out/raw/ and reused. Licences: OSM data (c) OpenStreetMap
contributors, ODbL; NUTS boundaries (c) EuroGeographics for the administrative boundaries.
"""
import json, time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
import shapely

DATA = Path(__file__).resolve().parents[1] / "data" / "working_data"
OUT = Path(__file__).resolve().parent / "out"
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)

EFAS = {rp: DATA / f"cems-efas/Europe_RP{rp}_filled_depth.tif" for rp in (10, 100, 500)}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
GISCO = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/"
UA = {"User-Agent": "eu-ai-challenge-2026-flood-src/0.1"}
EQUAL_AREA = 3035
SELECTORS = [
    '["amenity"~"^(hospital|clinic|nursing_home|school|kindergarten|childcare|fire_station|police|townhall)$"]',
    '["social_facility"~"^(nursing_home|assisted_living)$"]',
    '["power"="substation"]',
    '["man_made"~"^(wastewater_plant|water_works)$"]',
]
AMENITY = {"hospital": "hospital", "clinic": "hospital", "nursing_home": "care_home",
           "school": "school", "kindergarten": "kindergarten", "childcare": "kindergarten",
           "fire_station": "fire_station", "police": "police", "townhall": "town_hall"}

aoi = gpd.read_file(OUT / "aoi.geojson")[["aoi_id", "geometry"]]
flood = gpd.read_file(OUT / "flood.geojson")[["geometry"]]


def category(t):
    if t.get("amenity") in AMENITY and t["amenity"] != "nursing_home":
        return AMENITY[t["amenity"]]
    if t.get("amenity") == "nursing_home" or t.get("social_facility") in ("nursing_home", "assisted_living"):
        return "care_home"
    if t.get("power") == "substation":
        return "power_substation"
    if t.get("man_made") in ("wastewater_plant", "water_works"):
        return "water_treatment"


def post_overpass(q):
    """POST a query, retrying busy servers (502/504/429) and falling back to a mirror."""
    for attempt in range(6):
        try:
            r = requests.post(OVERPASS[attempt % 2], data={"data": q}, headers=UA, timeout=360)
            r.raise_for_status()
            return r.json()["elements"]
        except (requests.RequestException, ValueError) as err:
            print(f"overpass attempt {attempt + 1} failed: {err}")
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("Overpass unavailable; rerun later")


def overpass(bbox):
    s, w, n, e = bbox
    body = "".join(f"nwr{sel}({s},{w},{n},{e});" for sel in SELECTORS)
    return post_overpass(f"[out:json][timeout:300];({body});out center tags;")


# 1. OSM facilities (union bbox, falling back to one query per AOI)
cache = RAW / "overpass.json"
if not cache.exists():
    w, s, e, n = aoi.total_bounds
    try:
        elements = overpass((s, w, n, e))
    except RuntimeError as err:
        print(f"union query failed ({err}); querying per AOI")
        elements = []
        for b in aoi.bounds.itertuples():
            elements += overpass((b.miny, b.minx, b.maxy, b.maxx))
    cache.write_text(json.dumps({"elements": elements}))
elements = json.loads(cache.read_text())["elements"]

rows = {}
for el in elements:
    t, c = el.get("tags", {}), el.get("center", el)
    cat = category(t)
    if cat and "lat" in c:
        rows[f"{el['type']}/{el['id']}"] = (cat, t.get("name", ""), c["lon"], c["lat"])
fac = pd.DataFrame([(k, *v) for k, v in rows.items()], columns=["osm_id", "category", "name", "lon", "lat"])
fac = gpd.GeoDataFrame(fac, geometry=gpd.points_from_xy(fac.lon, fac.lat), crs=4326)
fac = gpd.sjoin(fac, aoi, predicate="within").drop(columns="index_right")
fac = fac.drop_duplicates("osm_id").reset_index(drop=True)

flood_union = flood.union_all()
fac["in_flood"] = fac.within(flood_union)
flood_3035 = flood.to_crs(EQUAL_AREA).union_all()
fac["near_flood"] = fac.to_crs(EQUAL_AREA).dwithin(flood_3035, 100)

fac["efas"] = "none"
for rp in (500, 100, 10):  # wettest-first wins: RP10 overrides RP100 overrides RP500
    with rasterio.open(EFAS[rp]) as src:
        pts = fac.to_crs(src.crs).geometry
        depth = np.array([v[0] for v in src.sample(zip(pts.x, pts.y), masked=True)], dtype=object)
    wet = np.array([d is not np.ma.masked and float(d) > 0 for d in depth])
    fac.loc[wet, "efas"] = f"RP{rp}"

cols = ["osm_id", "category", "name", "lon", "lat", "aoi_id", "in_flood", "near_flood", "efas"]
fac[cols].to_parquet(OUT / "osm_facilities.parquet", index=False)

# 2. NUTS3 regions intersecting the AOIs
index = requests.get(GISCO + "nuts-2021-files.json", headers=UA, timeout=60).json() \
    if not (RAW / "nuts-2021-files.json").exists() else json.loads((RAW / "nuts-2021-files.json").read_text())
(RAW / "nuts-2021-files.json").write_text(json.dumps(index))
fname = "NUTS_RG_01M_2021_4326_LEVL_3.geojson"
nuts_raw = RAW / fname
if not nuts_raw.exists():
    r = requests.get(GISCO + "geojson/" + fname, headers=UA, timeout=300)
    r.raise_for_status()
    nuts_raw.write_bytes(r.content)
nuts = gpd.read_file(nuts_raw).to_crs(4326)
nuts = nuts[nuts.intersects(aoi.union_all())]
nuts = nuts.rename(columns={"NUTS_ID": "nuts_id", "NAME_LATN": "name", "CNTR_CODE": "country"})
nuts[["nuts_id", "name", "country", "geometry"]].to_file(OUT / "nuts3.geojson", driver="GeoJSON")

# 3. OSM waterways inside the AOIs (one query per AOI; streams matter because EFAS skips
#    rivers with a catchment below 500 km²)
cache = RAW / "waterways.json"
if not cache.exists():
    ways = {}
    for b in aoi.bounds.itertuples():
        q = (f'[out:json][timeout:300];way["waterway"~"^(river|canal|stream)$"]'
             f'({b.miny},{b.minx},{b.maxy},{b.maxx});out geom tags;')
        ways.update({w["id"]: w for w in post_overpass(q) if "geometry" in w})
    cache.write_text(json.dumps({"elements": list(ways.values())}))
ways = json.loads(cache.read_text())["elements"]
wat = gpd.GeoDataFrame(
    [{"kind": "stream" if w["tags"]["waterway"] == "stream" else "river", "name": w["tags"].get("name", "")}
     for w in ways],
    geometry=[shapely.LineString([(g["lon"], g["lat"]) for g in w["geometry"]]) for w in ways], crs=4326)
wat = gpd.clip(wat, aoi.union_all()).explode(index_parts=False)
wat = wat[wat.geom_type == "LineString"]
wat["geometry"] = wat.to_crs(EQUAL_AREA).simplify(5).to_crs(4326)
wat.to_file(OUT / "waterways.geojson", driver="GeoJSON")

# 4. Summary
summary = fac.groupby("category").agg(
    n=("osm_id", "size"), in_flood=("in_flood", "sum"), near_flood=("near_flood", "sum"),
    efas_none=("efas", lambda s: (s == "none").sum()))
print(summary.to_string())
print(f"total {len(fac)} facilities; efas: {fac.efas.value_counts().to_dict()}")
print(f"waterways: {wat.kind.value_counts().to_dict()}")
print(f"{len(nuts)} NUTS3 regions: {', '.join(nuts.nuts_id + ' ' + nuts.name)}")
