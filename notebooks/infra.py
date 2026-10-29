"""Transport infrastructure inside the July 2021 flood (worst = all satellite passes; vesdre = EFAS 500-year model).
Per area, from today's OpenStreetMap (Geofabrik extracts 2026-10-29 in cache/osm/; public Overpass was unreachable):
  rail lines (railway=rail, not abandoned/disused) -> km inside the flood, line name/ref, stations/halts inside;
  bridges (bridge=* except no) on rail and main roads that intersect the flood;
  main roads (motorway, trunk, primary, secondary, incl. links) -> km inside the flood.
Each piece is split by municipality outline (outputs/data/municipality_outlines.geojson).
Outputs: outputs/data/infra_in_flood.csv, outputs/data/infra_rail.geojson.
Run from eu-ai/:  .venv/bin/python -I notebooks/infra.py
Caveat: OSM is 2026, not 2021 (rebuilt bridges/lines may differ in place or form). Bridges are counted as connected
groups of OSM bridge ways per kind (dual carriageways and parallel tracks on one structure count once).
"""
import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd, geopandas as gpd, pyogrio
from shapely.ops import unary_union

AREAS = ["ahr", "liege", "rochefort", "venlo", "eschweiler", "wassenberg", "schleiden", "euskirchen", "erftstadt", "vesdre"]
M = "EPSG:3035"
D = Path("outputs/data"); C = Path("cache/osm")
PBF = ["limburg", "koeln-regbez", "rheinland-pfalz", "belgium"]          # Geofabrik extracts, downloaded 2026-10-29
TEST = len(sys.argv) > 1                     # test mode: python infra.py <pbf> <area>; separate cache, no outputs
if TEST: PBF, AREAS = [sys.argv[1]], [sys.argv[2]]
ROADS = ["motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link", "secondary_link"]
WHERE = {"lines": "railway = 'rail' OR highway IN (%s)" % ",".join(f"'{r}'" for r in ROADS),
         "points": "other_tags LIKE '%\"railway\"=>\"station\"%' OR other_tags LIKE '%\"railway\"=>\"halt\"%'",
         "multilinestrings": "other_tags LIKE '%\"route\"=>\"railway\"%' OR other_tags LIKE '%\"route\"=>\"train\"%'"}


def tag(g, k):
    return g["other_tags"].astype("string").str.extract(rf'"{k}"=>"([^"]*)"', expand=False)


def layer(name):
    """One layer from all extracts, filtered, cached as gpkg (a raw re-parse takes minutes)."""
    out = C / f"{'_test_' if TEST else ''}infra_{name}.gpkg"
    if out.exists(): return gpd.read_file(out)
    fr = []
    for p in PBF:
        g = pyogrio.read_dataframe(C / f"{p}-latest.osm.pbf", layer=name, where=WHERE[name]); fr.append(g)
        print(f"  {p:16s} {name:16s} {len(g):6d}", flush=True)
    g = gpd.GeoDataFrame(pd.concat(fr, ignore_index=True), crs=4326).drop_duplicates(subset="osm_id")
    g.to_file(out, driver="GPKG"); return g


L, P, R = layer("lines"), layer("points"), layer("multilinestrings")
for k in ("bridge", "usage", "service", "ref", "disused", "abandoned"): L[k] = tag(L, k)
L = L[~L.usage.isin(["abandoned"]) & L.disused.isna() & L.abandoned.isna()].to_crs(M)
P["railway"] = tag(P, "railway"); P = P[tag(P, "disused").isna()].to_crs(M)
R["route"], R["ref"] = tag(R, "route"), tag(R, "ref")
R["label"] = (R.ref.fillna("") + " " + R["name"].fillna("")).str.strip(); R = R[R.label != ""].to_crs(M)
# line labels: infrastructure routes (route=railway, e.g. "KBS 477"/"L 37") first, else train services
RR = R[R.route == "railway"].copy(); RT = R[R.route == "train"].copy()

outl = gpd.read_file(D / "municipality_outlines.geojson")[["municipality", "geometry"]].to_crs(M)
rows, rail_out = [], []
for a in AREAS:
    fl = gpd.read_file(D / f"flood_{a}_worst.geojson").to_crs(M)
    flood = unary_union(fl.geometry.buffer(0))
    W = L.iloc[L.sindex.query(flood, predicate="intersects")].copy()
    W["kind"] = W.highway.str.replace("_link", "").radd("road_").where(W.railway != "rail", "rail")
    W["bridge"] = W.bridge.notna() & (W.bridge != "no")
    names = []
    for _, w in W.iterrows():
        if w.kind != "rail": names.append(w.ref if isinstance(w.ref, str) else (w["name"] if isinstance(w["name"], str) else "unnamed")); continue
        probe = w.geometry.interpolate(0.5, normalized=True).buffer(2)          # way midpoint on a route geometry
        rr = sorted(set(RR.iloc[RR.sindex.query(probe, predicate="intersects")].label))
        tr = sorted(set(RT.iloc[RT.sindex.query(probe, predicate="intersects")].label))
        own = [x for x in (w.ref, w["name"]) if isinstance(x, str)]                # way ref (e.g. Infrabel "L37")
        parts = list(dict.fromkeys(own + rr)) or [f"trains {', '.join(tr[:3])}" if tr else "unnamed rail"]
        n = "; ".join(parts)
        names.append(n + (f" (service={w.service})" if isinstance(w.service, str) else ""))
    W["name"] = names
    nodes = P.iloc[P.sindex.query(flood, predicate="contains")].assign(kind=lambda d: "rail_" + d.railway)
    # 1+3: km inside the flood per line/road, per municipality
    inside = W.copy(); inside["geometry"] = W.geometry.intersection(flood)
    inside = gpd.overlay(inside, outl, how="identity", keep_geom_type=True)
    inside["municipality"] = inside["municipality"].fillna("(outside outlines)")
    inside["km"] = inside.length / 1000
    for (mun, kind, name), g in inside.groupby(["municipality", "kind", "name"]):
        if g.km.sum() < 0.005: continue
        rows.append(dict(area=a, municipality=mun, kind=kind if kind == "rail" else "road_main", subkind=kind,
                         name=name, km_in_flood=round(g.km.sum(), 2), count=None, bridge=False))
    r = inside[inside.kind == "rail"]
    if len(r):
        r = r.dissolve(by=["municipality", "name"], as_index=False)[["municipality", "name", "geometry"]]
        r["area"] = a; r["source"] = "modelled EFAS 500-yr" if a == "vesdre" else "observed EMS all passes"
        r["km_in_flood"] = (r.length / 1000).round(2)
        rail_out.append(r.to_crs(4326))
    # 2: bridges = connected groups of bridge ways (one structure) per kind group, touching the flood
    B = W[W.bridge].copy()
    B["grp"] = B.kind.where(B.kind == "rail", "road_main")
    for grp, g in B.groupby("grp"):
        merged = gpd.GeoDataFrame(geometry=list(getattr(unary_union(g.geometry.buffer(15)), "geoms", [unary_union(g.geometry.buffer(15))])), crs=M)
        j = gpd.sjoin(g, merged, predicate="intersects")
        for _, s in j.groupby("index_right"):
            pt = s.geometry.unary_union.intersection(flood).representative_point()
            mun = outl[outl.contains(pt)].municipality
            rows.append(dict(area=a, municipality=mun.iloc[0] if len(mun) else "(outside outlines)", kind=f"bridge_{'rail' if grp == 'rail' else 'road'}",
                             subkind="; ".join(sorted(set(s.kind))), name="; ".join(sorted(set(s.name)))[:200],
                             km_in_flood=None, count=1, bridge=True))
    # stations / halts inside the flood
    if len(nodes):
        N = gpd.sjoin(nodes[["osm_id", "kind", "name", "geometry"]], outl, how="left", predicate="within")
        for _, s in N.iterrows():
            rows.append(dict(area=a, municipality=s.municipality if isinstance(s.municipality, str) else "(outside outlines)",
                             kind="station", subkind=s.kind, name=s["name"], km_in_flood=None, count=1, bridge=False))
    print(f"{a:11s} ways in flood {len(W):5d}", flush=True)

df = pd.DataFrame(rows)
if TEST: print(df.to_string()); sys.exit()
df.insert(1, "source", df.area.map(lambda x: "modelled EFAS 500-yr" if x == "vesdre" else "observed EMS all passes"))
df.sort_values(["area", "kind", "municipality", "name"]).to_csv(D / "infra_in_flood.csv", index=False)
rg = pd.concat(rail_out, ignore_index=True)
rg["geometry"] = rg.geometry.simplify(0.00005)
gpd.GeoDataFrame(rg, crs=4326).to_file(D / "infra_rail.geojson", driver="GeoJSON")
s = df.groupby("area").apply(lambda g: pd.Series(dict(
    rail_km=g[g.kind == "rail"].km_in_flood.sum().round(1), road_km=g[g.kind == "road_main"].km_in_flood.sum().round(1),
    stations=int((g.kind == "station").sum()), rail_bridges=int((g.kind == "bridge_rail").sum()),
    road_bridges=int((g.kind == "bridge_road").sum()))))
print(s.to_string())
