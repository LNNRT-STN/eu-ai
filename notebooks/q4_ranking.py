"""Q4: where do we still stand exposed? Transparent ranking per municipality, no hidden weights.
Rank = residents with no shelter (central assumptions) in the 2021 flood as seen by ALL satellite passes (variant
"worst" in the pipeline). It is the headline because it is closer to the official 2021 figures (Ahr: 7,202 buildings
vs ">9,000"; the first pass alone gives 3,300). The first pass ("main") is kept as a lower bound.
Shown next to the rank, never blended in: why (too far / shelter full), vulnerable sites flooded, data source
(observed vs modelled), Q2 evidence (pending).
Run from eu-ai/ after pipeline.py:  .venv/Scripts/python.exe -I notebooks/q4_ranking.py
"""
import json
import pandas as pd

D = "outputs/data/"
m = pd.read_csv(D + "municipalities.csv"); s = pd.read_csv(D + "area_summary.csv"); c = pd.read_csv(D + "critical_sites.csv")
MODELLED = {"vesdre"}

allp = m[m.variant == "worst"].copy()
allp["no_shelter"] = allp.no_reach + allp.full
first = m[m.variant == "main"].assign(no_shelter_first_pass=lambda d: d.no_reach + d.full)[
    ["area", "municipality", "people", "no_shelter_first_pass"]].rename(columns={"people": "people_first_pass"})
r = allp.merge(first, on=["area", "municipality"], how="left")
r["why"] = r.apply(lambda x: "shelters too far" if x.no_reach > x.full else ("shelters full" if x.full > 0 else "-"), axis=1)
# vulnerable sites (hospital / care home) and schools with at least 5% of the site under water, worst-case flood
cc = c[c.share_of_site_flooded >= 0.05]
vul = cc[cc.type.isin(["hospital", "care home"])].groupby(["area", "municipality"]).name.apply(lambda s: "; ".join(sorted(s)))
nvul = cc[cc.type.isin(["hospital", "care home"])].groupby(["area", "municipality"]).size()
nsch = cc[cc.type == "school"].groupby(["area", "municipality"]).size()
r = r.set_index(["area", "municipality"])
r["hospitals_carehomes_flooded"] = nvul.reindex(r.index).fillna(0).astype(int)
r["schools_flooded"] = nsch.reindex(r.index).fillna(0).astype(int)
r["vulnerable_sites"] = vul.reindex(r.index).fillna("")
r = r.reset_index()
r["source"] = r.area.map(lambda a: "MODELLED (EFAS 100-yr)" if a in MODELLED else "observed (EMS 2021)")
r["q2_evidence"] = "pending (researchers)"
r = r[(r.people >= 1) & (r.municipality != "(outside mapped municipalities)")]
r = r.sort_values(["no_shelter", "hospitals_carehomes_flooded"], ascending=False).reset_index(drop=True)
r.insert(0, "rank", r.index + 1)
cols = ["rank", "municipality", "area", "source", "people", "covered", "no_shelter", "why", "no_reach", "full",
        "people_first_pass", "no_shelter_first_pass", "hospitals_carehomes_flooded", "schools_flooded", "vulnerable_sites", "q2_evidence"]
r[cols].to_csv(D + "q4_ranking.csv", index=False, encoding="utf-8-sig")

# municipality centroids (Eurostat GISCO LAU 2021) so the app can order towns along each river
import geopandas as gpd
lau = gpd.read_file("cache/gisco/lau_be_nl_de.gpkg")
lau["municipality"] = lau["LAU_NAME"] + " (" + lau["CNTR_CODE"] + ")"
lau["pt"] = lau.geometry.representative_point()
_flood = {a: gpd.read_file(D + f"flood_{a}_worst.geojson").to_crs(lau.crs).union_all().centroid for a in m.area.unique()}
def centroid(area, name):
    """Names repeat across Germany (several 'Kall'): take the polygon nearest this area's flood."""
    c = lau[lau.municipality == name]
    if c.empty: return (None, None)
    p = gpd.GeoSeries([c.loc[c.pt.distance(_flood[area]).idxmin(), "pt"]], crs=lau.crs).to_crs(4326).iloc[0]
    return (round(p.x, 4), round(p.y, 4))
_cache = {}
def lonlat(area, name):
    if (area, name) not in _cache: _cache[(area, name)] = centroid(area, name)
    return _cache[(area, name)]
r["lon"] = [lonlat(a, n)[0] for a, n in zip(r.area, r.municipality)]
r["lat"] = [lonlat(a, n)[1] for a, n in zip(r.area, r.municipality)]
r[cols + ["lon", "lat"]].to_csv(D + "q4_ranking.csv", index=False, encoding="utf-8-sig")

# per-variant town table (sheltered / too far / full) for the app, central assumptions
m2 = m.copy(); m2["no_shelter"] = m2.no_reach + m2.full
m2 = m2[(m2.people >= 1) & (m2.municipality != "(outside mapped municipalities)")]
m2["lon"] = [lonlat(a, n)[0] for a, n in zip(m2.area, m2.municipality)]
m2["lat"] = [lonlat(a, n)[1] for a, n in zip(m2.area, m2.municipality)]
m2["source"] = m2.area.map(lambda a: "modelled" if a in MODELLED else "observed")
m2.to_csv(D + "app_towns.csv", index=False, encoding="utf-8-sig")

# headline numbers per flood variant, central assumptions; observed and modelled kept apart
def tot(d): return dict(people=int(d.people_2020.sum()), sheltered=int(d.central_covered.sum()),
                        no_shelter=int((d.central_no_reach + d.central_full).sum()), too_far=int(d.central_no_reach.sum()), full=int(d.central_full.sum()),
                        no_shelter_range=[int(d.people_2020.sum() - d.high_covered.sum()), int(d.people_2020.sum() - d.low_covered.sum())],
                        coordination_gain=int((d.central_covered - d.central_covered_nearest_first).sum()))
def sites(v):
    flag = "in_worst_flood" if v == "worst" else "in_main_flood"
    x = cc[cc[flag].astype(bool)]
    vul = x[x.type.isin(["hospital", "care home"])]
    by_town = vul.groupby("municipality").size().sort_values(ascending=False)
    return dict(vulnerable=int(len(vul)), schools=int((x.type == "school").sum()),
                top_town=by_town.index[0] if len(by_town) else None, top_town_count=int(by_town.iloc[0]) if len(by_town) else 0)
head = {v: dict(observed=tot(s[(s.variant == v) & ~s.area.isin(MODELLED)]),
                modelled_vesdre=tot(s[(s.variant == v) & s.area.isin(MODELLED)]), sites=sites(v)) for v in ("main", "worst")}
head["top10"] = r[cols[:10]].head(10).to_dict("records")
json.dump(head, open(D + "q4_headline.json", "w"), indent=2, default=str)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(r[["rank", "municipality", "source", "people", "no_shelter", "why", "no_shelter_first_pass", "hospitals_carehomes_flooded", "schools_flooded"]].head(15).to_string(index=False))
print(json.dumps({k: v for k, v in head.items() if k != "top10"}, indent=1))
print(r[r.hospitals_carehomes_flooded > 0][["municipality", "vulnerable_sites"]].to_string(index=False))
