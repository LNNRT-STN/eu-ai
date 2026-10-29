"""Shelter plan inputs for the Shelter plan page (views/shelter_plan.py). Run after build_meuse.py:
python src/build_shelter_plan.py → out/meuse/shelters.parquet, shelter_edges.parquet, shelter_cells.parquet, at_risk.parquet

Shelters  OSM schools, colleges, sports halls, community centres, town halls and civic buildings in the Meuse scope,
          with their building footprints (Overpass `out geom`). A campus (school grounds) counts the buildings inside
          it; a point gets the buildings within 25 m. Floor area = footprint × building:levels (1 when untagged).
          A site qualifies when it is dry in July 2021 (not within 100 m of the mapped water), outside the EFAS 10- and
          100-year zones, and has ≥ MIN_FLOOR m² of floor. Capacity itself is set in the dashboard (m² per person).
Edges     every (~1 km cell with residents, shelter) pair within MAX_KM road distance; road km = straight km × DETOUR.
At risk   schools, hospitals and care homes inside the 2021 water (or within 100 m) or inside the 10/100-year zone."""
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
DST = OUT / "meuse"
RAW = OUT / "raw"
EFAS = {rp: DATA / f"cems-efas/Europe_RP{rp}_filled_depth.tif" for rp in (10, 100, 500)}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
UA = {"User-Agent": "eu-ai-challenge-2026-flood-src/0.1"}
EQUAL_AREA = 3035
MIN_FLOOR = 300   # m²: below this a site shelters under ~40 people, not worth a coordinated opening
MAX_LEVELS = 4    # cap odd building:levels tags
MAX_KM, DETOUR = 25, 1.3
LOCAL_NAME = {"Luik": "Liège", "Wezet": "Visé", "Limburg": "Limbourg", "Bitsingen": "Bassenge",  # as build_meuse.py
              "Saint-Nicolas (Luik)": "Saint-Nicolas", "Hoei": "Huy", "Namen": "Namur", "Borgworm": "Waremme"}
NOT_MEUSE = ("BE_71",)
SITE = ['["amenity"~"^(school|college|university|townhall|community_centre|social_centre|hospital|nursing_home)$"]',
        '["leisure"~"^(sports_hall|sports_centre)$"]', '["social_facility"~"^(nursing_home|assisted_living)$"]',
        '["building"~"^(school|sports_hall|civic|public|university|college|hospital)$"]']


def kind(t):
    a, l, b = t.get("amenity"), t.get("leisure"), t.get("building")
    if a == "hospital" or b == "hospital":
        return "Hospital"
    if a == "nursing_home" or t.get("social_facility") in ("nursing_home", "assisted_living"):
        return "Care home"
    if a in ("school", "college", "university") or b in ("school", "university", "college"):
        return "School"
    if l in ("sports_hall", "sports_centre") or b == "sports_hall":
        return "Sports hall"
    if a in ("community_centre", "social_centre"):
        return "Community centre"
    if a == "townhall" or b in ("civic", "public"):
        return "Town hall / civic"


def post_overpass(q):
    for attempt in range(6):
        try:
            r = requests.post(OVERPASS[attempt % 2], data={"data": q}, headers=UA, timeout=900)
            r.raise_for_status()
            return r.json()["elements"]
        except (requests.RequestException, ValueError) as err:
            print(f"overpass attempt {attempt + 1} failed: {err}")
            time.sleep(15 * (attempt + 1))
    raise RuntimeError("Overpass unavailable; rerun later")


def shape(el):
    """Polygon for a closed way or a multipolygon relation (outer rings), a point otherwise."""
    ring = lambda g: [(p["lon"], p["lat"]) for p in g]
    if el["type"] == "way" and len(el.get("geometry", [])) >= 4 and el["geometry"][0] == el["geometry"][-1]:
        return shapely.Polygon(ring(el["geometry"]))
    if el["type"] == "relation":
        outer = [shapely.Polygon(ring(m["geometry"])) for m in el.get("members", [])
                 if m.get("role") == "outer" and len(m.get("geometry", [])) >= 4 and m["geometry"][0] == m["geometry"][-1]]
        if outer:
            return shapely.union_all(outer)
    c = el.get("center", el)
    return shapely.Point(c["lon"], c["lat"]) if "lat" in c else None


aoi = gpd.read_file(DST / "aoi.geojson")
x0, y0, x1, y1 = aoi.total_bounds
cache = RAW / "shelters_osm.json"
if not cache.exists():
    bb = f"({y0},{x0},{y1},{x1})"
    q = (f"[out:json][timeout:900];(" + "".join(f"nwr{s}{bb};" for s in SITE) + ")->.s;"
         ".s out geom tags;"
         "way.s->.w;rel.s->.r;(.w;.r;)->.p;.p map_to_area->.a;way[building](area.a);out geom tags;"
         "node.s->.n;way[building](around.n:25);out geom tags;")
    cache.write_text(json.dumps({"elements": post_overpass(q)}))
els = {f"{e['type']}/{e['id']}": e for e in json.loads(cache.read_text())["elements"]}

rows = []
for oid, e in els.items():
    t = e.get("tags", {})
    g = shape(e)
    if g is None or not g.is_valid and not (g := g.buffer(0)).is_valid:
        continue
    lv = pd.to_numeric(t.get("building:levels"), errors="coerce")
    rows.append((oid, kind(t), t.get("name", ""), "building" in t, 1 if pd.isna(lv) else min(max(lv, 1), MAX_LEVELS), g))
f = gpd.GeoDataFrame(rows, columns=["osm_id", "type", "name", "is_bldg", "levels", "geometry"], crs=4326).to_crs(EQUAL_AREA)
sites = f[f["type"].notna()].copy()
bldg = f[f.is_bldg & (f.geom_type != "Point")].copy()
bldg["floor"] = bldg.area * bldg.levels

# each building belongs to the site it sits in (campus); a point site takes its one nearest building within 25 m
inside = gpd.sjoin(bldg.set_geometry(bldg.representative_point())[["osm_id", "floor", "geometry"]],
                   sites[sites.geom_type != "Point"][["osm_id", "geometry"]].rename(columns={"osm_id": "site"}),
                   predicate="within").drop_duplicates("osm_id")  # nested campuses: count once
near = gpd.sjoin_nearest(sites[sites.geom_type == "Point"][["osm_id", "geometry"]].rename(columns={"osm_id": "site"}),
                         bldg[~bldg.osm_id.isin(inside.osm_id)][["osm_id", "floor", "geometry"]],
                         max_distance=25).drop_duplicates("site")
floor = pd.concat([inside[["site", "floor"]], near[["site", "floor"]]]).groupby("site").floor.sum()
own = sites.is_bldg & (sites.geom_type != "Point") & ~sites.osm_id.isin(inside.osm_id)  # a tagged building, standalone
sites["floor"] = sites.osm_id.map(floor).fillna(0) + np.where(own, sites.area * sites.levels, 0)
sites = sites[~sites.osm_id.isin(inside.osm_id) | sites.osm_id.isin(floor.index)]  # a tagged hall inside a school: once

# hazard at the site (any part of the footprint for 2021, representative point for EFAS)
flood = gpd.read_file(OUT / "flood.geojson").to_crs(EQUAL_AREA).union_all()
sites["wet2021"] = sites.dwithin(flood, 100)
sites["in2021"] = sites.intersects(flood)
pt = sites.representative_point()
sites["efas"] = "none"
for rp in (500, 100, 10):  # wettest wins
    with rasterio.open(EFAS[rp]) as src:
        p = pt.to_crs(src.crs)
        d = np.array([v[0] for v in src.sample(zip(p.x, p.y), masked=True)], dtype=object)
    sites.loc[np.array([v is not np.ma.masked and float(v) > 0 for v in d]), "efas"] = f"RP{rp}"

sites = sites.set_geometry(pt).to_crs(4326)
sites["lon"], sites["lat"] = sites.geometry.x, sites.geometry.y
lau = gpd.read_parquet(RAW / "LAU_RG_01M_2021_4326.parquet").rename_geometry("geometry").set_crs(4326, allow_override=True)
lau = lau[lau.CNTR_CODE.isin(["BE", "DE", "NL"])].cx[x0:x1, y0:y1].rename(columns={"GISCO_ID": "lau_id", "LAU_NAME": "commune"})
lau["commune"] = lau.commune.replace(LOCAL_NAME)
sites = gpd.sjoin(sites, lau[["lau_id", "commune", "geometry"]], predicate="within").drop(columns="index_right")
sites = sites[~sites.lau_id.str.startswith(NOT_MEUSE)].drop_duplicates("osm_id")
sites["name"] = sites.name.where(sites.name.str.strip() != "", "Unnamed " + sites["type"].str.lower())
sites["flood_2021"] = np.select([sites.in2021, sites.wet2021], ["In the water", "Within 100 m"], "Dry")
sites["model_zone"] = sites.efas.map({"RP10": "10-year zone", "RP100": "100-year zone", "RP500": "500-year zone only",
                                      "none": "Outside all zones"})
zone = sites.efas.isin(["RP10", "RP100"])

# 1. at-risk schools and care sites (flag list)
care = sites["type"].isin(["School", "Hospital", "Care home"])
risk = sites[care & (sites.wet2021 | zone)]
risk[["osm_id", "type", "name", "commune", "lau_id", "lon", "lat", "flood_2021", "model_zone"]].sort_values(
    ["type", "commune", "name"]).to_parquet(DST / "at_risk.parquet", index=False)

# 2. shelters
sh = sites[sites["type"].isin(["School", "Sports hall", "Community centre", "Town hall / civic"])
           & ~sites.wet2021 & ~zone & (sites.floor >= MIN_FLOOR)].reset_index(drop=True)
sh["sid"] = sh.index
sh[["sid", "osm_id", "type", "name", "commune", "lau_id", "lon", "lat", "floor", "model_zone"]].to_parquet(
    DST / "shelters.parquet", index=False)

# 3. cell → shelter road distances (cells from build_meuse.py, both lenses)
cells = pd.read_parquet(DST / "cells.parquet")
cells = cells[cells.residents > 0].assign(lon=lambda d: (d.lon0 + d.lon1) / 2, lat=lambda d: (d.lat0 + d.lat1) / 2)
pos = cells[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
cxy = np.radians(pos.to_numpy())
sxy = np.radians(sh[["lat", "lon"]].to_numpy())
c_lat, c_lon = cxy[:, :1], cxy[:, 1:]
a = np.sin((sxy[:, 0] - c_lat) / 2) ** 2 + np.cos(c_lat) * np.cos(sxy[:, 0]) * np.sin((sxy[:, 1] - c_lon) / 2) ** 2
road = 2 * 6371 * np.arcsin(np.sqrt(a)) * DETOUR
i, j = np.nonzero(road <= MAX_KM)
edges = pd.DataFrame({"lat": pos.lat.to_numpy()[i], "lon": pos.lon.to_numpy()[i], "sid": j, "km": road[i, j].round(2)})
edges = cells[["lens", "cell", "lon", "lat"]].merge(edges, on=["lon", "lat"])[["lens", "cell", "sid", "km"]]
edges.to_parquet(DST / "shelter_edges.parquet", index=False)
cg = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326)
cg = gpd.sjoin_nearest(cg.to_crs(EQUAL_AREA), lau[["lau_id", "commune", "geometry"]].to_crs(EQUAL_AREA)).drop_duplicates(["lens", "cell"])
cg[["lens", "cell", "lon", "lat", "residents", "lau_id", "commune"]].to_parquet(DST / "shelter_cells.parquet", index=False)

print(f"{len(sh)} shelters, {sh.floor.sum():,.0f} m² floor; by type:\n{sh.groupby("type").floor.agg(['size', 'sum']).to_string()}")
print(f"{len(sites[sites["type"].isin(['School', 'Sports hall', 'Community centre', 'Town hall / civic'])])} candidate sites before filters")
print(f"at risk:\n{risk.groupby('type').size().to_string()}")
print(f"{len(edges):,} edges")
