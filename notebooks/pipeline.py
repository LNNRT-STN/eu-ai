"""Full data pipeline: Q1 exposure + Q3 shelters for every study area, by municipality.
Run from eu-ai/:  .venv/Scripts/python.exe -I notebooks/pipeline.py
Decisions (change here):
  main flood  = EMS PRODUCT ; worst case = PRODUCT + MONIT (later monitoring images)
  Vesdre      = no EMS polygons -> EFAS modelled proxy: main = 100-year, worst = 500-year (validated in efas_validation)
  people      = dasymetric (cell residents spread over residential buildings by footprint area), GHS-POP 2020 (+2025 projection)
  shelters    = OSM schools / sports halls / civic buildings, capacity from OBAT footprint x floors (height / 3 m),
                excluded if they touch the worst-case flood; reach = straight-line distance
Outputs in outputs/data/.
"""
import sys, json, time, pickle, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
from rasterio import features as rfeat
from rasterio.windows import from_bounds
from shapely.validation import make_valid
import osmnx as ox
from common import D, M, flood_geom, read_pop, read_buildings, attach_people

OUT = Path("outputs/data"); OUT.mkdir(parents=True, exist_ok=True)
ox.settings.use_cache = True; ox.settings.cache_folder = "cache/osmnx"; ox.settings.log_console = False; ox.settings.requests_timeout = 300
ox.settings.max_query_area_size = 2e8                # ask OSM in ~200 km2 tiles: big single queries time out
AREAS = [  # order matters: a building exposed in two areas is counted in the first only
    dict(key="ahr", name="Ahr valley (DE)", cc="de", ems=["EMSR517_AOI15_", "EMSR517_AOI03_"]),
    dict(key="liege", name="Liege / Meuse (BE)", cc="be", ems=["EMSR518_AOI01_"]),
    dict(key="rochefort", name="Rochefort (BE)", cc="be", ems=["EMSR518_AOI02_"]),
    dict(key="venlo", name="Venlo / Meuse (NL)", cc="nl", ems=["EMSR520_AOI01_"]),
    dict(key="eschweiler", name="Eschweiler (DE)", cc="de", ems=["EMSR517_AOI09_"]),
    dict(key="wassenberg", name="Wassenberg (DE)", cc="de", ems=["EMSR517_AOI10_"]),
    dict(key="schleiden", name="Schleiden (DE)", cc="de", ems=["EMSR517_AOI18_"]),
    dict(key="euskirchen", name="Euskirchen-Rheinbach (DE)", cc="de", ems=["EMSR517_AOI08_"]),
    dict(key="erftstadt", name="Erftstadt (DE)", cc="de", ems=["EMSR517_AOI07_"]),
    dict(key="vesdre", name="Vesdre valley (BE) - MODELLED", cc="be", efas=(100, 500), bbox=(5.60, 50.54, 5.97, 50.64)),
]
EFAS_THR = 0.1                                       # m of water depth counted as flooded
MIN_GFA, FLOOR_H, MAX_FLOORS = 200, 3.0, 10
SCEN = {"low": dict(use=0.4, m2=5.0, walk=1000), "central": dict(use=0.5, m2=4.0, walk=1500), "high": dict(use=0.6, m2=3.0, walk=2500),
        "bus": dict(use=0.5, m2=4.0, walk=10000)}   # central capacity, but buses take people up to 10 km (straight line)
VARIANTS = ("main", "worst")
def say(*a): print(*a, flush=True)

# ---------------------------------------------------------------- helpers
def efas_depth(rp, bbox):
    with rasterio.open(D / f"cems-efas/Europe_RP{rp}_filled_depth.tif") as r:
        win = from_bounds(*bbox, transform=r.transform).round_offsets().round_lengths()
        return r.read(1, window=win), r.window_transform(win)

def efas_polygon(rp, bbox):
    d, t = efas_depth(rp, bbox)
    shp = [shapely.geometry.shape(s) for s, v in rfeat.shapes((d > EFAS_THR).astype("uint8"), transform=t) if v == 1]
    return gpd.GeoSeries(shp, crs=4326).to_crs(M).unary_union

def sample(d, t, b):
    c = np.floor((b["lon"].values - t.c) / t.a).astype(int); r = np.floor((b["lat"].values - t.f) / t.e).astype(int)
    ok = (r >= 0) & (r < d.shape[0]) & (c >= 0) & (c < d.shape[1])
    return np.where(ok, d[np.clip(r, 0, d.shape[0] - 1), np.clip(c, 0, d.shape[1] - 1)], -9999.0)

def aoi_union(cc, keys):
    parts = [gpd.read_file(f).to_crs(M) for prod in (D / f"ems_{cc}").iterdir() if prod.is_dir() and any(k in prod.name for k in keys)
             for f in prod.glob("*areaOfInterestA*.shp")]
    return pd.concat(parts).unary_union

LAU = None
def municipalities(bbox):
    """Official municipality borders: Eurostat GISCO LAU 2021 (cache/gisco/lau_be_nl_de.gpkg, EPSG:3035)."""
    global LAU
    if LAU is None: LAU = gpd.read_file("cache/gisco/lau_be_nl_de.gpkg")
    win = gpd.GeoSeries([shapely.geometry.box(*bbox)], crs=4326).to_crs(M).iloc[0]
    f = LAU[LAU.intersects(win)]
    return gpd.GeoDataFrame({"name": f["LAU_NAME"] + " (" + f["CNTR_CODE"] + ")"}, geometry=f.geometry.values, crs=M)

def local_osm(bbox):
    """OSM candidates from the local Geofabrik extract (notebooks/osm_extract.py), same columns as an Overpass result."""
    return gpd.read_file("cache/osm/facilities.gpkg", bbox=bbox, engine="pyogrio")

def overpass(bbox, tags, tries=4):                       # kept for reference: public server was at capacity on 2026-10-29
    for i in range(tries):
        try: return ox.features.features_from_bbox(bbox, tags)
        except Exception as e:
            say(f"  OSM request failed ({type(e).__name__}), retry {i + 1}/{tries} in {30 * (i + 1)} s"); time.sleep(30 * (i + 1))
    raise RuntimeError("OSM server unavailable")

def assign_muni(gdf, munis):
    j = gpd.sjoin(gdf[["geometry"]], munis, predicate="within", how="left")
    return j[~j.index.duplicated()]["name"].reindex(gdf.index).fillna("(outside mapped municipalities)")

TAGS = {"amenity": ["school", "college", "university", "kindergarten", "community_centre", "townhall", "events_venue", "hospital", "nursing_home", "social_facility"],
        "leisure": ["sports_hall", "sports_centre"], "building": ["school", "sports_hall", "civic", "public", "hospital", "college", "university", "kindergarten"],
        "healthcare": ["hospital"], "social_facility": ["nursing_home", "assisted_living"]}
def _g(r, k): v = r.get(k); return v if isinstance(v, str) else ""
def classify(r):
    am, bl, le, hc, sf = (_g(r, k) for k in ("amenity", "building", "leisure", "healthcare", "social_facility"))
    if am == "hospital" or hc == "hospital" or bl == "hospital": return "hospital"
    if am == "nursing_home" or sf in ("nursing_home", "assisted_living"): return "care home"
    if am in ("school", "college", "university", "kindergarten") or bl in ("school", "college", "university", "kindergarten"): return "school"
    if le in ("sports_hall", "sports_centre") or bl == "sports_hall": return "sports hall"
    if am in ("community_centre", "townhall", "events_venue") or bl in ("civic", "public"): return "civic"
    return None

def osm_sites(bbox, qc):
    raw = local_osm(bbox)
    qc["osm_raw"] = len(raw)
    raw["cat"] = raw.apply(classify, axis=1)
    if "name" not in raw: raw["name"] = None
    raw = raw[raw["cat"].notna() & raw.geom_type.isin(["Point", "Polygon", "MultiPolygon"])].to_crs(M)
    qc["osm_in_scope"] = len(raw); qc["osm_unnamed"] = int(raw["name"].isna().sum())
    out = []
    for cat, grp in raw.groupby("cat"):
        polys, pts = grp[grp.geom_type != "Point"], grp[grp.geom_type == "Point"]
        # 1) overlapping shapes of one category = one site; 2) parts of one campus (within 75 m) = one site
        comps = gpd.GeoDataFrame(geometry=[], crs=M)
        if len(polys):
            u = shapely.unary_union(polys.buffer(37.5).values)
            comps = gpd.GeoDataFrame(geometry=list(getattr(u, "geoms", [u])), crs=M)
            comps["geometry"] = [shapely.unary_union(polys[polys.intersects(c)].geometry.values) for c in comps.geometry]
            j = gpd.sjoin(comps, polys[["name", "geometry"]], predicate="intersects", how="left")
            comps["name"] = j.groupby(level=0)["name"].agg(lambda s: next((x for x in s if isinstance(x, str)), None))
            comps["parts"] = j.groupby(level=0).size()
        if len(comps) and len(pts):
            near = gpd.sjoin_nearest(pts, comps[["geometry"]], max_distance=75, how="left")
            pts = pts.loc[near[near["index_right"].isna()].index.unique()]
        out.append(pd.concat([comps.assign(cat=cat, kind="polygon"), pts[["name", "geometry"]].assign(cat=cat, kind="point", parts=1)], ignore_index=True))
    s = gpd.GeoDataFrame(pd.concat(out, ignore_index=True), crs=M)
    qc["sites_after_dedup"] = len(s)
    return s

def tukey_upper(s, k=3.0):
    """Extreme-outlier fence on a log scale (sizes are skewed): Q3 + k * IQR."""
    l = np.log10(s[s > 0])
    if len(l) < 8: return float("inf")                  # too few values to call anything an outlier
    q1, q3 = l.quantile([.25, .75]); return float(10 ** (q3 + k * (q3 - q1)))

def capacity(sites, b, qc):
    # Missing data, analysed not hidden: OBAT height is NaN for some buildings and floored at 2.5 m by design
    # (GHS-OBAT doc p.19). Both mean "no usable height" -> 1 storey (conservative), and both are counted.
    h = b["height"]
    b = b.assign(height_missing=h.isna(), height_at_floor=h.le(2.5),
                 floors=np.clip(np.floor(h.fillna(2.5) / FLOOR_H), 1, MAX_FLOORS))
    pts = gpd.GeoDataFrame(b[["area", "floors", "height_missing", "height_at_floor"]].assign(gfa=b["area"] * b["floors"]),
                           geometry=gpd.points_from_xy(b.x, b.y), crs=M)
    inside = gpd.sjoin(pts, sites[sites.kind == "polygon"][["geometry"]], predicate="within")
    near = gpd.sjoin_nearest(sites[sites.kind == "point"][["geometry"]], pts, max_distance=50, how="left")
    near = near[~near.index.duplicated()]
    matched = pd.concat([inside.rename(columns={"index_right": "site"}).reset_index(drop=True),
                         near.dropna(subset=["gfa"]).rename_axis("site").reset_index()], ignore_index=True)
    sites["gfa"] = matched.groupby("site")["gfa"].sum().reindex(sites.index).fillna(0.0)
    qc["shelter_buildings_matched"] = len(matched)
    qc["shelter_buildings_height_missing"] = int(matched["height_missing"].sum())
    qc["shelter_buildings_height_at_2.5m_floor"] = int(matched["height_at_floor"].sum())
    qc["sites_no_building"] = int((sites.gfa == 0).sum()); qc["sites_too_small"] = int(((sites.gfa > 0) & (sites.gfa < MIN_GFA)).sum())
    # Outliers (book p.223-224: detect beyond a threshold, then cap): one site's floor area far above the rest
    # usually means a wrong match (e.g. an OSM point snapped to an industrial hall). Cap at the fence and list them.
    fence = tukey_upper(sites.gfa); out = sites[sites.gfa > fence]
    qc["capacity_fence_m2"] = None if np.isinf(fence) else round(fence)
    qc["capacity_outliers_capped"] = [dict(name=r["name"] if isinstance(r["name"], str) else "(no name)", cat=r["cat"], gfa_m2=round(r.gfa))
                                      for _, r in out.iterrows()]
    sites["gfa_raw"] = sites["gfa"]; sites["gfa"] = sites["gfa"].clip(upper=fence)
    return sites

SCALE = 1000
def allocate_maxflow(exp, shel, s, flows=False):
    """Best possible plan: maximum flow (CLRS ch.26, p.669-670). Supersource -> each exposed building (capacity = its
    residents) -> every shelter in walking reach (unbounded) -> supersink (capacity = shelter places). Units: 0.001 person (0.1 dropped small fractions)."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow
    n, m = len(exp), len(shel); need = np.round(exp["people"].values * SCALE).astype(np.int64)
    reach = np.zeros(n, bool); got = np.zeros(n)
    if n and m:
        q = shel.sindex.query(exp.geometry, predicate="dwithin", distance=s["walk"]); reach[q[0]] = True
        cap = np.round((shel["gfa"] * s["use"] / s["m2"]).values * SCALE).astype(np.int64)
        big = int(min(need.sum() + 1, 2**31 - 1))
        S, T = 0, n + m + 1
        rows = np.concatenate([np.zeros(n, int), 1 + q[0], 1 + n + np.arange(m)])
        cols = np.concatenate([1 + np.arange(n), 1 + n + q[1], np.full(m, T)])
        caps = np.concatenate([np.minimum(need, 2**31 - 1), np.full(len(q[0]), big), np.minimum(cap, 2**31 - 1)]).astype(np.int32)
        f = maximum_flow(csr_matrix((caps, (rows, cols)), shape=(T + 1, T + 1)), S, T, method="dinic").flow
        got = np.asarray(f[0, 1:n + 1].todense()).ravel() / SCALE
        assert got.sum() <= cap.sum() / SCALE + 1e-6, "max-flow exceeds shelter capacity"
        if flows:                                            # who goes where: building i -> shelter j, people
            fs = f[1:n + 1, n + 1:n + m + 1].tocoo()
            keep = fs.data > 0
            flow_df = pd.DataFrame({"i": fs.row[keep], "j": fs.col[keep], "people": fs.data[keep] / SCALE})
    got = np.minimum(got, exp["people"].values)
    e = exp.assign(covered=got, reach=reach)
    e["no_reach"] = np.where(~reach, e.people, 0.0); e["full"] = np.where(reach, e.people - e.covered, 0.0)
    assert np.allclose(e.covered + e.no_reach + e.full, e.people, atol=0.2), "people buckets do not add up"
    assert (e[["covered", "no_reach", "full"]] >= -1e-6).all().all(), "negative people"
    if flows:
        e.attrs["flows"] = flow_df if n and m else pd.DataFrame(columns=["i", "j", "people"])
    return e

def allocate(exp, shel, s):
    """Nearest-first greedy: each exposed building's residents go to the nearest shelter in reach that still has room."""
    cap = (shel["gfa"] * s["use"] / s["m2"]).values.copy()
    need = exp["people"].values.copy(); reach = np.zeros(len(exp), bool)
    if len(shel) and len(exp):
        q = shel.sindex.query(exp.geometry, predicate="dwithin", distance=s["walk"])
        reach[q[0]] = True
        d = exp.geometry.values[q[0]].distance(shel.geometry.values[q[1]])
        for i, j in zip(q[0][np.argsort(d)], q[1][np.argsort(d)]):
            if need[i] > 0 and cap[j] > 0:
                t = min(need[i], cap[j]); need[i] -= t; cap[j] -= t
    e = exp.assign(left=need, reach=reach)
    e["no_reach"] = np.where(~e.reach, e.people, 0.0); e["full"] = np.where(e.reach, e.left, 0.0); e["covered"] = e.people - e.left
    # consistency: every exposed person is in exactly one bucket, nothing negative, no shelter over capacity
    assert np.allclose(e.covered + e.no_reach + e.full, e.people), "people buckets do not add up"
    assert (e[["covered", "no_reach", "full"]] >= -1e-6).all().all(), "negative people"
    assert (cap >= -1e-6).all(), "shelter over capacity"
    return e

# ---------------------------------------------------------------- run
seen, summary, muni_rows, crit_rows, shelters_all, qc_all, validation = set(), [], [], [], [], {}, {}
bus_rows = []                                    # bus plan: (area, municipality) -> shelter, people
for A in AREAS:
    key, cc = A["key"], A["cc"]; qc = {}
    if len(sys.argv) > 1 and key not in sys.argv[1:]: continue      # optional: run only the named areas
    say(f"\n######## {A['name']}")
    part = OUT / "parts" / f"{key}.pkl"; part.parent.mkdir(exist_ok=True)
    if part.exists():                                   # finished in an earlier run: reuse it
        p = pickle.load(open(part, "rb"))
        summary += p["summary"]; muni_rows += p["muni"]; crit_rows += p["crit"]; shelters_all.append(p["shel"])
        qc_all[key] = p["qc"]; validation.update(p["val"]); seen |= p["seen"]; bus_rows += p.get("bus", [])
        say("  (cached)"); continue
    n0 = (len(summary), len(muni_rows), len(crit_rows), len(bus_rows))
    if "efas" in A:
        bbox = A["bbox"]; fl = {"main": efas_polygon(A["efas"][0], bbox), "worst": efas_polygon(A["efas"][1], bbox)}
        npoly = {"main": None, "worst": None}; source = f"EFAS modelled {A['efas'][0]}-year (main) / {A['efas'][1]}-year (worst)"
    else:
        parts = {v: [flood_geom(cc, k, kinds) for k in A["ems"]] for v, kinds in (("main", ("PRODUCT",)), ("worst", ("PRODUCT", "MONIT")))}
        fl = {v: shapely.unary_union([p[0] for p in parts[v]]) for v in VARIANTS}
        npoly = {v: sum(p[1] for p in parts[v]) for v in VARIANTS}; source = "EMS observed (PRODUCT main / +MONIT worst)"
        x0, y0, x1, y1 = gpd.GeoSeries([fl["worst"]], crs=M).to_crs(4326).total_bounds
        bbox = (x0 - .05, y0 - .05, x1 + .05, y1 + .05)
    b = attach_people(read_buildings(cc, bbox), *read_pop(bbox, 2020))
    b["people25"] = attach_people(b.drop(columns=["row", "col", "cellpop", "people"]), *read_pop(bbox, 2025))["people"].reindex(b.index).fillna(0.0)
    for v in VARIANTS: b[f"in_{v}"] = shapely.contains_xy(fl[v], b["x"].values, b["y"].values)
    # Missing-data analysis (book p.210) and sanity checks on the exposed group
    win_pop = float(read_pop(bbox, 2020)[0].sum()); placed = float(b["people"].sum())
    assert placed <= win_pop * 1.0001, "dasymetric placed more people than exist"
    ex = b[b.in_worst]
    ppm2 = (ex["people"] / ex["area"].where(ex["area"] > 0)).dropna()     # ["area"] = OBAT footprint, not .area (geometry)
    qc.update(window_population=round(win_pop), population_not_on_any_home=round(win_pop - placed),
              population_not_on_any_home_pct=round(100 * (win_pop - placed) / max(win_pop, 1), 1),
              exposed_buildings=len(ex), exposed_height_missing=int(ex.height.isna().sum()),
              exposed_use0_outside_builtup=int((ex.use == 0).sum()),
              exposed_people_per_m2_max=round(float(ppm2.max()), 2) if len(ppm2) else None,
              exposed_buildings_people_density_outliers=int((ppm2 > tukey_upper(ppm2)).sum()) if len(ppm2) else 0)
    b["dup"] = b["id"].isin(seen) & (b.in_main | b.in_worst)
    qc["exposed_already_counted_in_earlier_area"] = int(b["dup"].sum())
    seen |= set(b.loc[b.in_worst, "id"])
    munis = municipalities(bbox); qc["municipalities"] = len(munis)
    sites = capacity(osm_sites(bbox, qc), b, qc)
    sites["in_main"], sites["in_worst"] = sites.intersects(fl["main"]), sites.intersects(fl["worst"])
    # share of each site under water (a campus whose car park touches the edge is not "flooded" like a submerged one)
    poly_area = sites.area.where(sites.area > 0)
    sites["share_worst"] = (sites.intersection(fl["worst"]).area / poly_area).fillna(sites["in_worst"].astype(float)).round(2)
    # "not mapped" is not "safe": a shelter must also be dry in the EFAS 100-year model, outside the satellite AOIs too
    rp = sites.representative_point().to_crs(4326)
    sites["in_efas100"] = sample(*efas_depth(100, bbox), pd.DataFrame({"lon": rp.x.values, "lat": rp.y.values})) > EFAS_THR
    sites["muni"] = assign_muni(gpd.GeoDataFrame(geometry=sites.centroid, crs=M), munis)
    is_shelter_type = sites["cat"].isin(["school", "sports hall", "civic"])
    shel = sites[is_shelter_type & ~sites["in_worst"] & ~sites["in_efas100"] & (sites.gfa >= MIN_GFA)].copy()
    qc["usable_shelters"] = len(shel); qc["shelter_sites_flooded"] = int((is_shelter_type & sites.in_worst).sum())
    qc["shelter_sites_excluded_by_efas100_only"] = int((is_shelter_type & ~sites.in_worst & sites.in_efas100).sum())
    shelters_all.append(shel.assign(area=key, capacity_central=(shel.gfa * .5 / 4).round()))
    for _, r in sites[sites["cat"].isin(["hospital", "care home", "school"]) & sites.in_worst].iterrows():
        c = gpd.GeoSeries([r.geometry.centroid], crs=M).to_crs(4326).iloc[0]
        crit_rows.append(dict(area=key, municipality=r["muni"], type=r["cat"], name=r["name"] if isinstance(r["name"], str) else "(no name in OSM)",
                              osm_parts=int(r.parts), in_main_flood=bool(r.in_main), in_worst_flood=True,
                              share_of_site_flooded=float(r.share_worst), also_in_efas100=bool(r.in_efas100), lon=round(c.x, 5), lat=round(c.y, 5), source=source))
    bm = gpd.GeoDataFrame(b, geometry=gpd.points_from_xy(b.x, b.y), crs=M)
    bm["muni"] = assign_muni(bm, munis)
    for v in VARIANTS:
        e = bm[bm[f"in_{v}"] & ~bm["dup"]]
        row = dict(area=key, name=A["name"], source=source, variant=v, polygons=npoly[v], flood_km2=round(fl[v].area / 1e6, 2),
                   buildings=len(e), residential=int((e.use == 1).sum()), non_residential=int((e.use == 2).sum()),
                   people_2020=round(e.people.sum()), people_2025=round(e.people25.sum()))
        exp = e[e.people > 0][["people", "muni", "geometry"]]
        for sc, s in SCEN.items():
            al = allocate_maxflow(exp, shel, s, flows=(sc == "bus" and v == "worst"))   # best coordinated plan
            nf = allocate(exp, shel, s)                         # everyone goes to the nearest shelter with room
            if al.covered.sum() < nf.covered.sum() - max(1, 0.001 * exp.people.sum()):     # 0.1-person rounding tolerance
                pickle.dump((exp, shel, s), open(OUT / "debug_maxflow.pkl", "wb"))
                raise AssertionError(f"max-flow below greedy: bug ({al.covered.sum():.0f} < {nf.covered.sum():.0f}), case saved")
            row.update({f"{sc}_covered": round(al.covered.sum()), f"{sc}_no_reach": round(al.no_reach.sum()), f"{sc}_full": round(al.full.sum()),
                        f"{sc}_covered_nearest_first": round(nf.covered.sum())})
            if sc == "bus" and v == "worst" and len(al.attrs.get("flows", [])):
                fdf = al.attrs["flows"]
                pts = gpd.GeoSeries(shel.geometry.values, crs=M).representative_point().to_crs(4326)
                fdf = fdf.assign(municipality=exp["muni"].values[fdf.i.values],
                                 shelter=[n if isinstance(n, str) else f"Unnamed {c}" for n, c in
                                          zip(shel["name"].values[fdf.j.values], shel["cat"].values[fdf.j.values])],
                                 cat=shel["cat"].values[fdf.j.values], s_lon=pts.x.values[fdf.j.values].round(5),
                                 s_lat=pts.y.values[fdf.j.values].round(5),
                                 places=(shel["gfa"].values[fdf.j.values] * s["use"] / s["m2"]).round())
                agg = fdf.groupby(["municipality", "shelter", "cat", "s_lon", "s_lat", "places"], as_index=False).people.sum()
                bus_rows += agg.assign(area=key, people=agg.people.round(1)).to_dict("records")
            if sc == "central":
                g = al.groupby("muni")[["people", "covered", "no_reach", "full"]].sum().round()
                g2 = e.groupby("muni").agg(buildings=("id", "size"), people_2025=("people25", "sum")).round()
                for m, gr in g.join(g2, how="outer").fillna(0).iterrows():
                    muni_rows.append(dict(area=key, variant=v, municipality=m, **{k: int(x) for k, x in gr.items()}))
        row["critical_sites_in_flood"] = int((sites["cat"].isin(["hospital", "care home", "school"]) & sites[f"in_{v}"]).sum())
        summary.append(row); say({k: row[k] for k in ("variant", "flood_km2", "buildings", "people_2020", "people_2025", "central_covered", "central_no_reach", "central_full", "critical_sites_in_flood")})
    # EFAS proxy validation where we have observed EMS floods
    if key in ("ahr", "liege"):
        inside_aoi = shapely.contains_xy(aoi_union(cc, A["ems"]), b["x"].values, b["y"].values)
        bb, obs = b[inside_aoi], b.loc[inside_aoi, "in_worst"].values
        val = {}
        for rp in (10, 100, 500):
            wet = sample(*efas_depth(rp, bbox), bb) > EFAS_THR
            tp = int((wet & obs).sum())
            val[f"RP{rp}"] = dict(observed_flooded=int(obs.sum()), efas_flooded=int(wet.sum()), both=tp,
                                  recall=round(tp / max(1, obs.sum()), 2), precision=round(tp / max(1, wet.sum()), 2))
        validation[key] = val; say("  EFAS validation:", val)
    qc_all[key] = qc; say("  QC:", qc)
    for v in VARIANTS:
        gpd.GeoSeries([fl[v]], crs=M).simplify(15).to_crs(4326).to_file(OUT / f"flood_{key}_{v}.geojson", driver="GeoJSON")
    pickle.dump(dict(summary=summary[n0[0]:], muni=muni_rows[n0[1]:], crit=crit_rows[n0[2]:], shel=shelters_all[-1], qc=qc,
                     bus=bus_rows[n0[3]:],
                     val={key: validation[key]} if key in validation else {}, seen=set(b.loc[b.in_worst, "id"])), open(part, "wb"))

pd.DataFrame(summary).to_csv(OUT / "area_summary.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(muni_rows).sort_values(["variant", "people"], ascending=[True, False]).to_csv(OUT / "municipalities.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(crit_rows).to_csv(OUT / "critical_sites.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(bus_rows).to_csv(OUT / "bus_plan.csv", index=False, encoding="utf-8-sig")
gpd.GeoDataFrame(pd.concat(shelters_all, ignore_index=True), crs=M).to_crs(4326)[["area", "muni", "name", "cat", "gfa", "capacity_central", "geometry"]] \
    .to_file(OUT / "shelters.geojson", driver="GeoJSON")
json.dump(dict(qc=qc_all, efas_validation=validation, decisions=__doc__), open(OUT / "qc_and_validation.json", "w"), indent=2, default=str)
say("\nDONE ->", OUT)
