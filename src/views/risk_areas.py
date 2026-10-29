"""Who sat in the July 2021 water, per municipality, and which care sites and schools were in it: map, list, details.
A section of "2021, today, next" (then_now.py), tab "What the water covered". Its selection lives in
st.session_state.risk_town, because the sidebar Town picker owns `town`."""
import streamlit as st

import anna
import core
from core import about, fmt

KEY = "risk_town"


def render(named=frozenset()):
    """named: municipalities (plain names) that appear in a measure on record, marked in the list."""
    d = core.load()
    areas, towns, sites, shelters = d["areas"], d["towns"], d["sites"], d["shelters"]
    gauges, *_ = core.outlook()

    c1, c2, c3 = st.columns([3, 2, 2], vertical_alignment="center")
    variant = c1.segmented_control("Flood map", list(core.VARIANT), format_func=core.VARIANT.get, default="worst",
                                   required=True, label_visibility="collapsed", key="risk_variant",
                                   help="All passes: the headline, closer to official counts. First pass: a lower bound.")
    names = dict(zip(areas.area, areas.name))
    area = c2.selectbox("Area", [None, *names], format_func=lambda a: "All ten areas" if a is None else names[a],
                        label_visibility="collapsed", key="risk_area")
    with c3.popover("Map layers", icon=":material/layers:", width="stretch"):
        show_care = st.toggle("Care sites and schools in the water", value=True, key="risk_care")
        show_gauges = gauges is not None and st.toggle("River forecast points", value=True, key="risk_gauges")

    a = areas[areas.variant == variant]
    obs, mod = a[~a.area.eq("vesdre")], a[a.area.eq("vesdre")].iloc[0]
    st.caption(f"≈ **{about(obs.people_2020.sum())} people** in **{fmt(obs.buildings.sum())} buildings** in the observed "
               f"water (a floor). :gray[Modelled Vesdre ({'100' if variant == 'main' else '500'}-year zone): "
               f"≈ {about(mod.people_2020)} more, never added.]")

    com = towns[towns.variant == variant]
    if area is not None:
        com = com[com.area == area]
    com = com.sort_values("people", ascending=False).reset_index(drop=True)
    ev = sites[sites[f"in_{variant}_flood"] & ((area is None) | (sites.area == area))]
    tkey = f"commune-{variant}-{area}"
    if st.session_state.get(KEY) not in set(com.municipality):
        st.session_state[KEY] = None

    def from_map():
        objs = [o for os_ in st.session_state.risk_map.selection.objects.values() for o in os_]
        hit = [o.get("properties", o).get("municipality") for o in objs]
        if hit and hit[0] is not None:
            st.session_state[KEY] = hit[0]

    def from_table(names=tuple(com.municipality)):
        rows = st.session_state[tkey].selection.rows
        st.session_state[KEY] = names[rows[0]] if rows else None

    left, right = st.columns([3, 2], gap="medium")

    with right:
        tab_c, tab_e = st.tabs([f":orange[:material/location_city:] Municipalities · {len(com)}",
                                f":violet[:material/local_hospital:] Sites in the water · {len(ev)}"])
        with tab_c:
            tab = com.assign(seen=com.modelled.map({True: "Modelled", False: "Observed"}),
                             found=core.plain(com.municipality).isin(named).map({True: "Yes", False: ""}))
            st.dataframe(tab[["municipality", "people", "seen", "found"]], hide_index=True, height=420,
                         on_select=from_table, selection_mode="single-row", key=tkey, column_config={
                             "municipality": "Municipality",
                             "people": st.column_config.ProgressColumn("People", format="localized", min_value=0,
                                                                       max_value=int(tab.people.max() or 1),
                                                                       help="Residents in the water, an order of magnitude"),
                             "seen": st.column_config.TextColumn(
                                 "2021", width="small", help="Observed: satellite map. Modelled: the Vesdre, missed by "
                                                             "the satellite, from the EFAS zone. Never added together."),
                             "found": st.column_config.TextColumn(
                                 "Change", width="small", help="Named in a measure under “What changed since”.")})
        with tab_e:
            st.dataframe(ev[["name", "type", "municipality", "share_of_site_flooded"]], hide_index=True, height=420,
                         column_config={"name": "Site", "type": st.column_config.TextColumn("Type", width="small"),
                                        "municipality": "Municipality",
                                        "share_of_site_flooded": st.column_config.ProgressColumn(
                                            "In the water", format="percent", min_value=0, max_value=1, width="small")})
            st.caption("Vesdre sites are in the modelled zone.",
                       help="Hospitals, care homes and schools (OpenStreetMap) with at least 5 % of the site inside "
                            "the water.")

    sel = com[com.municipality == st.session_state[KEY]].iloc[0] if st.session_state[KEY] else None
    with right:
        if sel is None:
            st.caption(":material/touch_app: Click a municipality on the map or in the list for its details.")
        else:
            here = ev[ev.municipality == sel.municipality]
            near = (core.km(sel.lon, sel.lat, shelters.lon, shelters.lat) <= 1.5).sum()
            o = core.outlines()[sel.municipality]["properties"]
            core.group([("Residents", f"Eurostat 2021 · {o['area_km2']:,.0f} km²", fmt(o["population_2021"])),
                        ("People in the water", f"{sel.people / o['population_2021']:.0%} of residents · "
                         + ("EFAS model" if sel.modelled else "satellite map, 2020 census grid"),
                         f"<b>≈ {about(sel.people)}</b>"),
                        ("Same homes, 2025 census grid", "Who lives there now", f"≈ {about(sel.people_2025)}"),
                        ("Buildings in the water", "GHS-OBAT", fmt(sel.buildings)),
                        ("Shelter place in walking reach", "Best possible plan, 1.5 km", f"≈ {about(sel.covered)}"),
                        ("No shelter within 1.5 km", "Too far to walk", f"≈ {about(sel.no_reach)}"),
                        ("Shelters in reach full", "Need more or larger sites", f"≈ {about(sel.full)}"),
                        ("Care sites and schools in the water", "OSM, ≥ 5 % of the site", fmt(len(here))),
                        ("Dry candidate sites", "Candidates, not official · within 1.5 km of the centre", fmt(near))],
                       sel.municipality + (" · modelled" if sel.modelled else ""),
                       core.AS_OF["model" if sel.modelled else "obs"])
            if len(here):
                core.group([(f"<b>{n}</b>", f"{ty} · {s:.0%} of the site in the water", "") for n, ty, s in
                            zip(here.name, here.type, here.share_of_site_flooded)], "Which sites")
            # the Town plan holds this town's shelters and evacuation; only towns in its picker can be opened there
            tw = anna.load()[1]
            if sel.municipality in set(tw[(tw.variant == "worst") & (tw.people >= 10)].municipality):
                if st.button("Open its town plan", icon=":material/directions_run:", type="primary", width="stretch",
                             key="risk_open_plan", help="Shelters, roads out and who gives the order, for this town."):
                    st.session_state._town = st.session_state.near = sel.municipality
                    st.switch_page("views/evacuate.py")

    tips = [f"{m}\n≈ {about(p)} people in the water" + (" (modelled)" if mo else "") + f"\n{b:,} buildings\nClick for details"
            for m, p, b, mo in zip(com.municipality, com.people, com.buildings, com.modelled)]
    pick = None if sel is None else sel.municipality
    layers = [core.regions(com.assign(fill=[core.rgb(core.MISSED if mo else core.PEOPLE, 120 if m == pick else 30 if pick else 55)
                                            for m, mo in zip(com.municipality, com.modelled)], tip=tips), "fill", pick)]
    layers += core.water(variant) + [core.towns(com.assign(
        fill=[core.rgb(core.MISSED if m else core.PEOPLE, 210) for m in com.modelled], tip=tips), "people", "fill", 20)]
    if show_care:
        layers.append(core.points(ev.assign(tip=[f"{n}\n{t} · {m}\n{s:.0%} of the site in the water" for n, t, m, s in
                                                 zip(ev.name, ev.type, ev.municipality, ev.share_of_site_flooded)]),
                                  core.rgb(core.EVACUATE), 5))
    if show_gauges:
        import forecast
        layers.append(core.points(gauges.assign(fill=[core.rgb(forecast.LEVELS[l][1]) for l in gauges.level],
                                                tip=[f"{r.gauge}\nforecast peak {r.peak:,.0f} m³/s ({r.pct_2021:.0%} of 2021)"
                                                     for r in gauges.itertuples()]), "fill", 7))
    with left:
        focus = (sel.lon, sel.lat) if sel is not None else (com.lon.mean(), com.lat.mean()) if area is not None else None
        core.deck(layers, core.view(core.bbox(variant), focus, 12 if sel is not None else 10.5), 520, on_select=from_map,
                  selection_mode="single-object", key="risk_map")
        core.legend("<b>Outlined area: municipality · circle size: people in the water · click for details</b>"
                    + core.swatch(core.PEOPLE, "Observed", True) + core.swatch(core.MISSED, "Modelled (Vesdre)", True),
                    core.swatch(core.WATER, "Observed 2021 water") + core.swatch(core.MODEL, "Vesdre, modelled water")
                    + (core.swatch(core.EVACUATE, "Care site or school in the water", True) if show_care else ""))
