"""Crisis room: the whole region, live, in three tabs: Live board (this file), Priorities (views/first_action.py and
views/briefing.py) and Rivers (views/rivers.py). A replay of July 2021 (or the live forecast) drives each town's alert level;
at each rise the tool queues briefings for the mayor and the district fire brigade (drafted by Claude from the tool's
numbers), simulated check-ins arrive, and roads in the 2021 water close. State: src/live.py (data/live.db).
Status uses the highest river flow reached so far (it never drops in a replay); daily GloFAS flows are held for their
whole day, so the replay gives the day, not the hour."""
import json
import re

import pandas as pd
import shapely
import streamlit as st
from shapely.geometry import mapping, shape

import anna
import core
import live
from views import briefing, first_action, rivers
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

# the scenario player is in every role's sidebar (dashboard.py)
c = live.clock()


# the absorbed pages draw with core's grouped-list classes; take those, not its page padding or sidebar rules
st.html(re.sub(r"\.block-container\{[^}]*\}|\[data-testid=st(Sidebar|SidebarNav|NavSectionHeader)\][^{]*\{[^}]*\}", "",
               core.CSS))
ROWS = {"evacuate": "red", "warn": "orange", "watch": "yellow", "none": "gray"}


def when(t, mode):
    return f"{live.drill(t):%a %d %b}" if mode == "replay" else f"{pd.Timestamp(t):%d %b %H:%M}"


def coming(t):
    """What the 2021 flows still hold after t: the towns not yet at evacuate that will get there, and on which day."""
    tm = live._replay()["times"]
    ahead = tm.t_evacuate[tm.t_evacuate > t].dropna()
    if ahead.empty:
        st.caption("No further town reaches evacuate in the July 2021 flows.")
        return
    first = ahead.min()
    by = ahead.dt.normalize().value_counts().sort_index()
    days = " · ".join(f"{live.drill(d):%a %-d %b}: {n}" for d, n in by.items())
    st.warning(f"**A flood like July 2021 is coming. {len(ahead)} more towns reach evacuate, the first on "
               f"{live.drill(first):%A %-d %B}.** Towns per day: {days}. A replay of the 2021 forecast, not an "
               "official warning.", icon=":material/flood:")


def board():
    c = live.advance()
    t = c["t"]
    live.tick(t)
    s = live.towns_status(t)
    m = live.summary(t)
    if c["mode"] == "replay":
        st.subheader(f"{live.drill(t):%a %d %b %Y, %H:%M} · replay of the 2021 forecast, arriving now")
        coming(t)
    else:
        st.subheader(f"{t:%a %d %b %Y, %H:%M} · live forecast")

    sim = c["mode"] == "replay"
    k = st.container(horizontal=True, gap="small")  # wraps on phones instead of stacking six rows
    k.metric("Towns to evacuate", m["evacuate"], border=True, width=165,
             help=f"{m['evacuate_under_50']} of them had fewer than 50 residents in the mapped 2021 water.")
    k.metric("Towns warned", m["warn"], border=True, width=130)
    k.metric("People to move", about(m["people_evacuate"]), border=True, width=185,
             delta=f"+{about(m['people_evacuate_modelled'])} modelled" if m["people_evacuate_modelled"] else None,
             delta_color="off", delta_arrow="off",
             help="Residents inside the 2021 satellite flood of the towns at 'evacuate' (a floor). Below it, kept "
                  "apart: residents in the modelled Vesdre zone (EFAS 500-year), which the satellite did not map")
    hh = "Check-ins per home" + (", simulated in the replay." if sim else ".")
    k.metric("Homes safe", fmt(m["safe"]), border=True, width=140, help=hh)
    k.metric("Homes need help", fmt(m["needs_help"]), border=True, width=170, help=hh)
    k.metric("Roads closed", m["roads_closed"], border=True, width=130)
    st.caption("People to move: observed and modelled (Vesdre) kept apart, never added."
               + (" Homes: simulated check-ins." if sim else ""))

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
            st.session_state.cr_sel = sel["selected"]
            if T.people.get(sel["selected"], 0) >= 10:  # only towns the sidebar Town picker lists
                st.session_state.town = st.session_state._town = sel["selected"]
        if st.session_state.get("cr_sel"):
            a, b = st.columns([3, 1])
            sel_t = st.session_state.cr_sel
            if T.people.get(sel_t, 0) >= 10:  # the Town plan covers towns with 10 or more people in the water
                a.page_link("views/evacuate.py", label=f"Open the plan for {anna.town(sel_t)}",
                            icon=":material/arrow_forward:")
            else:
                a.caption(f"{anna.town(sel_t)}: under 10 people in the 2021 water, no town plan.")
            b.button("Whole region", on_click=lambda: st.session_state.update(cr_sel=None), width="stretch")
        st.caption(":red[●] Evacuate · :orange[●] Warn · :yellow[●] Watch · :blue[●] Normal · dashed edge: modelled "
                   "(Vesdre) · click a town to fly in",
                   help="Barrier: road closed. Number: people in the 2021 water (Vesdre: in the modelled zone). "
                        + ATTRIBUTION)
    with right:
        ev = live.events().tail(6).iloc[::-1]
        st.markdown("**Latest**", help="The last alert changes, newest first. Levels never drop during a replay.")
        if ev.empty:
            st.caption("Nothing yet. Press Play in the sidebar.")
        else:
            st.markdown("  \n".join(f"`{when(r.t, c['mode'])}` :{ROWS.get(r.to, 'gray')}[●] **{anna.town(r.municipality)}**"
                                    f" → {WORD.get(r.to, r.to)}" for r in ev.itertuples()))
        ob = live.outbox().tail(8).iloc[::-1]
        st.markdown(f"**Briefing drafts** · {len(live.outbox())} in the outbox, not sent",
                    help="One briefing for the mayor and one for the district fire brigade each time a town's alert "
                         "rises. Drafted by Claude from the tool's numbers (words only; every figure comes from the "
                         "tool); a template when no AI is available.")
        if ob.empty:
            st.caption("Briefings for mayors and fire brigades appear here when a town's alert rises.")
        else:
            lab = {r.id: f"{when(r.t, c['mode'])} · {r.recipient}" for r in ob.itertuples()}
            rid = st.selectbox("Draft", list(lab), format_func=lab.get, key="cr_draft",
                               label_visibility="collapsed") or ob.id.iloc[0]
            with st.container(border=True, height=230):
                st.write(live.report(rid))
            if ob.set_index("id").source.get(rid) == "template":
                st.caption("Template (no AI available).")


# 2021 for comparison: sourced times from docs/TIMELINE_2021.md (all verified in the cited document)
JRC = "https://european-flood.emergency.copernicus.eu/sites/default/files/2023-12/JRC135679_CEMS_EFAS_DetailedAssessmentReport_RhineMeuseFloodsJuly2021_FINAL.pdf"
Y2021 = [("ahr", "Ahr", f"13 Jul 11:25, flash-flood notice for the Koblenz region ([JRC]({JRC}))",
          "14 Jul 23:09, Kreis Ahrweiler: leave 50 m either side of the Ahr "
          "([Landtag RLP](https://dokumente.landtag.rlp.de/landtag/vorlagen/5776-V-18.pdf))"),
         ("vesdre", "Vesdre", f"13 Jul 11:26, flash-flood notice for Liège province ([JRC]({JRC}))",
          "14 Jul 17:57, Province of Liège: general order for the Vesdre valley ([Walloon Parliament](https://www."
          "wallonie.be/sites/default/files/2022-11/Inondations%20rapport%20de%20la%20commission%20parlementaire.pdf))"),
         ("erftstadt", "Erft", f"None received: NRW was not yet an EFAS partner ([JRC]({JRC}))",
          "15 Jul about 08:10, Erftstadt: evacuate Blessem and Bliesheim "
          "([Stadt Erftstadt](https://www.radioerft.de/files/pdf2/pm-stellungnahme-zur-wdr-berichterstattung-am-23.08.2021.pdf))")]


def then_2021():
    st.subheader(":violet[:material/history:] July 2021: when the orders came",
                 help="EFAS notices and the first evacuation orders of 2021, against the first day the tool puts a "
                      "town of that river at evacuate. Sources and more times: docs/TIMELINE_2021.md.")
    st.caption("Tool column: the day, from flows computed afterwards; not the forecast available at the time.")
    # the day whose daily flow (placed at noon) first puts a town of the river at evacuate; the hourly replay
    # interpolates towards the next day's mean, which would claim hours the daily data cannot give
    rp, area = live._replay(), live._towns().area.values
    noon = [i for i, t in enumerate(rp["index"]) if t.hour == 12]
    day = {a: next((rp["index"][i] for i in noon if (rp["status"][i][area == a] == "evacuate").any()), None)
           for a, *_ in Y2021}
    # a four-column table cannot fit 390 px: it keeps its width and scrolls sideways inside its own box
    st.html("<style>.st-key-y2021{overflow-x:auto}.st-key-y2021 table{min-width:640px}</style>")
    st.container(key="y2021").markdown("| River | EFAS warned | 2021 evacuation order | Tool: river at evacuate level (replay day) |\n"
                "|---|---|---|---|\n" +
                "\n".join(f"| {name} | {efas} | {order} | " + (f"{day[a]:%d Jul} ({live.drill(day[a]):%a %d %b})"
                                                              if day[a] is not None else "not reached") + " |"
                           for a, name, efas, order in Y2021))


st.title("Crisis room")
t1, t2, t3 = st.tabs([":red[:material/crisis_alert:] Live board", ":violet[:material/priority_high:] Priorities",
                      ":blue[:material/water:] Rivers"])
with t1:
    st.fragment(board, run_every=1.5 if c["playing"] else None)()
    if c["mode"] == "replay":
        st.space("small")
        then_2021()
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(
            "- **Alert level:** GloFAS river flow on each town's river against its own 2-year flood and July 2021 "
            "peak (impact forecast, src/build_ml2.py). Status uses the highest flow reached so far: levels never drop "
            "during a replay.\n"
            "- **Replay of the 2021 forecast:** it steps on daily modelled flows (GloFAS reanalysis, computed afterwards), so it "
            f"gives the day, not the hour. Shown as if it began on {live.drill(live.START):%a %d %b %Y}: the dates are "
            "moved, the flows are those of 12-17 July 2021. A model replay, not official warnings.\n"
            "- **People to move:** residents inside the 2021 satellite flood of the towns at evacuate, a floor. The "
            "Vesdre valley has no satellite map: its residents come from the EFAS 500-year model and are shown apart.\n"
            "- **Homes safe / need help:** check-ins per home; in the replay they are simulated.\n"
            "- **Briefings:** queued at each rise for the mayor and the district fire brigade; Claude writes the words, "
            "every figure comes from the tool. Nothing is sent.\n"
            "- **July 2021 comparison:** the first day whose mean river flow puts a town of that river at evacuate. "
            "Times and sources: docs/TIMELINE_2021.md.\n"
            f"- **Map:** {ATTRIBUTION}")
with t2:
    first_action.render()
    briefing.render()
    st.space("small")
    with st.expander("How this is computed", icon=":material/info:"):
        first_action.how()
        briefing.how()
with t3:
    rivers.render()
