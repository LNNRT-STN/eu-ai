"""Valley in 3D: one town's July 2021 water draped on satellite terrain, with the homes, dry shelters, evacuation roads,
rail and care sites in it, and a day-by-day river replay. MapLibre GL JS (open source, no token) in a component;
elevation: AWS Terrain Tiles (Terrarium); imagery: EOX Sentinel-2 cloudless or Esri World Imagery.
Numbers: outputs/data/ (app_towns, buildings_3d, bus_plan, critical_sites, evac_edges, infra_rail) and the GloFAS
replay (core.load_replay). The water opacity on the timeline is a visual cue, not a flood simulation."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import anna
import core
import map3d
import forecast
from core import about, fmt

V = "worst"
head, towns, crit, shel, flood, *_ = anna.load()
recv, bus = anna.load_moves()
B3D = map3d.B3D

# ---- town: shared sidebar picker (session_state["town"]), else the town with the most people in the water
T = towns[towns.variant == V].sort_values("people", ascending=False)
pick = st.session_state.get("town")
rows = T[T.municipality == pick]
t = (rows if len(rows) else T).iloc[0]
modelled = t.area in anna.MODELLED

# ---- controls
with st.sidebar:
    st.caption("3D view layers")
    on = dict(water=st.toggle("2021 water", True), homes=st.toggle("Homes", True),
              shelters=st.toggle("Dry shelters", True), roads=st.toggle("Evacuation roads", True),
              rail=st.toggle("Rail in the water", True), care=st.toggle("Care sites", True))
    exag = st.slider("Terrain exaggeration", 1.0, 3.0, 1.5, 0.25, help="Heights ×; 1 = true relief")
    imagery = st.segmented_control("Imagery", ["Sentinel-2", "Esri"], default="Sentinel-2",
                                   help="Sentinel-2 cloudless (10 m, EOX) or Esri World Imagery (sharper)") or "Sentinel-2"

# ---- data for this town
hb = B3D[(B3D.municipality == t.municipality) & (B3D.area == t.area)]
homes = hb[hb.use == 1]
single = (homes.storeys == 1) & (homes.height_m != 2.5)  # 2.5 m is OBAT's fill-in value: height unknown
n_single, n_unknown = int(single.sum()), int((homes.height_m == 2.5).sum())
plan = (bus[(bus.municipality == t.municipality) & (bus.area == t.area)]
        .groupby(["shelter", "s_lon", "s_lat"], as_index=False).people.sum().sort_values("people", ascending=False))
care = crit[(crit.municipality == t.municipality) & (crit.share_of_site_flooded >= .05) & crit.in_worst_flood]


# ---- river replay: nearest GloFAS point within 15 km of the town centre
rep = core.load_replay().loc["2021-07-12":"2021-07-20"]
g_lat, g_lon = np.array(list(forecast.GAUGES.values())).T
d_km = core.km(t.lon, t.lat, g_lon, g_lat)
gauge = list(forecast.GAUGES)[int(d_km.argmin())] if d_km.min() <= 15 else None

# ---- layout
st.title(f"{t['name']} in 3D")
st.caption(f"The July 2021 water on the valley floor{' (modelled: EFAS 500-year zone, no satellite map here)' if modelled else ''}. "
           "Drag to pan, right-drag or Ctrl-drag to tilt and turn, scroll to zoom.")

opacity, day = .45, None
if gauge:
    days = list(rep.index)
    q = rep[gauge]
    day = st.select_slider("Day, July 2021", days, value=q.idxmax(), format_func=lambda d: f"{d:%a %d %b}")
    lo, hi = q.min(), q.max()
    opacity = .1 + .4 * (q[day] - lo) / (hi - lo) if hi > lo else .45

map_col, facts = st.columns([3, 1], gap="medium")

with facts:
    with st.container(border=True):
        st.metric("Residents in the 2021 water", about(t.people),
                  help="GHS-POP 2020 spread over flooded homes: an order of magnitude")
        st.metric("Single-storey homes", fmt(n_single),
                  help=f"No upper floor to escape to. {fmt(n_unknown)} more homes have no reliable height (OBAT 2.5 m).")
        st.metric("Dry shelters", fmt(len(plan)), help="Candidate sites in the 10 km bus plan, dry in 2021 and "
                                                        "in the EFAS 100-year model; not official")
        st.metric("Care sites and schools", fmt(len(care)), help="Hospitals, care homes, schools with at least 5 % "
                                                                  "of the site in the 2021 water")
    if gauge:
        with st.container(border=True):
            ch = pd.DataFrame({"day": rep.index, "flow": rep[gauge].values})
            base = alt.Chart(ch).encode(x=alt.X("day:T", title=None, axis=alt.Axis(format="%d", tickCount=9)))
            line = base.mark_line(color="#0071e3", strokeWidth=2).encode(
                y=alt.Y("flow:Q", title="m³/s", axis=alt.Axis(tickCount=3)))
            rule = alt.Chart(pd.DataFrame({"day": [day]})).mark_rule(color="#1d1d1f", strokeDash=[3, 3]).encode(x="day:T")
            dot = base.transform_filter(alt.datum.day == alt.expr.toDate(day.isoformat())).mark_point(
                filled=True, size=50, color="#1d1d1f").encode(y="flow:Q")
            st.caption(f"River flow, {gauge} ({d_km.min():.0f} km away)")
            st.altair_chart((line + rule + dot).properties(height=120), width="stretch")
            st.caption(f"{day:%d %b}: {fmt(rep.loc[day, gauge])} m³/s. GloFAS model. Water opacity on the map follows "
                       "this flow as a visual cue only: the map shows the final 2021 extent, not the water on that day.")
    else:
        st.caption("No river point of the replay lies within 15 km of this town, so there is no timeline here.")


with map_col:
    map3d.render(t, on, exag, imagery, opacity)
