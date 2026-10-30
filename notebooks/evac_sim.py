"""Evacuation road simulation: the July 2021 flood comes back, residents leave BEFORE the water arrives.

Run from eu-ai/:  source .venv/bin/activate && python -u notebooks/evac_sim.py
Inputs (outputs/data/): app_towns.csv (variant == "worst"), bus_plan.csv, flood_<area>_worst.geojson,
municipality_outlines.geojson. Roads: OpenStreetMap, Geofabrik extracts already in cache/osm/*.osm.pbf (downloaded
2026-10-29; the public Overpass server did not answer, so osmnx downloads were replaced by these local files). The
highway lines of each extract are cached once in cache/osm/<extract>.highways.gpkg.
Outputs: outputs/data/evac_towns.csv (one row per town), outputs/data/evac_edges.geojson (top 15 loaded roads per town).

Road graph (built here, no osmnx): every OSM way with a highway tag, split at every vertex; ways meet where they share
an OSM node (same coordinate). Walk graph = all highway types except motorway / motorway_link / construction /
proposed / abandoned / raceway / bus_guideway / platform, minus foot=no and access=private|no; two-way.
Drive graph = motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street, service and
*_link, minus access=private|no; oneway=yes|1|true and junction=roundabout one way, oneway=-1 reversed.
Only the largest connected part of each graph is kept (cuts off unconnected fragments at the bbox edge).

Method
1. Towns: every municipality with people >= 300 in app_towns (worst). Graph bbox = flood polygons inside the
   municipality + that town's bus_plan shelters, padded by 1 km.
2. Origins: walk-graph nodes inside the 2021 flood polygon AND inside the municipality outline. The town's `people`
   is spread EVENLY over these nodes (ASSUMPTION: the cleaned data has no per-building residents, so where people
   live inside the flood zone is not known at node level; nodes are denser where roads are denser).
3a. Time to leave the water on foot: shortest walk-graph distance from each origin to the nearest node outside the
   area's 2021 flood polygon (the whole area's flood, not only this municipality's part). Speeds: 4 km/h
   (ASSUMPTION: usual planning walking speed for adults) and 3 km/h (ASSUMPTION: older or less mobile people).
   People-weighted median and 90th percentile. No slope, crowding, debris or darkness penalty.
3b. Route to shelter: origins are assigned to the town's bus_plan shelters by walk-graph distance, greedy nearest
   pair first, each shelter taking at most its bus_plan `people` for this town. People bus_plan does not place
   (bus_plan total < town people) are `people_no_shelter`. Mode: walk if walk-graph distance <= 1.5 km (the shelter
   plan's walking reach), else bus on the drive graph (one-ways respected) from the drive node nearest the origin.
   Bus speed 30 km/h (ASSUMPTION: average for a bus on built-up valley roads; not calibrated). Boarding, waiting
   and repeat trips are NOT included, so bus times are a lower bound.
3c. Road load: people summed over the shortest-path routes per graph segment (walkers on walk segments, bus
   passengers on drive segments, counted as people, not vehicles); reported per OSM way as the maximum over its
   segments. Top 15 ways per town with OSM name, way length and bridge tag (bridge present and not "no").
3d. Routes through water: share of placed people whose route, AFTER its first node outside the flood, uses a
   segment whose midpoint lies inside the 2021 flood (these routes should be re-routed). Bridges inside the flood
   used by any route = distinct OSM bridge ways with a used segment inside the flood.
4. Sanity checks (printed and stored): walk-graph / straight-line distance ratio for origin -> shelter pairs over
   200 m apart (people-weighted median; expected about 1.2-1.6); sum of origin people == app_towns people; placed +
   no shelter + no route == people.
Limits: OSM is 2026, not 2021 (rebuilt bridges may differ); roads may already be flooded or blocked before the
evacuation; Vesdre flood is modelled (EFAS 500-year), never add it to observed areas.
"""
import os
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / os.environ.get("OUT_DIR", "outputs/data")   # OUT_DIR=outputs/rp: each return period (variant column)
VARIANTS = ["rp10", "rp100", "rp500"] if D.name == "rp" else ["worst"]
C = ROOT / "cache" / "osm"

MIN_PEOPLE = 300
WALK_KMH, SLOW_KMH, BUS_KMH = 4.0, 3.0, 30.0
WALK_MAX_M = 1500
PAD_M = 1000
TOP_EDGES = 15
CUTOFF_M = 40000
NO_WALK = {"motorway", "motorway_link", "construction", "proposed", "abandoned", "raceway", "bus_guideway",
           "platform", "corridor", "elevator", "escape", "emergency_bay", "rest_area", "services"}
DRIVE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
         "service", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}


def tag(g, k):
    return g["other_tags"].astype("string").str.extract(rf'"{k}"=>"([^"]*)"', expand=False)


def highways():
    """All highway lines of all extracts, cached per extract (one slow pass over each .pbf)."""
    fr = []
    for f in sorted(C.glob("*-latest.osm.pbf")):
        out = C / f.name.replace(".osm.pbf", ".highways.gpkg")
        if not out.exists():
            print(f"  reading highways from {f.name} (once)")
            g = pyogrio.read_dataframe(f, layer="lines", where="highway IS NOT NULL",
                                       columns=["osm_id", "name", "highway", "other_tags"])
            for k in ("bridge", "foot", "access", "oneway", "junction"):
                g[k] = tag(g, k)
            g.drop(columns="other_tags").to_file(out, driver="GPKG")
        fr.append(out)
    return fr


def load_roads(files, bbox):
    g = pd.concat([gpd.read_file(f, bbox=bbox) for f in files], ignore_index=True)
    return gpd.GeoDataFrame(g.drop_duplicates("osm_id"), crs=4326)


def build(roads, mode, utm):
    """Segment graph from road lines. Returns dict with node xy, csr matrix, segment table."""
    acc = roads.access.fillna("")
    if mode == "walk":
        r = roads[~roads.highway.isin(NO_WALK) & (roads.foot.fillna("") != "no")
                  & (~acc.isin(["private", "no"]) | roads.foot.isin(["yes", "designated", "permissive"]))]
    else:
        r = roads[roads.highway.isin(DRIVE) & ~acc.isin(["private", "no"])]
    r = r.to_crs(utm).reset_index(drop=True)
    xy, li = shapely.get_coordinates(r.geometry.values, return_index=True)
    same = li[1:] == li[:-1]
    a, b, way = np.where(same)[0], np.where(same)[0] + 1, li[:-1][same]
    key = np.round(xy, 1)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    u, v = inv[a], inv[b]
    keep = u != v
    u, v, way = u[keep], v[keep], way[keep]
    length = np.hypot(*(uniq[u] - uniq[v]).T)
    n = len(uniq)
    if mode == "walk":
        fu, fv = np.r_[u, v], np.r_[v, u]
        sid = np.r_[np.arange(len(u)), np.arange(len(u))]
    else:
        ow = r.oneway.fillna("").to_numpy()[way]
        rb = (r.junction.fillna("").to_numpy()[way] == "roundabout")
        fwd = np.isin(ow, ["yes", "1", "true"]) | rb
        rev = ow == "-1"
        sid_all = np.arange(len(u))
        f1, r1 = ~rev, ~fwd  # forward allowed unless reversed; backward allowed unless one way
        fu, fv = np.r_[u[f1], v[r1]], np.r_[v[f1], u[r1]]
        sid = np.r_[sid_all[f1], sid_all[r1]]
    # largest weakly connected component
    M0 = csr_matrix((np.ones(len(fu)), (fu, fv)), shape=(n, n))
    _, lab = connected_components(M0, directed=True, connection="weak")
    big = np.bincount(lab).argmax()
    ok = (lab[fu] == big) & (lab[fv] == big)
    fu, fv, sid = fu[ok], fv[ok], sid[ok]
    # keep shortest of parallel arcs: csr sums duplicates, so dedupe first
    arcs = pd.DataFrame({"u": fu, "v": fv, "sid": sid, "len": length[sid] + 1e-3}).sort_values("len")
    arcs = arcs.drop_duplicates(["u", "v"])
    M = csr_matrix((arcs["len"].to_numpy(), (arcs.u.to_numpy(), arcs.v.to_numpy())), shape=(n, n))
    arc_sid = dict(zip(zip(arcs.u.to_numpy(), arcs.v.to_numpy()), arcs.sid.to_numpy()))
    in_big = lab == big
    seg = pd.DataFrame({"u": u, "v": v, "way": way, "len": length})
    return {"xy": uniq, "M": M, "arc": arc_sid, "seg": seg, "roads": r, "in_big": in_big}


def wq(x, w, q):
    """People-weighted quantile."""
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = np.isfinite(x) & (w > 0)
    if not ok.any():
        return np.nan
    x, w = x[ok], w[ok]
    o = np.argsort(x)
    c = np.cumsum(w[o]) / w.sum()
    return float(x[o][min(np.searchsorted(c, q), len(x) - 1)])


def flood_flags(G, fl_utm):
    G["node_in"] = shapely.contains_xy(fl_utm, G["xy"][:, 0], G["xy"][:, 1])
    s = G["seg"]
    mid = (G["xy"][s.u.to_numpy()] + G["xy"][s.v.to_numpy()]) / 2
    s["in_flood"] = shapely.contains_xy(fl_utm, mid[:, 0], mid[:, 1])
    br = G["roads"].bridge.fillna("no").to_numpy()
    s["bridge"] = ~np.isin(br[s.way.to_numpy()], ["no"])


def nearest(G, pts):
    big = np.where(G["in_big"])[0]
    return big[cKDTree(G["xy"][big]).query(pts)[1]]


def trace(G, pred, start, f, load, used):
    """Follow the shortest-path tree to the shelter; add load; True if route re-enters flood after first exit."""
    s, node_in, arc = G["seg"], G["node_in"], G["arc"]
    n, out, wet = start, not node_in[start], False
    while True:
        p = pred[n]
        if p < 0:
            break
        k = arc.get((n, p), arc.get((p, n)))
        load[k] += f
        used.add(k)
        if out and s.in_flood.iat[k]:
            wet = True
        n = p
        if not node_in[n]:
            out = True
    return wet


def top_ways(G, load, mode):
    s = G["seg"].assign(people=load)
    s = s[s.people > 0]
    if s.empty:
        return pd.DataFrame()
    w = s.groupby("way").agg(people=("people", "max"), in_flood=("in_flood", "any"))
    r = G["roads"].iloc[w.index]
    return pd.DataFrame({"mode": mode, "name": r["name"].fillna(r["highway"]).values, "osm_id": r.osm_id.values,
                         "people": w.people.values, "length_m": r.length.values, "bridge": G["seg"].groupby("way")
                         .bridge.first().reindex(w.index).values, "in_flood_2021": w.in_flood.values,
                         "geometry": r.geometry.values})


def run_town(row, sh, flood, outline, files):
    name = row.municipality
    fl_town = gpd.clip(flood, outline)
    g = gpd.GeoSeries(list(fl_town.geometry) + list(gpd.points_from_xy(sh.s_lon, sh.s_lat)), crs=4326)
    utm = g.estimate_utm_crs()
    bb = gpd.GeoSeries([box(*g.to_crs(utm).total_bounds).buffer(PAD_M)], crs=utm).to_crs(4326).total_bounds
    roads = load_roads(files, tuple(bb))
    fl_utm = flood.to_crs(utm).union_all()
    shapely.prepare(fl_utm)
    town_utm = outline.to_crs(utm).union_all()
    W, R = build(roads, "walk", utm), build(roads, "drive", utm)
    flood_flags(W, fl_utm), flood_flags(R, fl_utm)

    origin = np.where(W["node_in"] & W["in_big"] & shapely.contains_xy(town_utm, W["xy"][:, 0], W["xy"][:, 1]))[0]
    if len(origin) == 0:
        return None, None, "no road node inside the flood"
    P = float(row.people)
    pp = np.full(len(origin), P / len(origin))

    # (a) exit: multi-source Dijkstra from every dry node of the connected walk graph
    dry = np.where(~W["node_in"] & W["in_big"])[0]
    dexit = dijkstra(W["M"], indices=dry, min_only=True, limit=CUTOFF_M)[origin]

    # (b) assignment by walk distance (walk graph symmetric)
    sh = sh.reset_index(drop=True)
    s_xy = np.c_[gpd.GeoSeries(gpd.points_from_xy(sh.s_lon, sh.s_lat), crs=4326).to_crs(utm).x,
                 gpd.GeoSeries(gpd.points_from_xy(sh.s_lon, sh.s_lat), crs=4326).to_crs(utm).y]
    s_w = nearest(W, s_xy)
    Dw, Pw = dijkstra(W["M"], indices=s_w, return_predecessors=True, limit=CUTOFF_M)
    Do = Dw[:, origin]  # shelters x origins
    jj, ii = np.where(np.isfinite(Do))
    order = np.argsort(Do[jj, ii], kind="stable")
    cap = sh.people.to_numpy(float).copy()
    left = pp.copy()
    flows = []
    for j, i in zip(jj[order], ii[order]):
        if left[i] <= 1e-9 or cap[j] <= 1e-9:
            continue
        f = min(left[i], cap[j])
        left[i] -= f
        cap[j] -= f
        flows.append((i, j, f))
    no_shelter = left.sum()

    o_xy = W["xy"][origin]
    o_d, s_d = nearest(R, o_xy), nearest(R, s_xy)
    need = sorted({j for i, j, f in flows if Do[j, i] > WALK_MAX_M})
    Dd, Pd = {}, {}
    if need:  # distance TO the shelter = Dijkstra on the transposed (reversed) drive graph
        dd, pdd = dijkstra(R["M"].T.tocsr(), indices=s_d[need], return_predecessors=True, limit=CUTOFF_M)
        for k, j in enumerate(need):
            Dd[j], Pd[j] = dd[k], pdd[k]

    wload, dload = np.zeros(len(W["seg"])), np.zeros(len(R["seg"]))
    used_w, used_d = set(), set()
    t_min, t_w, ratios, r_w = [], [], [], []
    walk_p = bus_p = noroute_p = wet_p = 0.0
    for i, j, f in flows:
        dw = Do[j, i]
        if dw <= WALK_MAX_M:
            walk_p += f
            t_min.append(dw / 1000 / WALK_KMH * 60); t_w.append(f)
            wet = trace(W, Pw[j], origin[i], f, wload, used_w)
        else:
            d = Dd[j][o_d[i]]
            if not np.isfinite(d):
                noroute_p += f
                continue
            bus_p += f
            t_min.append(d / 1000 / BUS_KMH * 60); t_w.append(f)
            wet = trace(R, Pd[j], o_d[i], f, dload, used_d)
        wet_p += f * wet
        sl = np.hypot(*(o_xy[i] - s_xy[j]))
        if sl > 200:
            ratios.append(dw / sl); r_w.append(f)
    placed = walk_p + bus_p

    def flood_bridges(G, used):
        s = G["seg"].iloc[sorted(used)] if used else G["seg"].iloc[[]]
        return set(G["roads"].osm_id.iloc[s[s.in_flood & s.bridge].way].tolist())
    fb = flood_bridges(W, used_w) | flood_bridges(R, used_d)

    te = pd.concat([top_ways(W, wload, "walk"), top_ways(R, dload, "bus")], ignore_index=True)
    te = te.sort_values("people", ascending=False).drop_duplicates("osm_id").head(TOP_EDGES)
    te = gpd.GeoDataFrame(te.assign(municipality=name, area=row.area), geometry="geometry", crs=utm).to_crs(4326)
    te["people"], te["length_m"] = te.people.round(0), te.length_m.round(0)

    q = lambda x, w, p: round(wq(x, w, p), 1)
    out = {
        "area": row.area, "municipality": name, "source": row.source, "people": P, "origin_nodes": len(origin),
        "exit_med_m": q(dexit, pp, .5), "exit_p90_m": q(dexit, pp, .9),
        "exit_med_min_4kmh": round(wq(dexit, pp, .5) / 1000 / WALK_KMH * 60, 1),
        "exit_p90_min_4kmh": round(wq(dexit, pp, .9) / 1000 / WALK_KMH * 60, 1),
        "exit_med_min_3kmh": round(wq(dexit, pp, .5) / 1000 / SLOW_KMH * 60, 1),
        "exit_p90_min_3kmh": round(wq(dexit, pp, .9) / 1000 / SLOW_KMH * 60, 1),
        "exit_unreachable_people": round(pp[~np.isfinite(dexit)].sum()),
        "shelters": len(sh), "people_walk": round(walk_p), "people_bus": round(bus_p),
        "people_no_shelter": round(no_shelter), "people_no_route": round(noroute_p),
        "route_med_min": q(t_min, t_w, .5), "route_p90_min": q(t_min, t_w, .9),
        "reroute_share": round(wet_p / placed, 3) if placed else np.nan,
        "flood_bridges_used": len(fb),
        "busiest_road": te["name"].iat[0] if len(te) else "", "busiest_road_people": te.people.iat[0] if len(te) else 0,
        "busiest_road_mode": te["mode"].iat[0] if len(te) else "",
        "check_net_straight_ratio_med": q(ratios, r_w, .5),
        "check_origin_people_sum": round(pp.sum(), 1),
        "check_people_balance": round(placed + noroute_p + no_shelter - P, 3),
        "walk_nodes": int(W["in_big"].sum()), "drive_nodes": int(R["in_big"].sum()),
    }
    return out, te, ""


def main():
    t0 = time.time()
    files = highways()
    towns_all = pd.read_csv(D / "app_towns.csv", encoding="utf-8-sig")
    bus_all = pd.read_csv(D / "bus_plan.csv", encoding="utf-8-sig")
    outl = gpd.read_file(D / "municipality_outlines.geojson")
    rows, edges, skipped = [], [], []
    for v in VARIANTS:
      towns = towns_all[(towns_all.variant == v) & (towns_all.people >= MIN_PEOPLE)].sort_values("people", ascending=False)
      bus = bus_all[bus_all.variant == v] if "variant" in bus_all else bus_all
      for r in towns.itertuples():
        t1 = time.time()
        print(f"{v} {r.municipality} ({r.area}, {r.people} people)")
        sh = bus[bus.municipality == r.municipality]
        if sh.empty:
            skipped.append((v, r.municipality, "no bus_plan shelters")); continue
        flood = gpd.read_file(D / f"flood_{r.area}_{v}.geojson").to_crs(4326)
        out, te, why = run_town(r, sh, flood, outl[outl.municipality == r.municipality], files)
        if out is None:
            skipped.append((v, r.municipality, why)); print("  SKIP", why); continue
        out["runtime_s"] = round(time.time() - t1)
        out["variant"] = v
        rows.append(out); edges.append(te.assign(variant=v))
        print("  exit 4 km/h med/p90 {exit_med_min_4kmh}/{exit_p90_min_4kmh} min | route med/p90 {route_med_min}/"
              "{route_p90_min} | walk {people_walk} bus {people_bus} no shelter {people_no_shelter} no route "
              "{people_no_route} | reroute {reroute_share} | flood bridges {flood_bridges_used} | busiest "
              "{busiest_road} {busiest_road_people} | ratio {check_net_straight_ratio_med} | sum "
              "{check_origin_people_sum} bal {check_people_balance} | {runtime_s}s".format(**out))
    df = pd.DataFrame(rows)
    df.to_csv(D / "evac_towns.csv", index=False)
    e = gpd.GeoDataFrame(pd.concat(edges, ignore_index=True), crs=4326)
    e["geometry"] = e.geometry.simplify(0.00005)
    e[["municipality", "area", *(["variant"] if D.name == "rp" else []), "mode", "name", "osm_id", "people",
       "length_m", "bridge", "in_flood_2021", "geometry"]].to_file(D / "evac_edges.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    print("\nSkipped:", skipped or "none")
    print("Sanity: net/straight ratio medians", df.check_net_straight_ratio_med.tolist())
    print("Sanity: max |origin people - app_towns people|", (df.check_origin_people_sum - df.people).abs().max(),
          "| max |balance|", df.check_people_balance.abs().max())
    print(f"Runtime {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
