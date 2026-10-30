"""Crisis room, Priorities tab: the shelter gap for every municipality in the planned flood zone (live.variant();
map or list, a detail panel, CSV)."""
import pandas as pd
import streamlit as st

import anna
import core
import live
from core import about, fmt

SIDE = {"Liège": "BE", "Chaudfontaine": "BE", "Verviers": "BE", "Tabreux": "BE", "Rochefort": "BE", "Maastricht": "NL",
        "Roermond": "NL", "Venlo": "NL", "Wassenberg": "DE", "Eschweiler": "DE"}


def _from_map():
    objs = [o for os_ in st.session_state.gap_map.selection.objects.values() for o in os_]
    hit = [o.get("properties", o).get("rank") for o in objs]
    if hit and hit[0] is not None:
        st.session_state.commune = hit[0]


def _from_table():
    rows = st.session_state.gap_table.selection.rows
    if rows:
        st.session_state.commune = st.session_state.gap_table_ids[rows[0]]


def _plan(m):
    st.session_state._town = st.session_state.town = m
    st.session_state.near = m  # the shelter list (wherever it now lives) opens on this municipality


def render():
    d, v = core.load(), live.variant()
    rank = d["rank"][d["rank"].variant == v]
    sites = d["sites"].assign(in_zone=d["sites"][f"in_{v}_flood"].astype(bool))
    shelters = d["shelters"][~d["shelters"][f"in_{v}"].astype(bool)]  # dry in this zone
    st.subheader(f":red[:material/map:] Shelter gap by municipality · {v[2:]}-year flood",
                 help="Every municipality in the zone, most people without a shelter place within a 1.5 km walk first. "
                      "Select one on the map or in the list for the detail.")
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    side = c1.segmented_control("Country", ["All", "BE", "NL", "DE"], default="All", required=True, key="gap_country",
                                format_func={"All": "All", **core.COUNTRY}.get, label_visibility="collapsed")
    view = c2.segmented_control("View", ["List", "Map"], default="List", required=True, key="gap_view",
                                format_func={"List": ":material/list: List", "Map": ":material/map: Map"}.get,
                                label_visibility="collapsed")

    p = rank if side == "All" else rank[rank.country == side]
    ids = list(p["rank"])
    label = dict(zip(rank["rank"], rank.municipality))
    if st.session_state.get("commune") not in ids:
        st.session_state.commune = None
    sel = p[p["rank"] == st.session_state.commune].iloc[0] if st.session_state.commune is not None else None

    pickbox = lambda: st.selectbox(
        "Municipality", [None, *ids], key="commune", placeholder="Pick a municipality, or select one in the list or on the map",
        format_func=lambda x: "Whole area" if x is None else
        f"{label[x]} · ≈ {about(p.set_index('rank').no_shelter[x])} without shelter", label_visibility="collapsed")
    if view == "Map":
        left, right = st.columns([3, 2], gap="medium")
        with left:
            _map(p, sites, shelters, side, sel, v)
        with right:
            pickbox()
            _detail(sel, p, rank, sites, shelters)
        return
    # list: the table needs the full width; the detail sits under it, in two columns
    tab = p.sort_values("rank").reset_index(drop=True)
    st.session_state.gap_table_ids = list(tab["rank"])
    show = tab.assign(country=tab.country.map(core.COUNTRY))
    st.dataframe(core.paint(show[["municipality", "country", "gap", "no_shelter", "people",
                                  "hospitals_carehomes_flooded", "schools_flooded"]], "gap",
                            {k: c for k, (c, _) in core.GAP.items()}),
                 hide_index=True, height=360, on_select=_from_table, selection_mode="single-row", key="gap_table",
                 column_config={
                     "municipality": "Municipality", "country": st.column_config.TextColumn("Country", width="small"),
                     "gap": st.column_config.TextColumn("Shelter gap"),
                     "no_shelter": st.column_config.ProgressColumn("Without a place", format="localized", min_value=0,
                                                                   max_value=int(tab.no_shelter.max() or 1)),
                     "people": st.column_config.NumberColumn("People in the zone", format="localized",
                                                             help="EFAS zone, modelled, no dikes. Order of magnitude."),
                     "hospitals_carehomes_flooded": st.column_config.NumberColumn(
                         "Care sites", width="small", help="Hospitals and care homes flooded"),
                     "schools_flooded": st.column_config.NumberColumn("Schools", width="small", help="Schools flooded")})
    st.download_button("Download table (CSV)", tab.to_csv(index=False), f"shelter_gap_by_municipality_{v}.csv",
                       icon=":material/download:", type="tertiary")
    a, b = st.columns(2, gap="medium")
    with a:
        pickbox()
    _detail(sel, p, rank, sites, shelters, (a, b))


def _map(p, sites, shelters, side, sel, v):
    ev = sites[sites.in_zone & (sites.type != "school")]
    dry = shelters
    if side != "All":
        ev, dry = ev[ev.country == side], dry[dry.country == side]
    with st.popover("Layers", icon=":material/layers:"):
        show_water = st.toggle(f"{v[2:]}-year flood zone", value=True, key="gap_water", help="EFAS model, no dikes.")
        show_care = st.toggle("Care sites in the zone", value=True, key="gap_care")
        show_dry = st.toggle("Dry candidate sites", key="gap_dry")
    pick = None if sel is None else sel.municipality
    layers = [core.regions(p.assign(
        fill=[core.rgb(core.GAP[x][0], 150 if m == pick else 40 if pick else 85) for x, m in zip(p.gap, p.municipality)],
        tip=[f"{m} · {x}\n≈ {about(n)} people in the zone"
             + f"\n≈ {about(ns)} without a shelter place\nClick for details" for m, x, n, ns in
             zip(p.municipality, p.gap, p.people, p.no_shelter)]), "fill", pick)]
    layers += core.water(v) if show_water else []
    if show_dry:
        layers.append(core.points(dry.assign(tip=[f"{n}\n{t} · {m}\n≈ {c:,.0f} places" for n, t, m, c in
                                                  zip(dry.name, dry.type, dry.muni, dry.capacity_central)]),
                                  core.rgb(core.SHELTER), 3, 1))
    layers.append(core.towns(p.assign(
        fill=[core.rgb(core.GAP[x][0], 215 if sel is None or r == sel["rank"] else 90) for x, r in zip(p.gap, p["rank"])],
        tip=[f"{m} · {x}\n≈ {about(n)} people in the zone"
             + f"\n≈ {about(ns)} without a shelter place" for m, x, n, ns in
             zip(p.municipality, p.gap, p.people, p.no_shelter)]), "people", "fill", 18))
    if show_care:
        layers.append(core.points(ev.assign(tip=[f"{n}\n{t} · {m}\n{s:.0%} of the site in the 500-year zone"
                                                 for n, t, m, s in zip(ev.name, ev.type, ev.municipality,
                                                                       ev.share_of_site_flooded)]),
                                  core.rgb(core.EVACUATE), 5))
    vs = core.view(core.bbox(v), None if sel is None else (sel.lon, sel.lat), 11)
    core.deck(layers, vs, 480, on_select=_from_map, selection_mode="single-object", key="gap_map")
    core.legend("<b>Shelter gap</b> (circle: people in the zone)"
                + "".join(core.swatch(c, lab, True) for lab, (c, _) in core.GAP.items()),
                (core.swatch(core.RP_COL[v], f"{v[2:]}-year zone") if show_water else "")
                + (core.swatch(core.EVACUATE, "Care site in the zone", True) if show_care else "")
                + (core.swatch(core.SHELTER, "Dry candidate site", True) if show_dry else ""))


def _detail(sel, p, rank, sites, shelters, cols=None):
    a, b = cols or (st.container(), st.container())
    if sel is None:
        with a:
            core.group([(core.chip(lab, c), what, f"{fmt((p.gap == lab).sum())}") for lab, (c, what) in core.GAP.items()],
                       "Municipalities per shelter gap")
        return
    with a:
        _head(sel, rank, sites)
    with b:
        _where(sel, shelters)


def _head(sel, rank, sites):
    c, what = core.GAP[sel.gap]
    st.html(f"<div class='group'><div class='row'><div class='t'><b style='font-size:1.15rem'>{sel.municipality}</b>"
            f"<span>{core.COUNTRY[sel.country]} · rank {sel['rank']} of {len(rank)}"
            + f"</span></div><div class='v'><div class='score'>{about(sel.no_shelter)}<small> without</small></div>"
            f"{core.chip(sel.gap, c)}</div></div><div class='row'><div class='t'><b>Next step</b><span>{what}"
            "</span></div></div></div>")
    st.space("small")
    o = core.outlines()[sel.municipality]["properties"]
    core.group([
        ("<b>Residents</b>", f"Eurostat 2021 · {o['area_km2']:,.0f} km²", fmt(o["population_2021"])),
        ("<b>People in the zone</b>", f"{sel.people / o['population_2021']:.0%} of residents · EFAS model",
         f"≈ {about(sel.people)}"),
        ("<b>Shelter place in walking reach</b>", "Best possible plan", f"≈ {about(sel.covered)}"),
        ("<b>No shelter within 1.5 km</b>", "Too far to walk", f"≈ {about(sel.no_reach)}"),
        ("<b>Shelters in reach full</b>", "Need more or larger sites", f"≈ {about(sel.full)}"),
    ], "People in the zone, in detail", "EFAS flood hazard map (model) · GHS-OBAT · GHS-POP 2020")
    at_risk = sites[(sites.municipality == sel.municipality) & (sites.area == sel.area)]
    if len(at_risk):
        st.space("small")
        core.group([(f"<b>{n}</b>", f"{ty} · {s:.0%} of the site in the 500-year zone"
                     + ("" if w else " · not in this flood's zone"), "") for n, ty, s, w in
                    zip(at_risk.name, at_risk.type, at_risk.share_of_site_flooded, at_risk.in_zone)],
                   "Care sites and schools in the zone")


def _where(sel, shelters):
    sh = shelters.assign(d=core.km(sel.lon, sel.lat, shelters.lon, shelters.lat)).nsmallest(5, "d")
    core.group([(f"{n}", f"{ty} · {m} · ≈ {c:,.0f} places", f"{k:.1f} km") for n, ty, m, c, k in
                zip(sh.name, sh.type, sh.muni, sh.capacity_central, sh.d)],
               "Where people could go · nearest dry sites",
               "Candidates, not official shelters. Straight-line distance from the municipality centre; confirm "
               "capacity and access with the commune.")
    tw = anna.load()[1]
    if sel.municipality in set(tw[(tw.variant == live.variant()) & (tw.people >= 10)].municipality):  # the sidebar Town list
        if st.button(f"Open the town plan for {sel.municipality}", icon=":material/arrow_forward:", type="primary",
                     width="stretch", key="gap_plan"):
            _plan(sel.municipality)
            st.switch_page("views/evacuate.py")


def how():
    """Method notes for the How this is computed expander."""
    core.group([
        ("<b>Who needs a place</b>", "Residents of homes inside the planned flood zone (EFAS model)", ""),
        ("<b>Where they can go</b>", "Schools, sports halls and civic buildings dry in that zone, ≥ 200 m² floor", ""),
        ("<b>How many fit</b>", "Floor × 50 % usable ÷ 4 m² per person", ""),
        ("<b>How far</b>", "1.5 km straight line, the best possible plan for the whole area", ""),
    ], "How the shelter gap is worked out", "Central assumptions; stricter and looser ones give the range above. Source · "
       + "EFAS flood hazard maps (model) · " + core.AS_OF["osm"])
