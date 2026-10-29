import altair as alt
import pandas as pd
import streamlit as st

import core

core.style()  # the older analyst pages keep their custom look; the main pages use the theme only
import forecast
import live
from core import about, fmt

d = core.load()
rank, sites, shelters, areas = d["rank"], d["sites"], d["shelters"], d["areas"]
flow = core.load_replay()
gauges, _, rain, _, err = core.outlook()
ref = forecast.refs()
SIDE = {"Liège": "BE", "Chaudfontaine": "BE", "Verviers": "BE", "Tabreux": "BE", "Rochefort": "BE", "Maastricht": "NL",
        "Roermond": "NL", "Venlo": "NL", "Wassenberg": "DE", "Eschweiler": "DE"}
DAY0 = pd.Timestamp("2021-07-12")  # the replay's "now": rivers still normal, the rain has not fallen yet
STEPS = {0: "Now", 1: "+24 h", 2: "+48 h", 3: "+72 h", 4: "+96 h"}

core.header("If July 2021 happens again",
            "The July 2021 river flows, replayed as if they start today. Each municipality hit in 2021 shows how many of "
            "its people would find no shelter place within walking distance.")

c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
side = c1.segmented_control("Country", ["All", "BE", "NL", "DE"], default="All", required=True,
                            format_func={"All": "All", **core.COUNTRY}.get)
step = c2.segmented_control("Forecast time", list(STEPS), default=0, required=True, format_func=STEPS.get,
                            help="Daily river flow from the GloFAS model for 12–16 July 2021, played back as a drill from "
                            f"{live.drill(DAY0):%a %d %b}.")
day = DAY0 + pd.Timedelta(days=step)

# river status per point and day: 0 normal · 1 above 2-year flood · 2 above half of July 2021 · 3 at July 2021
lvl = pd.DataFrame({g: [sum(q >= x for x in (ref[g][0], ref[g][1] / 2, ref[g][1])) for q in flow[g]] for g in flow},
                   index=flow.index)
now = lvl.loc[day]
place = lambda gs: ", ".join(g.split(" · ")[1] for g in gs)  # towns only: the river timeline below names each river
high = [g for g in now.index if now[g] >= 2]
peak = {g: flow[g].idxmax() for g in flow}
soon = [g for g in now.index if peak[g] > day]
if high:
    head = f"{len(high)} of {len(now)} river points are above half the July 2021 peak"
    detail = f"Now: {place(high)}."
else:
    head = ("All rivers are normal now, but a flood like July 2021 is forecast" if soon else
            "The water is falling: all river points are back below half the July 2021 peak")
    detail = ""
if soon:
    by = pd.Series(soon, index=[int((peak[g] - day).days * 24) for g in soon]).groupby(level=0).agg(list)
    detail += " " + " ".join(f"Peak in {h} h: {place(gs)}." for h, gs in by.items())
color = forecast.LEVELS[3 if soon and not high else int(now.max())][1] if now.max() or soon else core.SHELTER
st.html(f"<div class='banner' style='--c:{color}'><i class='dot'></i><div>"
        f"<h2>{head}</h2><p>{detail.strip()}</p><small>Drill day {live.drill(day):%a %d %b %Y} (the flows of {day:%d %b %Y}) · training scenario, not a warning · "
        "River points cover the Meuse basin only, not the Ahr or Erft · Live outlook today: "
        + ("unavailable" if gauges is None else core.status(gauges, rain, err)[1].lower()) + "</small></div></div>")
st.space("small")

mine = lambda df: df if side == "All" else df[df.country == side]
p, ev, dry = mine(rank), mine(sites[sites.in_worst_flood & (sites.type != "school")]), mine(shelters)
obs, mod = p[~p.modelled], p[p.modelled]
plus = lambda c: f" Modelled Vesdre: ≈ {about(mod[c].sum())} more, kept apart." if len(mod) else ""
core.facts([
    (about(obs.people.sum()), f"<strong>people in the July 2021 water</strong> across {fmt(len(obs))} municipalities."
                              + plus("people"), core.WATER),
    (about(obs.no_shelter.sum()), f"<strong>without a shelter place</strong> within a 1.5 km walk: "
                                  f"{about(obs.no_reach.sum())} too far, {about(obs.full.sum())} because shelters are "
                                  f"full." + plus("no_shelter"), core.GAP["No shelter in reach"][0], True),
    (fmt(len(ev)), "<strong>hospitals and care homes</strong> in the 2021 water. Slowest to evacuate.",
     core.EVACUATE, True),
    (fmt(len(dry)), f"<strong>dry schools, sports halls and civic buildings</strong>, ≈ {about(dry.capacity_central.sum())}"
                    " places in all. Candidates, not official.", core.SHELTER, True),
], "Source · " + " · ".join(core.AS_OF[k] for k in ("obs", "model", "osm")))
st.space("small")

# one selected municipality, set from the map, the table or the picker; keyed on rank, as a name can sit in two areas
ids = list(p["rank"])
label = dict(zip(rank["rank"], rank.municipality + rank.modelled.map({True: " · modelled", False: ""})))
if st.session_state.get("commune") not in ids:
    st.session_state.commune = None


def from_map():
    objs = [o for os_ in st.session_state.map.selection.objects.values() for o in os_]
    hit = [o.get("properties", o).get("rank") for o in objs]
    if hit and hit[0] is not None:
        st.session_state.commune = hit[0]


def from_table():
    rows = st.session_state.table.selection.rows
    if rows:
        st.session_state.commune = st.session_state.table_ids[rows[0]]


left, right = st.columns([3, 2], gap="medium")
sel = p[p["rank"] == st.session_state.commune].iloc[0] if st.session_state.commune is not None else None
with left:
    with st.popover("Map layers", icon=":material/layers:"):
        show_water = st.toggle("July 2021 water", value=True, help="All satellite passes. Grey: the Vesdre valley, "
                                                                  "missed by the satellite, drawn from the EFAS model.")
        show_care = st.toggle("Care sites in the water", value=True)
        show_dry = st.toggle("Dry candidate sites")
    g = pd.DataFrame([(k, la, lo, int(now[k]), flow.loc[day, k] / ref[k][1]) for k, (la, lo) in forecast.GAUGES.items()
                      if side == "All" or SIDE[k.split(" · ")[1]] == side], columns=["gauge", "lat", "lon", "lvl", "pct"])
    pick = None if sel is None else sel.municipality
    layers = [core.regions(p.assign(
        fill=[core.rgb(core.GAP[x][0], 150 if m == pick else 40 if pick else 85) for x, m in zip(p.gap, p.municipality)],
        tip=[f"{m} · {x}\n≈ {about(n)} people in the water" + (" (modelled)" if mo else "")
             + f"\n≈ {about(ns)} without a shelter place\nClick for details" for m, x, n, ns, mo in
             zip(p.municipality, p.gap, p.people, p.no_shelter, p.modelled)]), "fill", pick)]
    layers += core.water("worst") if show_water else []
    if show_dry:
        layers.append(core.points(dry.assign(tip=[f"{n}\n{t} · {m}\n≈ {c:,.0f} places" for n, t, m, c in
                                                  zip(dry.name, dry.type, dry.muni, dry.capacity_central)]),
                                  core.rgb(core.SHELTER), 3, 1))
    layers.append(core.towns(p.assign(
        fill=[core.rgb(core.GAP[x][0], 215 if sel is None or r == sel["rank"] else 90) for x, r in zip(p.gap, p["rank"])],
        tip=[f"{m} · {x}\n≈ {about(n)} people in the water" + (" (modelled)" if mo else "")
             + f"\n≈ {about(ns)} without a shelter place" for m, x, n, ns, mo in
             zip(p.municipality, p.gap, p.people, p.no_shelter, p.modelled)]), "people", "fill", 18))
    if show_care:
        layers.append(core.points(ev.assign(tip=[f"{n}\n{t} · {m}\n{s:.0%} of the site in the water"
                                                 for n, t, m, s in zip(ev.name, ev.type, ev.municipality,
                                                                       ev.share_of_site_flooded)]),
                                  core.rgb(core.EVACUATE), 5))
    layers.append(core.points(g.assign(fill=[core.rgb(forecast.LEVELS[l][1]) for l in g.lvl],
                                       tip=[f"{r.gauge}\n{forecast.LEVELS[r.lvl][0]} · {r.pct:.0%} of the "
                                            f"July 2021 peak" for r in g.itertuples()]), "fill", 8, 2))
    v = core.view(core.bbox(), None if sel is None else (sel.lon, sel.lat), 11)
    core.deck(layers, v, 540, on_select=from_map, selection_mode="single-object", key="map")
    core.legend("<b>Municipality: area coloured by shelter gap, circle size = people in the water · click for details</b>"
                + "".join(core.swatch(c, lab, True) for lab, (c, _) in core.GAP.items()),
                "<b>River point</b>" + "".join(core.swatch(c, lab, True) for lab, c in forecast.LEVELS)
                + (core.swatch(core.WATER, "2021 water") + core.swatch(core.MODEL, "Vesdre, modelled") if show_water else "")
                + (core.swatch(core.EVACUATE, "Care site in the water", True) if show_care else "")
                + (core.swatch(core.SHELTER, "Dry candidate site", True) if show_dry else ""))

with right:
    picked = st.selectbox("Municipality", [None, *ids], key="commune",
                          placeholder="Click a municipality on the map, or pick one",
                          format_func=lambda x: "Whole area" if x is None else
                          f"{label[x]} · ≈ {about(p.set_index('rank').no_shelter[x])} without shelter",
                          label_visibility="collapsed")
    if sel is None:
        core.group([(core.chip(lab, c), what, f"{fmt((p.gap == lab).sum())}") for lab, (c, what) in core.GAP.items()],
                   "Municipalities per shelter gap")
        st.space("small")
        with st.expander("How the gap is worked out"):
            core.group([
                ("<b>Who needs a place</b>", "Residents of homes inside the July 2021 water, all satellite passes", ""),
                ("<b>Where they can go</b>", "Schools, sports halls and civic buildings that stayed dry, ≥ 200 m² floor",
                 ""),
                ("<b>How many fit</b>", "Floor × 50 % usable ÷ 4 m² per person", ""),
                ("<b>How far</b>", "1.5 km straight line, the best possible plan for the whole area", ""),
            ], foot="Central assumptions. The Shelter plan page shows the low and high cases.")
    else:
        c, what = core.GAP[sel.gap]
        st.html(f"<div class='group'><div class='row'><div class='t'><b style='font-size:1.15rem'>{sel.municipality}</b>"
                f"<span>{core.COUNTRY[sel.country]} · rank {sel['rank']} of {len(rank)}"
                + (" · modelled, the satellite missed this valley" if sel.modelled else "")
                + f"</span></div><div class='v'><div class='score'>{about(sel.no_shelter)}<small> without</small></div>"
                f"{core.chip(sel.gap, c)}</div></div><div class='row'><div class='t'><b>Next step</b><span>{what}"
                "</span></div></div></div>")
        st.space("small")
        o = core.outlines()[sel.municipality]["properties"]
        core.group([
            ("<b>Residents</b>", f"Eurostat 2021 · {o['area_km2']:,.0f} km²", fmt(o["population_2021"])),
            ("<b>People in the water</b>", f"{sel.people / o['population_2021']:.0%} of residents · all satellite passes" + (" · EFAS 100-year model" if sel.modelled else ""),
             f"≈ {about(sel.people)}"),
            ("<b>First pass only</b>", "Lower bound", "–" if pd.isna(sel.people_first_pass) else
             f"≈ {about(sel.people_first_pass)}"),
            ("<b>Shelter place in walking reach</b>", "Best possible plan", f"≈ {about(sel.covered)}"),
            ("<b>No shelter within 1.5 km</b>", "Too far to walk", f"≈ {about(sel.no_reach)}"),
            ("<b>Shelters in reach full</b>", "Need more or larger sites", f"≈ {about(sel.full)}"),
        ], "People in the water, in detail", core.AS_OF["model" if sel.modelled else "obs"])
        at_risk = sites[(sites.municipality == sel.municipality) & (sites.area == sel.area)]
        if len(at_risk):
            st.space("small")
            core.group([(f"<b>{n}</b>", f"{ty} · {s:.0%} of the site in the water"
                         + ("" if w else " · not in the satellite water"), "") for n, ty, s, w in
                        zip(at_risk.name, at_risk.type, at_risk.share_of_site_flooded, at_risk.in_worst_flood)],
                       "Care sites and schools in the water")
        st.space("small")
        sh = shelters.assign(d=core.km(sel.lon, sel.lat, shelters.lon, shelters.lat)).nsmallest(5, "d")
        core.group([(f"{n}", f"{ty} · {m} · ≈ {c:,.0f} places", f"{k:.1f} km") for n, ty, m, c, k in
                    zip(sh.name, sh.type, sh.muni, sh.capacity_central, sh.d)],
                   "Where people could go · nearest dry sites",
                   "Straight-line distance from the municipality centre. Confirm capacity and access with the commune.")
        if st.button("Show dry sites nearby", icon=":material/home_health:", type="primary", width="stretch"):
            st.session_state.near = sel.municipality
            st.switch_page("views/shelters.py")

st.space("medium")
st.html("<div class='gh'>All municipalities, most people without a shelter place first · select a row to see why</div>")
tab = p.sort_values("rank").reset_index(drop=True)
st.session_state.table_ids = list(tab["rank"])
show = tab.assign(country=tab.country.map(core.COUNTRY), basis=tab.modelled.map({True: "Modelled", False: "Observed"}))
st.dataframe(core.paint(show[["municipality", "country", "gap", "no_shelter", "people", "basis",
                              "hospitals_carehomes_flooded", "schools_flooded"]], "gap",
                        {k: c for k, (c, _) in core.GAP.items()}),
             hide_index=True, height=380, on_select=from_table, selection_mode="single-row", key="table", column_config={
                 "municipality": "Municipality", "country": st.column_config.TextColumn("Country", width="small"),
                 "gap": st.column_config.TextColumn("Shelter gap", width="small"),
                 "no_shelter": st.column_config.ProgressColumn("Without a place", format="localized", min_value=0,
                                                               max_value=int(tab.no_shelter.max() or 1)),
                 "people": st.column_config.NumberColumn("People in the water", format="localized",
                                                         help="All satellite passes. Order of magnitude."),
                 "basis": st.column_config.TextColumn("Water", width="small",
                                                      help="Modelled: Vesdre valley, EFAS 100-year zone. Do not add to "
                                                           "observed totals."),
                 "hospitals_carehomes_flooded": st.column_config.NumberColumn("Care sites", width="small",
                                                                              help="Hospitals and care homes flooded"),
                 "schools_flooded": st.column_config.NumberColumn("Schools", width="small", help="Schools flooded")})
st.download_button("Download table", tab.to_csv(index=False), "shelter_gap_by_municipality.csv",
                   icon=":material/download:", type="tertiary")

st.space("medium")
st.html("<div class='gh'>When each river peaks · % of its own July 2021 peak</div>")
order = ["Lesse · Rochefort", "Ourthe · Tabreux", "Vesdre · Verviers", "Vesdre · Chaudfontaine", "Meuse · Liège",
         "Meuse · Maastricht", "Meuse · Roermond", "Meuse · Venlo", "Inde · Eschweiler", "Rur · Wassenberg"]
heat = pd.DataFrame([(t, g, flow.loc[t, g] / ref[g][1], *forecast.LEVELS[lvl.loc[t, g]]) for t in flow.index
                     for g in order], columns=["day", "gauge", "pct", "status", "fill"])
heat["ink"] = heat.fill.map(core.ink)
heat = heat[(heat.day >= DAY0) & (heat.day <= DAY0 + pd.Timedelta(days=5))]
heat["d"] = heat.day.map(live.drill).dt.strftime("%a %d")  # plain labels: a year-less time unit would print 2012 weekdays
x = alt.X("d:O", sort=list(heat.d.unique()), title=None, axis=alt.Axis(labelAngle=0, orient="top"))
y = alt.Y("gauge:N", sort=order, title=None, axis=alt.Axis(labelLimit=220))
base = alt.Chart(heat).encode(x=x, y=y)
st.altair_chart(alt.layer(
    base.mark_rect(stroke="#fff", strokeWidth=2, cornerRadius=4).encode(
        color=alt.Color("status:N", scale=alt.Scale(domain=[l for l, _ in forecast.LEVELS],
                                                    range=[c for _, c in forecast.LEVELS]), legend=None),
        tooltip=[alt.Tooltip("gauge:N", title="River"), alt.Tooltip("day:T", format="%d %b %Y", title="July 2021 flow of"),
                 alt.Tooltip("status:N"), alt.Tooltip("pct:Q", format=".0%", title="Of July 2021 peak")]),
    base.mark_text(fontSize=11).encode(text=alt.Text("pct:Q", format=".0%"),
                                       color=alt.Color("ink:N", scale=None)),
    alt.Chart(pd.DataFrame({"d": [f"{live.drill(day):%a %d}"]})).mark_rect(fill=None, stroke="#1d1d1f", strokeWidth=2).encode(
        x=alt.X("d:O", sort=list(heat.d.unique()))),
).properties(height=330, background="#ffffff", padding={"left": 12, "right": 12, "top": 8, "bottom": 8}).configure_view(stroke=None)
 .configure_axis(domain=False, ticks=False, labelColor="#1d1d1f", labelFontSize=12), width="stretch")
lag = (flow["Meuse · Venlo"].idxmax() - flow["Vesdre · Chaudfontaine"].idxmax()).days
st.html(f"<p class='foot'>Top to bottom follows the water: Ardennes tributaries peak first, Dutch Limburg about {lag} "
        f"day{'s' if lag != 1 else ''} later. That gap is the downstream lead time. Black frame: the forecast time above.</p>")
core.legend("".join(core.swatch(c, lab) for lab, c in forecast.LEVELS))
core.asof("replay")

st.space("medium")
core.group([
    ("<b>Emergency services</b>", "BE · NL · DE", "112"),
    ("<b>Belgium · Wallonia</b>", "SPW river levels and flood warnings, hydrometrie.wallonie.be · FR, DE", "Official"),
    ("<b>Netherlands</b>", "Rijkswaterstaat water levels, waterinfo.rws.nl · NL", "Official"),
    ("<b>Germany · North Rhine-Westphalia</b>", "State flood portal, hochwasserportal.nrw · DE", "Official"),
    ("<b>Germany · Rhineland-Palatinate (Ahr)</b>", "State flood warning service, hochwasser.rlp.de · DE", "Official"),
    ("<b>Your own focal points</b>", "Add each agency's contact person, phone and radio channel before an event", "To fill"),
], "Who issues the real warnings", "A training and planning tool. Check the official warning for your river before "
                                   "acting.")
