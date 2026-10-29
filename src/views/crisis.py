"""Crisis room: the whole region, live. A replay of July 2021 (or the live forecast) drives each town's alert level;
at each rise the tool queues briefings for the mayor and the district fire brigade (drafted by Claude from the tool's
numbers), simulated check-ins arrive, and roads in the 2021 water close. State: src/live.py (data/live.db).
Status uses the highest river flow reached so far (it never drops in a replay); daily GloFAS flows are placed at noon
and interpolated, so times are accurate to about ±12 h."""
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
import live
from core import about, fmt

COL = {"evacuate": "#d70015", "warn": "#f2994a", "watch": "#f2c94c", "none": "#8e8e93"}
WORD = {"evacuate": "Evacuate", "warn": "Warn", "watch": "Watch", "none": "Normal"}
towns = anna.load()[1]
T = towns[towns.variant == "worst"].drop_duplicates("municipality").set_index("municipality")

# ------------------------------------------------------------------ scenario player (sidebar)
c = live.clock()
with st.sidebar:
    st.caption("Scenario")
    mode = st.segmented_control("Mode", ["replay", "live"], default=c["mode"], key="cr_mode",
                                format_func={"replay": "Replay July 2021", "live": "Live forecast"}.get,
                                label_visibility="collapsed") or c["mode"]
    if mode != c["mode"]:
        live.set_mode(mode)
    b1, b2 = st.columns(2)
    if c["playing"]:
        b1.button("Pause", icon=":material/pause:", on_click=live.pause, width="stretch")
    else:
        b1.button("Play", icon=":material/play_arrow:", on_click=live.play, type="primary", width="stretch")
    b2.button("Reset", icon=":material/replay:", on_click=live.reset, width="stretch",
              help="Back to 12 July 06:00; clears alerts, reports, closures and simulated check-ins")
    sp = st.select_slider("Speed", [1.0, 3.0, 6.0, 12.0], value=float(c["speed"]) if c["speed"] in (1, 3, 6, 12) else 3.0,
                          format_func=lambda x: f"{x:g} h per second")
    if sp != c["speed"]:
        live.set_speed(sp)


def board():
    c = live.advance()
    t = c["t"]
    live.tick(t)
    s = live.towns_status(t)
    m = live.summary(t)
    st.title("Crisis room")
    st.subheader(f"{t:%a %d %b %Y, %H:%M}" + (" · replay of July 2021" if c["mode"] == "replay" else " · live forecast"))

    k = st.columns(6)
    k[0].metric("Towns to evacuate", m["evacuate"], border=True)
    k[1].metric("Towns warned", m["warn"], border=True)
    k[2].metric("People to move", about(m["people_evacuate"]), border=True,
                help="Residents in the 2021 water of the towns at 'evacuate', scaled by the impact forecast")
    k[3].metric("Reported safe", fmt(m["safe"]), border=True, help="Check-ins; in the replay they are simulated")
    k[4].metric("Need help", fmt(m["needs_help"]), border=True)
    k[5].metric("Roads closed", m["roads_closed"], border=True)

    left, right = st.columns([3, 2], gap="medium")
    with left:
        d = s.assign(lon=s.municipality.map(T.lon), lat=s.municipality.map(T.lat)).dropna(subset=["lon"])
        d["status"] = d.status.where(d.status.isin(COL), "none")
        d = d.assign(c=d.status.map(lambda x: core.rgb(COL[x], 220)), r=d.people.clip(lower=50) ** .5 * .35 + 5,
                     tname=d.municipality.map(anna.town), tinfo=[f"{WORD[x]} · {about(p)} residents in the 2021 water"
                                                                for x, p in zip(d.status, d.people)])
        cl = live.closures()
        layers = [pdk.Layer("ScatterplotLayer", d, get_position=["lon", "lat"], get_fill_color="c", get_radius="r",
                            radius_units="'pixels'", get_line_color=[255, 255, 255], line_width_min_pixels=2,
                            stroked=True, pickable=True)]
        if len(cl):
            layers.append(pdk.Layer("ScatterplotLayer", cl.dropna(subset=["lon"]), get_position=["lon", "lat"],
                                    get_fill_color=[29, 29, 31], get_radius=4, radius_units="'pixels'"))
        st.pydeck_chart(pdk.Deck(layers=layers, map_style=pdk.map_styles.CARTO_LIGHT,
                                 initial_view_state=pdk.ViewState(longitude=6.1, latitude=50.65, zoom=7.6),
                                 tooltip={"html": "<b>{tname}</b><br/>{tinfo}"},
                                 views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=430)
        st.caption(":red[●] Evacuate · :orange[●] Warn · :yellow[●] Watch · :gray[●] Normal · ● black: road closed. Circle size = residents "
                   "in the 2021 water.")
    with right:
        ev = live.events().tail(8).iloc[::-1]
        st.markdown("**Latest**")
        if ev.empty:
            st.caption("Nothing yet. Press Play in the sidebar.")
        for r in ev.itertuples():
            st.markdown(f"`{pd.Timestamp(r.t):%d %b %H:%M}` **{anna.town(r.municipality)}** → {WORD.get(r.to, r.to)}")
        ob = live.outbox().tail(4).iloc[::-1]
        st.markdown("**Reports sent** (outbox)")
        if ob.empty:
            st.caption("Briefings for mayors and fire brigades appear here when a town's alert rises.")
        for r in ob.itertuples():
            with st.expander(f"{pd.Timestamp(r.t):%d %b %H:%M} · {r.recipient}"):
                st.write(live.report(r.id))
                st.caption("Drafted by Claude from the tool's numbers; check before sending." if r.source != "template"
                           else "Template (no AI available).")
    st.caption("Alert level: GloFAS river flow on each town's river against its own 2-year flood and July 2021 peak "
               "(impact forecast, src/build_ml2.py). Levels never drop during a replay; daily flows, so times are "
               "accurate to about ±12 h. A model replay, not official warnings.")


st.fragment(board, run_every=1.5 if c["playing"] else None)()
