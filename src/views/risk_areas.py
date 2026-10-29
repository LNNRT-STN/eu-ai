import streamlit as st

import core
from core import about, fmt

d = core.load()
areas, towns, sites, shelters = d["areas"], d["towns"], d["sites"], d["shelters"]
gauges, *_ = core.outlook()

core.header("Risk areas", "Who sat in the July 2021 water, per municipality, and which care sites and schools were in it.")

c1, c2, c3 = st.columns([3, 2, 2], vertical_alignment="center")
variant = c1.segmented_control("Flood map", list(core.VARIANT), format_func=core.VARIANT.get, default="worst",
                               required=True, label_visibility="collapsed",
                               help="All passes: the headline, closer to official counts. First pass: a lower bound.")
names = dict(zip(areas.area, areas.name))
area = c2.selectbox("Area", [None, *names], format_func=lambda a: "All ten areas" if a is None else names[a],
                    label_visibility="collapsed")
with c3.popover("Map layers", icon=":material/layers:", width="stretch"):
    show_care = st.toggle("Care sites and schools in the water", value=True)
    show_gauges = gauges is not None and st.toggle("River forecast points", value=True)

a = areas[areas.variant == variant]
obs, mod = a[~a.area.eq("vesdre")], a[a.area.eq("vesdre")].iloc[0]
st.caption(f":material/info: **≈ {about(obs.people_2020.sum())} people** in **{fmt(obs.buildings.sum())} buildings** in "
           f"the observed water. A floor, not the toll: the satellite missed most of the Vesdre valley. Modelled Vesdre "
           f"({'100' if variant == 'main' else '500'}-year zone): ≈ {about(mod.people_2020)} more, kept apart.")

com = towns[towns.variant == variant]
if area is not None:
    com = com[com.area == area]
com = com.sort_values("people", ascending=False).reset_index(drop=True)
ev = sites[sites[f"in_{variant}_flood"] & ((area is None) | (sites.area == area))]
left, right = st.columns([3, 2], gap="medium")

with right:
    tab_c, tab_e = st.tabs([f"Municipalities · {len(com)}", f"Sites in the water · {len(ev)}"])
    with tab_c:
        tab = com.assign(country=com.country.map(core.COUNTRY))
        pick = st.dataframe(tab[["municipality", "country", "people"]], hide_index=True, height=420, on_select="rerun",
                            selection_mode="single-row", key=f"commune-{variant}-{area}", column_config={
                                "municipality": "Municipality",
                                "country": st.column_config.TextColumn("Country", width="small"),
                                "people": st.column_config.ProgressColumn("People", format="localized", min_value=0,
                                                                          max_value=int(tab.people.max() or 1))})
    with tab_e:
        st.dataframe(ev[["name", "type", "municipality", "share_of_site_flooded"]], hide_index=True, height=420,
                     column_config={"name": "Site", "type": st.column_config.TextColumn("Type", width="small"),
                                    "municipality": "Municipality",
                                    "share_of_site_flooded": st.column_config.ProgressColumn(
                                        "In the water", format="percent", min_value=0, max_value=1, width="small")})
        st.caption("Hospitals, care homes and schools (OSM) with at least 5 % of the site inside the water. "
                   "Vesdre sites are in the modelled zone.")

sel = com.iloc[pick.selection.rows[0]] if pick.selection.rows else None
if sel is not None:
    with right:
        here = ev[ev.municipality == sel.municipality]
        near = (core.km(sel.lon, sel.lat, shelters.lon, shelters.lat) <= 1.5).sum()
        core.group([("People in the water", f"<b>≈ {about(sel.people)}</b>"), ("Buildings", fmt(sel.buildings)),
                    ("Without a shelter place", f"≈ {about(sel.no_shelter)}"),
                    ("Care sites and schools in the water", fmt(len(here))),
                    ("Dry candidate sites within 1.5 km of the centre", fmt(near))],
                   sel.municipality + (" · modelled" if sel.modelled else ""))
        if st.button("Show dry sites nearby", icon=":material/home_health:", type="primary", width="stretch"):
            st.session_state.near = sel.municipality
            st.switch_page("views/shelters.py")

layers = core.water(variant) + [core.towns(com.assign(
    fill=[core.rgb(core.MISSED if m else core.PEOPLE, 210) for m in com.modelled],
    tip=[f"<b>{m}</b><br>≈ {about(p)} people in the water" + (" (modelled)" if mo else "")
         + f"<br>{b:,} buildings" for m, p, b, mo in zip(com.municipality, com.people, com.buildings, com.modelled)]),
    "people", "fill", 20)]
if show_care:
    layers.append(core.points(ev.assign(tip=[f"<b>{n}</b><br>{t} · {m}<br>{s:.0%} of the site in the water" for n, t, m, s in
                                             zip(ev.name, ev.type, ev.municipality, ev.share_of_site_flooded)]),
                              core.rgb(core.EVACUATE), 5))
if show_gauges:
    import forecast
    layers.append(core.points(gauges.assign(fill=[core.rgb(forecast.LEVELS[l][1]) for l in gauges.level],
                                            tip=[f"<b>{r.gauge}</b><br>forecast peak {r.peak:,.0f} m³/s ({r.pct_2021:.0%} of 2021)"
                                                 for r in gauges.itertuples()]), "fill", 7))
with left:
    focus = (sel.lon, sel.lat) if sel is not None else (com.lon.mean(), com.lat.mean()) if area is not None else None
    core.deck(layers, core.view(core.bbox(variant), focus, 12 if sel is not None else 10.5), 560)
    core.legend("<b>Municipality, size = people in the water</b>" + core.swatch(core.PEOPLE, "Observed", True)
                + core.swatch(core.MISSED, "Modelled (Vesdre)", True),
                core.swatch(core.WATER, "Observed 2021 water") + core.swatch(core.MODEL, "Vesdre, modelled water")
                + (core.swatch(core.EVACUATE, "Care site or school in the water", True) if show_care else ""))
core.asof("obs", "model", "osm")
