"""Q3: could we shelter the exposed people using buildings standing today?
Run from eu-ai/:  .venv/Scripts/python.exe -I notebooks/q3_shelters.py [area_key]
Steps: 1 exposed group (Q1) -> 2 OSM candidates (pull + clean) -> 3 capacity from OBAT buildings
       -> 4 exclude flooded sites, flag critical sites -> 5 reach + capacity allocation.
Assumptions (stated, varied in the sensitivity block): floor height 3 m, usable share, m2 per person, walk distance.
"""
import sys, json, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd, geopandas as gpd, shapely
import osmnx as ox
from common import M, flood_geom, read_pop, read_buildings, attach_people

AREAS = {"ahr": ("DE Ahr (EMSR517 AOI15)", "de", "EMSR517_AOI15_")}
key = sys.argv[1] if len(sys.argv) > 1 else "ahr"
NAME, CC, EMS = AREAS[key]
OUT = Path("outputs/q3") / key; OUT.mkdir(parents=True, exist_ok=True)
ox.settings.use_cache = True; ox.settings.cache_folder = "cache/osmnx"; ox.settings.log_console = False
MIN_FLOOR_M2 = 200            # smallest usable shelter (gross floor area)
FLOOR_H = 3.0                 # metres per storey
CENTRAL = dict(use=0.5, m2=4.0, walk=1500)
SCEN = {"low": dict(use=0.4, m2=5.0, walk=1000), "central": CENTRAL, "high": dict(use=0.6, m2=3.0, walk=2500)}
log = {"area": NAME}
def say(*a): print(*a, flush=True)

# ---- 1. Exposed group -------------------------------------------------------------------------------
fl_prod, _ = flood_geom(CC, EMS, ("PRODUCT",))
fl_all, _ = flood_geom(CC, EMS, ("PRODUCT", "MONIT"))
x0, y0, x1, y1 = gpd.GeoSeries([fl_all], crs=M).to_crs(4326).total_bounds
BBOX = (x0 - .05, y0 - .05, x1 + .05, y1 + .05)       # flood + ~5 km
b = attach_people(read_buildings(CC, BBOX), *read_pop(BBOX))
b["in_prod"] = shapely.contains_xy(fl_prod, b["x"].values, b["y"].values)
b["in_all"] = shapely.contains_xy(fl_all, b["x"].values, b["y"].values)
say(f"== 1. EXPOSED ({NAME}) ==")
for v in ("in_prod", "in_all"):
    e = b[b[v]]
    say(f"  {v}: buildings {len(e)}, residential {int((e.use==1).sum())}, people {e.people.sum():,.0f}")
    log[f"exposed_{v}"] = dict(buildings=len(e), people=round(float(e.people.sum())))

# ---- 2. OSM candidates: pull + clean --------------------------------------------------------------
TAGS = {"amenity": ["school", "college", "university", "kindergarten", "community_centre", "townhall", "events_venue",
                    "hospital", "nursing_home", "social_facility"],
        "leisure": ["sports_hall", "sports_centre"],
        "building": ["school", "sports_hall", "civic", "public", "hospital", "college", "university", "kindergarten"],
        "healthcare": ["hospital"], "social_facility": ["nursing_home", "assisted_living"]}
raw = ox.features.features_from_bbox(BBOX, TAGS).reset_index()
say(f"\n== 2. OSM raw: {len(raw)} features | geometry types {raw.geom_type.value_counts().to_dict()}")

def g(r, k):
    v = r.get(k); return v if isinstance(v, str) else ""
def classify(r):
    am, bl, le, hc, sf = g(r, "amenity"), g(r, "building"), g(r, "leisure"), g(r, "healthcare"), g(r, "social_facility")
    if am == "hospital" or hc == "hospital" or bl == "hospital": return "hospital"
    if am == "nursing_home" or sf in ("nursing_home", "assisted_living"): return "care home"
    if am in ("school", "college", "university", "kindergarten") or bl in ("school", "college", "university", "kindergarten"): return "school"
    if le in ("sports_hall", "sports_centre") or bl == "sports_hall": return "sports hall"
    if am in ("community_centre", "townhall", "events_venue") or bl in ("civic", "public"): return "civic"
    return None
raw["cat"] = raw.apply(classify, axis=1)
raw["name"] = raw.get("name", pd.Series(index=raw.index, dtype=object))
raw = raw[raw["cat"].notna() & raw.geom_type.isin(["Point", "Polygon", "MultiPolygon"])].to_crs(M)
say("  by category:", raw["cat"].value_counts().to_dict())
say("  without a name:", int(raw["name"].isna().sum()))

# Merge overlapping polygons of the same category into one site (campus + its buildings = one site)
sites = []
for cat, grp in raw.groupby("cat"):
    polys = grp[grp.geom_type != "Point"]; pts = grp[grp.geom_type == "Point"]
    comps = gpd.GeoDataFrame(geometry=list(getattr(shapely.unary_union(polys.geometry.values), "geoms", [shapely.unary_union(polys.geometry.values)])) if len(polys) else [], crs=M)
    comps = comps[~comps.is_empty]
    if len(comps):
        j = gpd.sjoin(comps, polys[["name", "geometry"]], predicate="intersects", how="left")
        comps["name"] = j.groupby(level=0)["name"].agg(lambda s: next((x for x in s if isinstance(x, str)), None))
    # drop points that sit inside (or within 30 m of) a polygon site of the same category: same facility
    if len(comps) and len(pts):
        near = gpd.sjoin_nearest(pts, comps[["geometry"]], max_distance=30, how="left")
        pts = pts.loc[near[near["index_right"].isna()].index.unique()]
    sites.append(pd.concat([comps.assign(cat=cat, kind="polygon"), pts[["name", "geometry"]].assign(cat=cat, kind="point")], ignore_index=True))
sites = gpd.GeoDataFrame(pd.concat(sites, ignore_index=True), crs=M)
say(f"  after de-duplication: {len(sites)} sites (from {len(raw)} features) | by category {sites['cat'].value_counts().to_dict()}")
log["osm"] = dict(raw=len(raw), sites=len(sites), by_cat=sites["cat"].value_counts().to_dict())

# ---- 3. Capacity from OBAT buildings ------------------------------------------------------------
b["floors"] = np.maximum(1, np.floor(b["height"].fillna(2.5) / FLOOR_H))
b["gfa"] = b["area"] * b["floors"]
pts_b = gpd.GeoDataFrame(b[["area", "height", "floors", "gfa", "use"]], geometry=gpd.points_from_xy(b.x, b.y), crs=M)
poly = sites[sites.kind == "polygon"]
inpoly = gpd.sjoin(pts_b, poly[["geometry"]], predicate="within")
gfa = inpoly.groupby("index_right")["gfa"].sum()
nbld = inpoly.groupby("index_right").size()
pnt = sites[sites.kind == "point"]
nearest = gpd.sjoin_nearest(pnt[["geometry"]], pts_b, max_distance=50, how="left", distance_col="d")
nearest = nearest[~nearest.index.duplicated()]
sites["gfa"] = pd.concat([gfa, nearest["gfa"]]).reindex(sites.index).fillna(0.0)
sites["n_buildings"] = pd.concat([nbld, nearest["gfa"].notna().astype(int)]).reindex(sites.index).fillna(0).astype(int)
say(f"\n== 3. CAPACITY: sites with no OBAT building matched: {int((sites.n_buildings==0).sum())} | "
    f"below {MIN_FLOOR_M2} m2: {int(((sites.gfa>0)&(sites.gfa<MIN_FLOOR_M2)).sum())}")

# ---- 4. Flooded sites and critical facilities ---------------------------------------------------
sites["in_flood"] = sites.intersects(fl_all)
crit = sites[sites["cat"].isin(["hospital", "care home", "school"]) & sites["in_flood"]]
say(f"\n== 4. CRITICAL SITES INSIDE THE 2021 FLOOD (PRODUCT+MONIT): {len(crit)}")
for _, r in crit.sort_values("cat").iterrows(): say(f"   - {r['cat']}: {r['name'] or '(no name)'}")
log["critical_in_flood"] = crit[["cat", "name"]].fillna("(no name)").to_dict("records")
shel = sites[sites["cat"].isin(["school", "sports hall", "civic"]) & ~sites["in_flood"] & (sites.gfa >= MIN_FLOOR_M2)].copy()
say(f"  usable shelter sites (outside flood, >= {MIN_FLOOR_M2} m2): {len(shel)} | by category {shel['cat'].value_counts().to_dict()}")
say(f"  excluded because flooded: {int((sites['cat'].isin(['school','sports hall','civic']) & sites['in_flood']).sum())}")

# ---- 5. Reach + capacity allocation (greedy, nearest first, straight-line distance) ------------
def allocate(exp, shel, s):
    cap = (shel["gfa"] * s["use"] / s["m2"]).values.copy()
    q = shel.sindex.query(exp.geometry, predicate="dwithin", distance=s["walk"])
    d = exp.geometry.values[q[0]].distance(shel.geometry.values[q[1]])
    order = np.argsort(d); need = exp["people"].values.copy(); reach = np.zeros(len(exp), bool); reach[q[0]] = True
    for i, j in zip(q[0][order], q[1][order]):
        if need[i] > 0 and cap[j] > 0:
            t = min(need[i], cap[j]); need[i] -= t; cap[j] -= t
    total = exp["people"].sum(); no_reach = exp["people"].values[~reach].sum()
    return dict(people=round(total), covered=round(total - need.sum()), no_reach=round(no_reach),
                full=round(need.sum() - no_reach), capacity=round((shel["gfa"] * s["use"] / s["m2"]).sum()))
say("\n== 5. COVERAGE (straight-line reach) ==")
res = {}
for v in ("in_prod", "in_all"):
    exp = gpd.GeoDataFrame(b[b[v] & (b.people > 0)][["people"]], geometry=gpd.points_from_xy(b[b[v] & (b.people > 0)].x, b[b[v] & (b.people > 0)].y), crs=M)
    for sc, s in SCEN.items():
        r = allocate(exp, shel, s); res[f"{v}:{sc}"] = r
        say(f"  {v:8s} {sc:8s} walk {s['walk']} m, {s['m2']} m2/p, {int(s['use']*100)}% usable -> {r}")
log["coverage"] = res

# ---- outputs for the app --------------------------------------------------------------------
sites.assign(capacity_central=(sites.gfa * CENTRAL["use"] / CENTRAL["m2"]).round()).to_crs(4326)[
    ["name", "cat", "kind", "gfa", "n_buildings", "in_flood", "capacity_central", "geometry"]].to_file(OUT / "sites.geojson", driver="GeoJSON")
json.dump(log, open(OUT / "q3_results.json", "w"), indent=2, default=str)
say("\nsaved", OUT)
