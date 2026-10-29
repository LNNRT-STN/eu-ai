import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

import core
import forecast
from core import about, fmt

s, communes, cells, sites, geo = core.load()
pri, flow = core.load_brief()
gauges, _, rain, _, err = core.outlook()
ref = forecast.refs()
SIDE = {"Liège": "BE", "Chaudfontaine": "BE", "Verviers": "BE", "Tabreux": "BE", "Rochefort": "BE", "Maastricht": "NL",
        "Roermond": "NL", "Venlo": "NL", "Wassenberg": "DE", "Eschweiler": "DE"}
DAY0 = pd.Timestamp("2021-07-12")  # the replay's "now": rivers still normal, the rain has not fallen yet
STEPS = {0: "Now", 1: "+24 h", 2: "+48 h", 3: "+72 h", 4: "+96 h"}

core.header("If July 2021 happens again",
            "The July 2021 river flows, replayed as if they start today. Each commune scores 0–10: higher acts sooner.")

c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
side = c1.segmented_control("Country", ["All", "BE", "NL", "DE"], default="All", required=True,
                            format_func={"All": "All", **core.COUNTRY}.get)
step = c2.segmented_control("Forecast time", list(STEPS), default=0, required=True, format_func=STEPS.get,
                            help="Daily river flow from the GloFAS model for 12–16 July 2021, played back as a forecast.")
day = DAY0 + pd.Timedelta(days=step)

# river status per point and day: 0 normal · 1 above 2-year flood · 2 above half of July 2021 · 3 at July 2021
lvl = pd.DataFrame({g: [sum(q >= x for x in (ref[g][0], ref[g][1] / 2, ref[g][1])) for q in flow[g]] for g in flow},
                   index=flow.index)
danger = lambda g: lvl.index[lvl[g] >= 2]
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
st.html(f"<div class='banner' style='--halo:{color}33'><i class='dot' style='background:{color}'></i><div>"
        f"<h2>{head}</h2><p>{detail.strip()}</p><small>Replay day {day:%a %d %b %Y} · training scenario, not a warning · "
        "Live outlook today: " + ("unavailable" if gauges is None else core.status(gauges, rain, err)[1].lower())
        + "</small></div></div>")
st.space("small")

p = pri if side == "All" else pri[pri.country == side]
ev = sites[(sites.role == "evacuate") & ((side == "All") | (sites.country == side))]
dry = sites[(sites.role == "shelter") & ((side == "All") | (sites.country == side))]
first = p[p.level == "Act first"]
core.facts([
    (fmt(len(first)), f"<strong>communes act first</strong> (score 7+): {', '.join(first.commune.head(3)) or 'none'}"
                      + ("…" if len(first) > 3 else "")),
    (about(p.people.sum()), f"<strong>people in the 100-year zone</strong>, across {fmt((p.people > 0).sum())} communes. "
                            "2021 reached further in places."),
    (fmt(len(ev)), "<strong>hospitals and care homes</strong> in or next to the zone. Slowest to evacuate."),
    ("–" if side == "DE" else fmt(len(dry)), "<strong>dry schools and town halls</strong> could take people. Capacity "
                                             "unknown." if side != "DE" else
     "<strong>dry sites unknown</strong>: OpenStreetMap has no schools or town halls here."),
], "Source · " + " · ".join(core.AS_OF[k] for k in ("zone", "obs", "osm")))
st.space("small")

# one selected commune, set from the map, the table or the picker
ids = list(p.lau_id)
if st.session_state.get("commune") not in ids:
    st.session_state.commune = None


def from_map():
    objs = [o for os_ in st.session_state.map.selection.objects.values() for o in os_]
    hit = [o.get("properties", o).get("lau_id") for o in objs]
    if hit and hit[0]:
        st.session_state.commune = hit[0]


def from_table():
    rows = st.session_state.table.selection.rows
    if rows:
        st.session_state.commune = st.session_state.table_ids[rows[0]]


left, right = st.columns([3, 2], gap="medium")
sel = p[p.lau_id == st.session_state.commune].iloc[0] if st.session_state.commune else None
with left:
    with st.popover("Map layers", icon=":material/layers:"):
        show_2021 = st.toggle("July 2021 satellite water", help="What the satellite saw, a floor: it missed most of the "
                                                                 "Vesdre valley and central Liège.")
        show_care = st.toggle("Care sites at risk", value=True)
        show_dry = st.toggle("Dry candidate sites")
        tall = st.toggle("3D: height = people at risk", help="Tilts the map and raises each commune by the number of "
                                                              "people in its flood zone.")
    g = pd.DataFrame([(k, la, lo, int(now[k]), flow.loc[day, k] / ref[k][1]) for k, (la, lo) in forecast.GAUGES.items()
                      if side == "All" or SIDE[k.split(" · ")[1]] == side], columns=["gauge", "lat", "lon", "lvl", "pct"])
    layers = [pdk.Layer("GeoJsonLayer", geo["rp100"], filled=True, stroked=False, get_fill_color=[0, 113, 227, 70])]
    if show_2021:
        layers.append(pdk.Layer("GeoJsonLayer", geo["flood"], filled=True, get_fill_color=[0, 60, 160, 150]))
    layers.append(pdk.Layer(
        "GeoJsonLayer", p.drop(columns=["lon", "lat"]).__geo_interface__, id="communes", pickable=True,
        auto_highlight=True, filled=True, stroked=True, get_fill_color="properties.fill", opacity=.75 if sel is None else .3,
        get_line_color=[255, 255, 255, 230], line_width_min_pixels=1, extruded=tall,
        get_elevation="properties.people * 0.25"))
    if sel is not None:
        mine = core.cell_communes().query("lau_id == @sel.lau_id").cell
        here = cells[(cells.lens == "rp100") & (cells.residents >= 1) & cells.cell.isin(mine)]
        layers.append(core.blocks(here, 235))
        layers.append(pdk.Layer("GeoJsonLayer", p[p.lau_id == sel.lau_id].drop(columns=["lon", "lat"]).__geo_interface__,
                                filled=False, stroked=True, get_line_color=[29, 29, 31], line_width_min_pixels=3))
    if show_care:
        layers.append(core.points(ev.assign(tip=[f"<b>{n}</b><br>{t} · {c}<br>2021: {f} · model: {z}" for n, t, c, f, z in
                                                 zip(ev.name, ev.type, ev.commune, ev.flood_2021, ev.model_zone)]),
                                  core.rgb(core.EVACUATE), 5))
    if show_dry:
        layers.append(core.points(dry.assign(tip=[f"<b>{n}</b><br>{t} · {c}" for n, t, c in
                                                  zip(dry.name, dry.type, dry.commune)]), core.rgb(core.SHELTER), 3, 1))
    layers.append(core.points(g.assign(fill=[core.rgb(forecast.LEVELS[l][1]) for l in g.lvl],
                                       tip=[f"<b>{r.gauge}</b><br>{forecast.LEVELS[r.lvl][0]} · {r.pct:.0%} of the "
                                            f"July 2021 peak" for r in g.itertuples()]), "fill", 8, 2))
    v = core.view(s, None if sel is None else (sel.lon, sel.lat))
    if sel is not None:
        v.zoom = 10.5
    if tall:
        v.pitch, v.bearing = 45, -12
    core.deck(layers, v, 540, on_select=from_map, selection_mode="single-object", key="map")
    core.legend("<b>Priority</b>" + "".join(core.swatch(c, lab) for lab, (c, _) in core.PRIORITY.items()),
                *(["<b>People in the flood zone per ~1 km block</b>" + "".join(core.swatch(h, lab) for _, lab, h in core.CLASSES)]
                  if sel is not None else []),
                "<b>River point</b>" + "".join(core.swatch(c, lab, True) for lab, c in forecast.LEVELS)
                + core.swatch("rgba(0,113,227,.35)", "100-year flood zone")
                + (core.swatch(core.EVACUATE, "Care site at risk", True) if show_care else "")
                + (core.swatch(core.SHELTER, "Dry candidate site", True) if show_dry else ""))

with right:
    picked = st.selectbox("Commune", [None, *ids], key="commune", placeholder="Click a commune on the map, or pick one",
                          format_func=lambda x: "Whole area" if x is None else
                          f"{p.set_index('lau_id').commune[x]} · {p.set_index('lau_id').score[x]}/10",
                          label_visibility="collapsed")
    if sel is None:
        core.group([(f"<span class='pill' style='background:{c};color:{'#1d1d1f' if lab in ('Watch', 'Low') else '#fff'}'>"
                     f"{lab}</span>", what, f"{fmt((p.level == lab).sum())}") for lab, (c, what) in core.PRIORITY.items()],
                   "Communes per level")
        st.space("small")
        with st.expander("How the score works"):
            core.group([
                ("<b>People in the flood zone</b>", "50+: 1 · 500+: 2 · 2,000+: 3 · 10,000+: 4", "up to 4"),
                ("<b>Share of the commune</b>", "5 %+ of residents: 1 · 20 %+: 2", "up to 2"),
                ("<b>Flooded in July 2021</b>", "Homes in the mapped water, or a known flood the satellite missed", "2"),
                ("<b>Care sites at risk</b>", "1–2 hospitals or care homes: 1 · 3+: 2", "up to 2"),
            ], foot="The team's thresholds, simple enough to redo by hand. Not an official standard.")
    else:
        c, what = core.PRIORITY[sel.level]
        ink = "#1d1d1f" if sel.level in ("Watch", "Low") else "#fff"
        st.html(f"<div class='group'><div class='row'><div class='t'><b style='font-size:1.15rem'>{sel.commune}</b>"
                f"<span>{core.COUNTRY[sel.country]} · {fmt(sel.population)} residents</span></div><div class='v'>"
                f"<div class='score'>{sel.score}<small>/10</small></div><span class='pill' style='background:{c};"
                f"color:{ink}'>{sel.level}</span></div></div><div class='row'><div class='t'><b>Next step</b><span>{what}"
                "</span></div></div></div>")
        st.space("small")
        core.group([
            ("<b>People in the flood zone</b>", f"≈ {about(sel.people)}", f"+{sel.pts_people}"),
            ("<b>Share of the commune</b>", f"{sel.share:.0%} of residents", f"+{sel.pts_share}"),
            ("<b>Flooded in July 2021</b>", "Missed by the satellite, flooded in reality" if sel.missed else
             f"≈ {about(sel.people_2021)} people in the mapped water" if sel.hit_2021 else "Not reached by mapped water",
             f"+{sel.pts_2021}"),
            ("<b>Care sites at risk</b>", f"{sel.care} hospitals or care homes", f"+{sel.pts_care}"),
        ], "Why this score")
        st.space("small")
        st.space("small")
        top = here.sort_values("residents", ascending=False)
        n_half = int((top.residents.cumsum() < top.residents.sum() / 2).sum()) + 1 if len(top) else 0
        lens = communes[communes.lau_id == sel.lau_id].set_index("lens")
        val = lambda l, c: about(lens.loc[l, c]) if l in lens.index else "0"
        reg = next((f["properties"] for f in geo.get("regions", {}).get("features", [])
                    if f["properties"]["lau_id"] == sel.lau_id), None)
        rows = [("<b>Where the people are</b>", f"Half of them in {n_half} of {len(top)} blocks of ~1 km, marked on the map"
                 if len(top) else "No block with residents in the 100-year zone", ""),
                ("<b>100-year zone · model</b>", f"{val('rp100', 'buildings')} buildings", f"≈ {val('rp100', 'residents')}"),
                ("<b>July 2021 · satellite</b>", f"{val('obs', 'buildings')} buildings"
                 + (" · flooded, but missed by the satellite" if sel.missed else ""), f"≈ {val('obs', 'residents')}")]
        if reg and reg["graded"]:
            rows.append(("<b>July 2021 damage</b>", "Copernicus EMS grading of buildings",
                         f"{reg['gra_destroyed']:.0f} destroyed · {reg['gra_damaged']:.0f} damaged"))
        core.group(rows, "Residents in the water, in detail", core.AS_OF["zone"] + " · " + core.AS_OF["obs"])
        at_risk = sites[(sites.role == "evacuate") & (sites.lau_id == sel.lau_id)]
        if len(at_risk):
            st.space("small")
            core.group([(f"<b>{n}</b>", f"{ty} · July 2021: {f.lower()} · model: {z}", "") for n, ty, f, z in
                        zip(at_risk.name, at_risk.type, at_risk.flood_2021, at_risk.model_zone)], "Care sites to evacuate first")
        st.space("small")
        sh = sites[sites.role == "shelter"]
        sh = sh.assign(d=core.km(sel.lon, sel.lat, sh.lon, sh.lat)).nsmallest(5, "d")
        shelter = ("Unknown: no OSM sites on the German side" if pd.isna(sel.dry_5km) else
                   f"{fmt(sel.dry_5km)} sites, ≈ {about(sel.per_site)} people per site" if sel.dry_5km else
                   "None within 5 km: look further or across the border")
        core.group([("<b>Dry candidate sites within 5 km</b>", shelter, "")]
                   + [(f"{n}", f"{ty} · {c}", f"{d:.1f} km") for n, ty, c, d in zip(sh.name, sh.type, sh.commune, sh.d)],
                   "Where people could go · nearest dry sites",
                   "Schools and town halls that stayed dry in 2021, distance from the commune centre. Confirm capacity "
                   "with the commune.")
        if sel.lau_id in set(communes[communes.lens == "rp100"].lau_id) and st.button(
                "Show dry sites nearby", icon=":material/home_health:", type="primary", width="stretch"):
            st.session_state.near = sel.lau_id
            st.switch_page("views/shelters.py")

st.space("medium")
st.html("<div class='gh'>All communes, highest priority first · select a row to see why</div>")
tab = p.drop(columns="geometry").sort_values(["score", "people"], ascending=False).reset_index(drop=True)
st.session_state.table_ids = list(tab.lau_id)
show = tab.assign(country=tab.country.map(core.COUNTRY))
st.dataframe(show[["commune", "country", "level", "score", "people", "care", "dry_5km", "per_site"]],
             hide_index=True, height=380, on_select=from_table, selection_mode="single-row", key="table", column_config={
                 "commune": "Commune", "country": st.column_config.TextColumn("Country", width="small"),
                 "level": st.column_config.TextColumn("Priority", width="small"),
                 "score": st.column_config.ProgressColumn("Score", format="%d / 10", min_value=0, max_value=10, width="small"),
                 "people": st.column_config.NumberColumn("People in flood zone", format="localized",
                                                         help="Residents in the EFAS 100-year zone. Order of magnitude."),
                 "care": st.column_config.NumberColumn("Care sites", width="small", help="Hospitals and care homes at risk"),
                 "dry_5km": st.column_config.NumberColumn("Dry sites ≤ 5 km", format="%d",
                                                          help="Empty on the German side: no OSM data."),
                 "per_site": st.column_config.NumberColumn("People per dry site", format="localized",
                                                           help="People in the flood zone ÷ dry candidate sites within "
                                                                "5 km. High = shelter shortfall: look further or across "
                                                                "the border.")})
st.download_button("Download table", tab.to_csv(index=False), "priority_by_commune.csv", icon=":material/download:",
                    type="tertiary")

st.space("medium")
st.html("<div class='gh'>When each river peaks · % of its own July 2021 peak</div>")
order = ["Lesse · Rochefort", "Ourthe · Tabreux", "Vesdre · Verviers", "Vesdre · Chaudfontaine", "Meuse · Liège",
         "Meuse · Maastricht", "Meuse · Roermond", "Meuse · Venlo", "Inde · Eschweiler", "Rur · Wassenberg"]
heat = pd.DataFrame([(t, g, flow.loc[t, g] / ref[g][1], forecast.LEVELS[lvl.loc[t, g]][0]) for t in flow.index
                     for g in order], columns=["day", "gauge", "pct", "status"])
heat = heat[(heat.day >= DAY0) & (heat.day <= DAY0 + pd.Timedelta(days=5))]
heat["d"] = heat.day.dt.strftime("%a %d")  # plain labels: a year-less time unit would print 2012 weekdays
x = alt.X("d:O", sort=list(heat.d.unique()), title=None, axis=alt.Axis(labelAngle=0, orient="top"))
y = alt.Y("gauge:N", sort=order, title=None, axis=alt.Axis(labelLimit=220))
base = alt.Chart(heat).encode(x=x, y=y)
st.altair_chart(alt.layer(
    base.mark_rect(stroke="#fff", strokeWidth=2, cornerRadius=4).encode(
        color=alt.Color("status:N", scale=alt.Scale(domain=[l for l, _ in forecast.LEVELS],
                                                    range=[c for _, c in forecast.LEVELS]), legend=None),
        tooltip=[alt.Tooltip("gauge:N", title="River"), alt.Tooltip("day:T", format="%a %d %b"),
                 alt.Tooltip("status:N"), alt.Tooltip("pct:Q", format=".0%", title="Of July 2021 peak")]),
    base.mark_text(fontSize=11).encode(text=alt.Text("pct:Q", format=".0%"),
                                       color=alt.condition("datum.pct >= 0.5", alt.value("#fff"), alt.value("#1d1d1f"))),
    alt.Chart(pd.DataFrame({"d": [f"{day:%a %d}"]})).mark_rect(fill=None, stroke="#1d1d1f", strokeWidth=2).encode(
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
    ("<b>Your own focal points</b>", "Add each agency's contact person, phone and radio channel before an event", "To fill"),
], "Who issues the real warnings", "A training and planning tool. Check the official warning for your river before "
                                   "acting.")
