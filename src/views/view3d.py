"""Valley in 3D, a tab of the Town plan: one town's July 2021 water draped on satellite terrain, with the homes, dry
shelters, evacuation roads, rail and care sites in it, and a day-by-day river replay. MapLibre GL JS (open source, no
token) in a component; elevation: AWS Terrain Tiles (Terrarium); imagery: EOX Sentinel-2 cloudless or Esri World
Imagery. Numbers: outputs/data/ (app_towns, buildings_3d, bus_plan, critical_sites, evac_edges, infra_rail) and the
GloFAS replay (core.load_replay). The water opacity on the timeline is a visual cue, not a flood simulation.

Imported once by views/evacuate.py, so everything that draws lives in render()."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import anna
import core
import map3d
import forecast
from core import fmt

LAYERS = {"water": "2021 water", "homes": "Homes", "shelters": "Dry shelters", "roads": "Evacuation roads",
          "rail": "Rail in the water", "care": "Care sites"}


def render(t):
    """Draw town row `t` (app_towns, variant worst) in 3D, controls in a popover above the map."""
    modelled = t.area in anna.MODELLED

    # river replay: nearest GloFAS point within 15 km of the town centre
    rep = core.load_replay().loc["2021-07-12":"2021-07-20"]
    g_lat, g_lon = np.array(list(forecast.GAUGES.values())).T
    d_km = core.km(t.lon, t.lat, g_lon, g_lat)
    gauge = list(forecast.GAUGES)[int(d_km.argmin())] if d_km.min() <= 15 else None

    c_pop, c_day = st.columns([1, 3], vertical_alignment="bottom")
    with c_pop.popover("Layers", icon=":material/layers:", width="stretch"):
        on = {k: st.toggle(lab, True, key=f"v3d_{k}") for k, lab in LAYERS.items()}
        exag = st.slider("Terrain exaggeration", 1.0, 3.0, 1.5, 0.25, key="v3d_exag", help="Heights ×; 1 = true relief")
        imagery = st.segmented_control("Imagery", ["Sentinel-2", "Esri"], default="Sentinel-2", key="v3d_img",
                                       help="Sentinel-2 cloudless (10 m, EOX) or Esri World Imagery (sharper)") \
            or "Sentinel-2"

    opacity, day = .45, None
    if gauge:
        days = list(rep.index)
        q = rep[gauge]
        day = c_day.select_slider("Day, July 2021", days, value=q.idxmax(), format_func=lambda d: f"{d:%a %d %b}",
                                  key=f"v3d_day_{gauge}",
                                  help="Water opacity on the map follows the river flow that day, as a visual cue only: "
                                       "the map always shows the final 2021 extent, not the water on that day.")
        lo, hi = q.min(), q.max()
        opacity = .1 + .4 * (q[day] - lo) / (hi - lo) if hi > lo else .45
    else:
        c_day.caption("No river point of the replay lies within 15 km of this town, so there is no timeline here.")
    if modelled:
        st.caption(":gray[Modelled water: EFAS 500-year zone, no satellite map of the Vesdre.]")

    map_col, side = st.columns([3, 1], gap="medium")
    with map_col:
        map3d.render(t, on, exag, imagery, opacity, height=560, attribution=False)
    with side:
        if gauge:
            ch = pd.DataFrame({"day": rep.index, "flow": rep[gauge].values})
            base = alt.Chart(ch).encode(x=alt.X("day:T", title=None, axis=alt.Axis(format="%d", tickCount=9)))
            line = base.mark_line(color="#0071e3", strokeWidth=2).encode(
                y=alt.Y("flow:Q", title="m³/s", axis=alt.Axis(tickCount=3)))
            rule = alt.Chart(pd.DataFrame({"day": [day]})).mark_rule(color="#1d1d1f", strokeDash=[3, 3]).encode(x="day:T")
            dot = base.transform_filter(alt.datum.day == alt.expr.toDate(day.isoformat())).mark_point(
                filled=True, size=50, color="#1d1d1f").encode(y="flow:Q")
            st.markdown(f"**River flow, {gauge}**", help=f"{d_km.min():.0f} km from the town centre. GloFAS model, "
                                                           "modelled after the event.")
            st.altair_chart((line + rule + dot).properties(height=140), width="stretch")
            st.caption(f"{day:%a %d %b}: {fmt(rep.loc[day, gauge])} m³/s (modelled)")
        st.caption("Drag to pan, right-drag or Ctrl-drag to tilt and turn, scroll to zoom.")

    with st.expander("How this is computed", icon=":material/info:"):
        st.caption("Elevation: AWS Terrain Tiles (Mapzen, Terrarium; SRTM, EU-DEM and other open sources). Imagery: "
                   + ("Sentinel-2 cloudless 2021 by EOX IT Services GmbH (contains modified Copernicus Sentinel data), "
                      "CC BY-NC-SA 4.0, non-commercial use." if imagery == "Sentinel-2" else
                      "Esri World Imagery (Esri, Maxar, Earthstar Geographics), attribution required, Esri terms of use.")
                   + " Map: MapLibre GL JS (BSD). Homes are OBAT points drawn as 9 m blocks, not real outlines; "
                     "red = single-storey; 2.5 m tall homes have no reliable height. Dry shelters are the candidate "
                     "sites of the 10 km plan, not official. The water opacity follows the GloFAS replay flow as a "
                     "visual cue, not a flood simulation.")
