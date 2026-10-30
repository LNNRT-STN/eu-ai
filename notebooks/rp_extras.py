"""Return-period demo, step 2: the app tables for the EFAS 10-, 100- and 500-year zones (outputs/rp/).
Run from eu-ai/ after  FLOOD=rp python -I notebooks/pipeline.py :  python -I notebooks/rp_extras.py
Then:  OUT_DIR=outputs/rp python -I notebooks/addresses.py ; OUT_DIR=outputs/rp python -I notebooks/shelter_addresses.py ;
       OUT_DIR=outputs/rp python -u notebooks/evac_sim.py

Writes, in outputs/rp/ (same columns as outputs/data/, one row per variant rp10 / rp100 / rp500 where it varies):
  app_towns.csv, q4_ranking.csv, q4_headline.json, municipality_outlines.geojson (GISCO LAU 2021),
  buildings_3d.parquet (OBAT buildings in the 500-year zone, flags in_rp10 / in_rp100 / in_rp500; the zones are
  nested, so the widest holds them all), receiving_sites.csv (dry hospitals / care homes for each flooded one; a
  receiving site must be dry in the 500-year zone, so it holds for every return period).
Everything here is modelled (EFAS), so `source` is "modelled" throughout; there is no observed / modelled split.
"""
import json, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd, geopandas as gpd, pyogrio, shapely
from common import M, OBAT

D = Path("outputs/rp")
VARIANTS = ("rp10", "rp100", "rp500"); W = VARIANTS[-1]
AREAS = [("ahr", "de"), ("liege", "be"), ("rochefort", "be"), ("venlo", "nl"), ("eschweiler", "de"), ("wassenberg", "de"),
         ("schleiden", "de"), ("euskirchen", "de"), ("erftstadt", "de"), ("vesdre", "be")]   # order = pipeline.py
OUTSIDE = "(outside mapped municipalities)"
m = pd.read_csv(D / "municipalities.csv"); s = pd.read_csv(D / "area_summary.csv"); c = pd.read_csv(D / "critical_sites.csv")
c = c.drop_duplicates(["name", "lon", "lat"])   # the Vesdre box lies inside Liège's: its care sites come twice
c.to_csv(D / "critical_sites.csv", index=False, encoding="utf-8-sig")
bus = pd.read_csv(D / "bus_plan.csv")

# ---- municipality outlines and centroids (GISCO LAU 2021; a repeated name takes the polygon nearest its area's flood)
lau = gpd.read_file("cache/gisco/lau_be_nl_de.gpkg")
lau["municipality"] = lau["LAU_NAME"] + " (" + lau["CNTR_CODE"] + ")"
flood = {(a, v): gpd.read_file(D / f"flood_{a}_{v}.geojson").to_crs(M).union_all() for a, _ in AREAS for v in VARIANTS}
pick = {}
for (a, name) in m[m.municipality != OUTSIDE][["area", "municipality"]].drop_duplicates().itertuples(index=False):
    cand = lau[lau.municipality == name]
    if len(cand):
        pick[(a, name)] = cand.geometry.distance(flood[(a, W)].centroid).idxmin()
outl = lau.loc[sorted(set(pick.values()))].drop_duplicates("municipality")
outl = outl.rename(columns={"GISCO_ID": "lau_id", "POP_2021": "population_2021", "AREA_KM2": "area_km2"})
outl = outl[["municipality", "lau_id", "population_2021", "area_km2", "geometry"]].to_crs(4326)
outl["geometry"] = outl.geometry.simplify(0.0005)
outl.to_file(D / "municipality_outlines.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
pt = lau.geometry.representative_point().to_crs(4326)
lonlat = {k: (round(pt[i].x, 4), round(pt[i].y, 4)) for k, i in pick.items()}
print(len(outl), "municipality outlines")

# ---- per-variant town table (as q4_ranking.py's app_towns.csv)
t = m[(m.people >= 1) & (m.municipality != OUTSIDE)].copy()
t["no_shelter"] = t.no_reach + t.full
t["lon"] = [lonlat.get((a, n), (None, None))[0] for a, n in zip(t.area, t.municipality)]
t["lat"] = [lonlat.get((a, n), (None, None))[1] for a, n in zip(t.area, t.municipality)]
t["source"] = "modelled"
bc = bus.groupby(["variant", "area", "municipality"]).people.sum().rename("bus_covered")
t = t.merge(bc, left_on=["variant", "area", "municipality"], right_index=True, how="left")
t["bus_covered"] = t.bus_covered.fillna(0).round()
t.to_csv(D / "app_towns.csv", index=False, encoding="utf-8-sig")
print(t.groupby("variant")[["people", "no_shelter", "bus_covered"]].sum().round())

# ---- ranking per variant: residents with no shelter in reach (central assumptions), care sites shown beside it
cc = c[c.share_of_site_flooded >= .05]
rows = []
for v in VARIANTS:
    r = t[t.variant == v].copy()
    x = cc[cc[f"in_{v}_flood"].astype(bool)]
    vul = x[x.type.isin(["hospital", "care home"])]
    k = ["area", "municipality"]
    r = r.set_index(k)
    r["hospitals_carehomes_flooded"] = vul.groupby(k).size().reindex(r.index).fillna(0).astype(int)
    r["schools_flooded"] = x[x.type == "school"].groupby(k).size().reindex(r.index).fillna(0).astype(int)
    r["vulnerable_sites"] = vul.groupby(k).name.apply(lambda s: "; ".join(sorted(s))).reindex(r.index).fillna("")
    r = r.reset_index().sort_values(["no_shelter", "hospitals_carehomes_flooded"], ascending=False).reset_index(drop=True)
    r.insert(0, "rank", r.index + 1)
    r["why"] = np.where(r.no_reach > r.full, "shelters too far", np.where(r.full > 0, "shelters full", "-"))
    r["source"] = f"MODELLED (EFAS {v[2:]}-yr)"
    rows.append(r)
rank = pd.concat(rows, ignore_index=True)
rank["people_first_pass"], rank["no_shelter_first_pass"], rank["q2_evidence"] = np.nan, np.nan, ""
rank[["rank", "variant", "municipality", "area", "source", "people", "covered", "no_shelter", "why", "no_reach", "full",
      "people_first_pass", "no_shelter_first_pass", "hospitals_carehomes_flooded", "schools_flooded",
      "vulnerable_sites", "q2_evidence", "lon", "lat"]].to_csv(D / "q4_ranking.csv", index=False, encoding="utf-8-sig")


# ---- headline per variant (as q4_ranking.py; all modelled, so the totals sit under "modelled")
def tot(d):
    return dict(people=int(d.people_2020.sum()), people_2025=int(d.people_2025.sum()), sheltered=int(d.central_covered.sum()),
                no_shelter=int((d.central_no_reach + d.central_full).sum()), too_far=int(d.central_no_reach.sum()),
                full=int(d.central_full.sum()),
                no_shelter_range=[int(d.people_2020.sum() - d.high_covered.sum()), int(d.people_2020.sum() - d.low_covered.sum())],
                coordination_gain=int((d.central_covered - d.central_covered_nearest_first).sum()),
                bus_covered=int(d.bus_covered.sum()), bus_no_shelter=int((d.people_2020 - d.bus_covered).sum()),
                buildings=int(d.buildings.sum()), flood_km2=round(float(d.flood_km2.sum()), 1))


def sites(v):
    x = cc[cc[f"in_{v}_flood"].astype(bool)]
    vul = x[x.type.isin(["hospital", "care home"])]
    by = vul.groupby("municipality").size().sort_values(ascending=False)
    return dict(vulnerable=int(len(vul)), schools=int((x.type == "school").sum()),
                top_town=by.index[0] if len(by) else None, top_town_count=int(by.iloc[0]) if len(by) else 0)


head = {v: dict(modelled=tot(s[s.variant == v]), sites=sites(v)) for v in VARIANTS}
json.dump(head, open(D / "q4_headline.json", "w"), indent=2, default=str)
print(json.dumps({v: head[v]["modelled"] for v in VARIANTS}, indent=1))

# ---- OBAT buildings in the 500-year zone, flagged per return period (input of addresses.py)
outm = outl[["municipality", "geometry"]]
seen, pts = set(), []
for area, cn in AREAS:
    z = {v: gpd.GeoSeries([flood[(area, v)]], crs=M).to_crs(4326).iloc[0] for v in VARIANTS}
    if z[W].is_empty:
        continue
    b = pyogrio.read_dataframe(OBAT[cn], bbox=tuple(z[W].bounds), columns=["id", "use", "epoch", "height"])
    b = b[shapely.contains_xy(z[W], b.geometry.x.values, b.geometry.y.values)]
    b = b[~b["id"].isin(seen)]; seen |= set(b["id"])
    j = gpd.sjoin(b, outm, predicate="within", how="left")
    b["municipality"] = j[~j.index.duplicated()]["municipality"].reindex(b.index).fillna(OUTSIDE)
    h = b["height"].where(b["height"] > 0)
    d = pd.DataFrame(dict(area=area, lon=b.geometry.x.round(5), lat=b.geometry.y.round(5), use=b["use"].values,
                          height_m=h.round(1), storeys=np.clip(np.round(h / 3.0), 1, 10), epoch=b["epoch"].values,
                          municipality=b["municipality"]))
    for v in VARIANTS:
        d[f"in_{v}"] = shapely.contains_xy(z[v], d.lon.values, d.lat.values)
    d[f"in_{W}"] = True
    pts.append(d); print(area, len(d), "buildings in the 500-year zone", flush=True)
pd.concat(pts, ignore_index=True).to_parquet(D / "buildings_3d.parquet", index=False)

# ---- receiving hospitals / care homes (as receiving.py), dry in the 500-year zone
K, MAX_KM = 3, 30
need = cc[cc[f"in_{W}_flood"].astype(bool) & cc.type.isin(["hospital", "care home"])]
f = gpd.read_file("cache/osm/facilities.gpkg")
g = lambda col: f[col].where(f[col].notna(), "") if col in f else ""
f["kind"] = np.where((g("amenity") == "hospital") | (g("healthcare") == "hospital") | (g("building") == "hospital"), "hospital",
                     np.where((g("amenity") == "nursing_home") | g("social_facility").isin(["nursing_home", "assisted_living"]),
                              "care home", ""))
f = f[f.kind != ""].copy()
p = f.to_crs(M).geometry.representative_point(); f["x"], f["y"] = p.x.values, p.y.values
ll = p.to_crs(4326); f["lon"], f["lat"] = ll.x.values, ll.y.values
f = f.sort_values("name").assign(gx=lambda d: (d.x // 300).astype(int), gy=lambda d: (d.y // 300).astype(int))
f = f.drop_duplicates(["kind", "name", "gx", "gy"])
wet = shapely.unary_union([flood[(a, W)] for a, _ in AREAS])
dry = f[~shapely.contains_xy(wet, f.x.values, f.y.values)]
rows = []
for r0 in need.itertuples():
    q = gpd.GeoSeries(gpd.points_from_xy([r0.lon], [r0.lat]), crs=4326).to_crs(M).iloc[0]
    x = dry[dry.kind == r0.type].assign(km=lambda d: np.hypot(d.x - q.x, d.y - q.y) / 1000)
    for r in x[(x.km <= MAX_KM) & (x.km > .3)].nsmallest(K, "km").itertuples():
        rows.append(dict(from_name=r0.name, from_town=r0.municipality, from_area=r0.area, type=r0.type,
                         to_name=r.name if isinstance(r.name, str) else f"Unnamed {r.kind}",
                         km=round(r.km, 1), lon=round(r.lon, 5), lat=round(r.lat, 5)))
pd.DataFrame(rows).to_csv(D / "receiving_sites.csv", index=False, encoding="utf-8-sig")
print(f"{len(need)} flooded care sites -> {len(rows)} receiving options")
