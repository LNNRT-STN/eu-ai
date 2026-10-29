"""Crisis room: the whole region, live. A replay of July 2021 (or the live forecast) drives each town's alert level;
at each rise the tool queues briefings for the mayor and the district fire brigade (drafted by Claude from the tool's
numbers), simulated check-ins arrive, and roads in the 2021 water close. State: src/live.py (data/live.db).
Status uses the highest river flow reached so far (it never drops in a replay); daily GloFAS flows are placed at noon
and interpolated, so times are accurate to about ±12 h."""
import json

import pandas as pd
import shapely
import streamlit as st
from shapely.geometry import mapping, shape

import anna
import core
import live
from regionmap import ATTRIBUTION, region_map
from core import about, fmt

COL = {"evacuate": "#d70015", "warn": "#f2994a", "watch": "#f2c94c", "none": "#8e8e93"}
WORD = {"evacuate": "Evacuate", "warn": "Warn", "watch": "Watch", "none": "Normal"}
towns = anna.load()[1]
T = towns[towns.variant == "worst"].drop_duplicates("municipality").set_index("municipality")


@st.cache_data
def water_by_town():
    """Each area's 2021 water cut by the real municipality outlines (Eurostat GISCO LAU), one feature per town."""
    flood = anna.load()[4]
    outl = {f["properties"]["municipality"]: shapely.make_valid(shape(f["geometry"]))
            for f in json.loads((core.DATA / "municipality_outlines.geojson").read_text())["features"]}
    feats = []
    for area in anna.AREA:
        water = shapely.make_valid(shape(flood[(area, "worst")]["features"][0]["geometry"]))
        for m in T.index[T.area == area]:
            if m in outl:
                part = water.intersection(outl[m]).simplify(.0001)
                if not part.is_empty:
                    feats.append({"type": "Feature", "geometry": mapping(part), "properties": {"municipality": m}})
    return {"type": "FeatureCollection", "features": feats}

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
        d = d.sort_values("level").drop_duplicates("municipality", keep="last")  # one row per town, worst status
        cl = live.closures().dropna(subset=["lon"])
        sel = region_map(dict(
            towns=[dict(municipality=r.municipality, label=anna.town(r.municipality), lon=r.lon, lat=r.lat,
                        status=r.status if r.status in COL else "none", people=float(r.people),
                        people_expected=float(r.people_expected or 0), modelled=r.area in anna.MODELLED)
                   for r in d.itertuples()],
            flood=water_by_town(),
            closures={"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                 "properties": {"name": r.name or ""}} for r in cl.itertuples()]},
            selected=st.session_state.get("cr_sel")), key="crisis_map", height=470)
        if sel and sel.get("selected") and sel.get("clicks") != st.session_state.get("cr_clicks"):
            st.session_state.cr_clicks = sel["clicks"]
            st.session_state.cr_sel = st.session_state.town = st.session_state._town = sel["selected"]
        if st.session_state.get("cr_sel"):
            a, b = st.columns([3, 1])
            a.page_link("views/evacuate.py", label=f"Open the plan for {anna.town(st.session_state.cr_sel)}",
                        icon=":material/arrow_forward:")
            b.button("Whole region", on_click=lambda: st.session_state.update(cr_sel=None), width="stretch")
        st.caption(":red[●] Evacuate · :orange[●] Warn · :yellow[●] Watch · :blue[●] Normal · dashed edge: modelled "
                   "(Vesdre) · barrier: road closed · number: people in the 2021 water. Click a town to fly in. " + ATTRIBUTION)
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
