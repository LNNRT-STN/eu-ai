import pandas as pd
import pydeck as pdk
import streamlit as st

import core
from core import fmt

s, communes, cells, sites, geo = core.load()
gauges, *_ = core.outlook()

core.header("Risk areas", "Who lives where the river can reach, per commune, and which care sites would need to leave first.")

c1, c2 = st.columns([3, 2], vertical_alignment="center")
lens = c1.segmented_control("View", list(core.LENS), format_func=core.LENS.get, label_visibility="collapsed",
                            default="obs" if st.query_params.get("view") == "observed" else "rp100", required=True)
with c2.popover("Map layers", icon=":material/layers:", width="stretch"):
    by_commune = lens == "obs" and "regions" in geo and st.toggle(
        "Colour communes by 2021 impact", help="Residents in the water, flooded buildings and share of the population "
        "hit, ranked against the other hit communes. Severe = top quarter.")
    show_care = st.toggle("Care sites at risk", value=True)
    show_gauges = gauges is not None and st.toggle("River forecast points", value=True)

t = s["lenses"][lens]
st.caption(f":material/info: **{fmt(t['residents'])} residents** in **{fmt(t['buildings'])} buildings** across "
           f"{t['communes']} communes. " + (
               "Model, not forecast: EFAS ignores dikes and flood walls and skips streams under 500 km²."
               if lens == "rp100" else
               "A floor, not the toll: the satellite missed most of the Vesdre valley and central Liège."))

com = communes[communes.lens == lens].sort_values("residents", ascending=False).reset_index(drop=True)
ev = sites[sites.role == "evacuate"]
left, right = st.columns([3, 2], gap="medium")

with right:
    tab_c, tab_e = st.tabs([f"Communes · {len(com)}", f"Care sites at risk · {len(ev)}"])
    with tab_c:
        tab = com.assign(country=com.country.map(core.COUNTRY), residents=com.residents.round().astype(int))
        pick = st.dataframe(tab[["commune", "country", "residents"]], hide_index=True, height=420, on_select="rerun",
                            selection_mode="single-row", key=f"commune-{lens}", column_config={
                                "commune": "Commune", "country": st.column_config.TextColumn("Country", width="small"),
                                "residents": st.column_config.ProgressColumn("Residents", format="localized", min_value=0,
                                                                             max_value=int(tab.residents.max()))})
    with tab_e:
        st.dataframe(ev[["name", "type", "commune", "flood_2021", "model_zone"]], hide_index=True, height=420,
                     column_config={"name": "Site", "type": "Type", "commune": "Commune", "flood_2021": "July 2021",
                                    "model_zone": "Model zone"})
        st.caption("Hospitals and care homes (OSM) inside or within 100 m of the 2021 water, or in the EFAS 10- or "
                   "100-year zone. OSM has no sites for the Eschweiler area.")

sel = com.iloc[pick.selection.rows[0]] if pick.selection.rows else None
if sel is not None:
    with right:
        here = ev[ev.lau_id == sel.lau_id]
        sh = sites[sites.role == "shelter"]
        near = (core.km(sel.lon, sel.lat, sh.lon, sh.lat) <= 5).sum()
        core.group([("Residents", f"<b>{fmt(sel.residents)}</b>"), ("Buildings", fmt(sel.buildings)),
                    ("Care sites at risk", fmt(len(here))), ("Candidate shelters within 5 km", fmt(near))],
                   sel.commune)
        if st.button("Show dry sites nearby", icon=":material/home_health:", type="primary", width="stretch"):
            st.session_state.near = sel.lau_id
            st.switch_page("views/shelters.py")

cel = cells[(cells.lens == lens) & (cells.residents >= 1)]
layers = core.water(geo, lens) + [
    pdk.Layer("GeoJsonLayer", geo["regions"], filled=True, stroked=True, get_fill_color="properties.fill",
              get_line_color=[255, 255, 255, 230], line_width_min_pixels=1, pickable=True, auto_highlight=True)
    if by_commune else
    core.blocks(cel)]
if show_care:
    layers.append(core.points(ev.assign(tip=[f"<b>{n}</b><br>{t} · {c}<br>2021: {f} · model: {z}" for n, t, c, f, z in
                                             zip(ev.name, ev.type, ev.commune, ev.flood_2021, ev.model_zone)]),
                              core.rgb(core.EVACUATE), 5))
if show_gauges:
    import forecast
    layers.append(core.points(gauges.assign(fill=[core.rgb(forecast.LEVELS[l][1]) for l in gauges.level],
                                            tip=[f"<b>{r.gauge}</b><br>forecast peak {r.peak:,.0f} m³/s ({r.pct_2021:.0%} of 2021)"
                                                 for r in gauges.itertuples()]), "fill", 7))
with left:
    core.deck(layers, core.view(s, None if sel is None else (sel.lon, sel.lat)), 560)
    keys = ("<b>2021 impact</b>" + "".join(core.swatch(h, lab) for lab, h in core.IMPACT)
            + core.swatch(core.MISSED, "Flooded, missed by satellite") if by_commune else
            "<b>Residents per ~1 km cell</b>" + "".join(core.swatch(h, lab) for _, lab, h in core.CLASSES))
    core.legend(keys, core.swatch("rgba(0,113,227,.4)", "Observed 2021 water" if lens == "obs" else "Modelled 100-year zone")
                + (core.swatch(core.EVACUATE, "Care site at risk", True) if show_care else ""))
