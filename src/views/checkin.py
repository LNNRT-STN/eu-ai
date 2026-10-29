"""Safe check-in and door-knock list. Residents of the 2021 flood zone report "I have left, I'm at X" (or "I need help
leaving") by street and house number; fire crews see every home in the water with no news, those who asked for help
first, then single-storey homes. Addresses: OpenStreetMap matched to GHS-OBAT buildings (notebooks/addresses.py, ODbL).
No names or phone numbers are stored: only the address, where people are and how many. Check-ins stay on this machine
(src/live.py, data/live.db, gitignored). The July 2021 replay adds simulated check-ins, labelled, removable in one click."""
import json
from datetime import datetime

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
import live
from core import fmt

COLS = ["when", "municipality", "door", "status", "where", "people", "drill"]
WHERE = ["A shelter", "Family or friends", "A spare bed offered by a resident", "Elsewhere, outside the flood zone"]

towns = anna.load()[1]
bus = anna.load_moves()[1]


@st.cache_data
def doors():
    """One row per home address in the 2021 water; homes without an OSM address keep their building id."""
    a = pd.read_parquet(core.DATA / "addresses.parquet")
    a = a[a.use == 1].copy()
    a["door"] = a.label.where(a.label.astype(bool), "No address · " + a.bid)
    a.loc[a.label.astype(bool) & a.street.isna(), "door"] = "House no. " + a.housenumber + " (no street name)"
    a["single"] = (a.storeys == 1) & (a.height_m != 2.5)
    return (a.groupby(["municipality", "door"], as_index=False)
            .agg(street=("street", "first"), number=("housenumber", "first"), lon=("lon", "mean"), lat=("lat", "mean"),
                 buildings=("bid", "size"), single=("single", "any"), has_address=("label", lambda x: x.iloc[0] != "")))


EDGES = json.loads((core.DATA / "evac_edges.geojson").read_text())


D = doors()
munis = (towns[towns.variant == "worst"].sort_values("people", ascending=False).municipality
         .drop_duplicates().loc[lambda m: m.isin(D.municipality)].tolist())

st.title("Safe check-in")
st.caption("Residents say they have left. Fire crews see who has not, and go there first.")
muni = st.session_state.get("town") if st.session_state.get("town") in munis else munis[0]
st.header(anna.town(muni))
here = D[D.municipality == muni]
me, crew = st.tabs(["I have left my home", "Door-knock list for crews"])

# ------------------------------------------------------------------ residents
with me:
    streets = sorted(here.loc[here.has_address, "street"].dropna().unique())
    if not streets:
        st.info("No street addresses in OpenStreetMap for the flooded homes here. Call the municipal help line instead.")
    else:
        c1, c2 = st.columns([3, 1])
        street = c1.selectbox("Your street", streets, index=None, placeholder="Type to search")
        nums = sorted(here.loc[here.street == street, "number"].dropna().unique(),
                      key=lambda n: (int("".join(filter(str.isdigit, n)) or 0), n)) if street else []
        number = c2.selectbox("Number", nums, index=None, placeholder="No.", disabled=not street)
        help_ = st.toggle("I am still at home and need help to leave", key="ci_help")
        shelters = bus[bus.municipality == muni].sort_values("people", ascending=False).shelter.tolist()
        where = None
        if not help_:
            where = st.radio("Where are you now?", WHERE, horizontal=True, key="ci_where")
            if where == "A shelter" and shelters:
                where = st.selectbox("Which shelter?", shelters, key="ci_shelter")
        people = st.number_input("How many people from this home are with you?" if not help_ else
                                 "How many people need help?", 1, 20, 1)
        if st.button("Send", type="primary", disabled=not (street and number), icon=":material/send:"):
            door = f"{street} {number}"
            row = dict(when=datetime.now().isoformat(timespec="minutes"), municipality=muni, door=door,
                       status="needs help" if help_ else "safe", where=where or "", people=int(people), drill=False)
            live.add_checkin(**{k: row[k] for k in ("municipality", "door", "status", "where", "people", "drill")})
            if help_:
                st.error(f"Help request sent for {door}: it is now first on the crews' list. If water is rising, go "
                         "upstairs and call 112.")
            else:
                st.success(f"Thank you. {door} is marked as left, so crews can skip it.")
    st.caption("No name or phone number is stored. In a real roll-out this form is reached from the link in the "
               "BE-Alert or NL-Alert SMS, or by phone through the municipal help line.")

# ------------------------------------------------------------------ crews


def crews():
    ci = live.checkins(muni)
    last = (ci.sort_values("when").groupby("door").last() if len(ci)
            else pd.DataFrame(columns=COLS + ["sim"]).set_index("door"))
    L = here.merge(last[["status", "where", "people", "drill", "sim"]], left_on="door", right_index=True, how="left")
    L["status"] = L.status.fillna("no news")
    L["alert"] = "no feed yet"
    order = {"needs help": 0, "no news": 1, "safe": 2}
    L = L.assign(o=L.status.map(order), s=~L.single).sort_values(["o", "s", "street", "door"]).reset_index(drop=True)
    simulated = bool(len(ci) and (ci.drill.astype(bool) | ci.sim.astype(bool)).any())
    if simulated:
        st.warning("Includes simulated check-ins from the July 2021 replay, not real ones.", icon=":material/science:")
    n = L.status.value_counts()
    single_open = int((L.single & (L.status == "no news")).sum())
    c = st.columns(3)
    c[0].metric("Need help: go first", fmt(n.get("needs help", 0)), border=True)
    c[1].metric("No news", fmt(n.get("no news", 0)), border=True, help=f"{fmt(single_open)} of them single-storey")
    c[2].metric("Have left", fmt(n.get("safe", 0)), border=True)
    color = {"needs help": core.rgb(core.EVACUATE), "no news": core.rgb("#c93400", 210), "safe": core.rgb(core.SHELTER, 150)}
    pts = L.assign(c=L.status.map(color), tname=L.door,
                   tinfo=[f"{s}{' · single-storey' if one else ''}" for s, one in zip(L.status, L.single)])
    left, right = st.columns([3, 2], gap="small")
    with left:
        st.pydeck_chart(pdk.Deck(
            layers=[pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_fill_color="c", get_radius=4,
                              radius_units="'pixels'", pickable=True)],
            initial_view_state=pdk.ViewState(longitude=here.lon.median(), latitude=here.lat.median(), zoom=14),
            map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "<b>{tname}</b><br/>{tinfo}"},
            views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=440)
        st.caption(":red[●] Needs help · :orange[●] No news · "
                   ":green[●] Has left")
    with right:
        todo = L[L.status != "safe"]
        st.dataframe(todo[["door", "status", "single", "alert"]], hide_index=True, height=440, column_config={
            "door": st.column_config.TextColumn("Address", width="medium"),
            "status": st.column_config.TextColumn("Status", width="small"),
            "single": st.column_config.CheckboxColumn("1 storey", width="small"),
            "alert": st.column_config.TextColumn("Reached by alert", width="small",
                                                 help="Would show SMS delivery or call result; no feed connected")})
        st.download_button("Download the list for crews", todo[["door", "status", "single", "lat", "lon"]].to_csv(index=False),
                           file_name=f"door_knock_{anna.town(muni).replace(' ', '_')}.csv", mime="text/csv",
                           icon=":material/download:")
    # road closures: crews close and reopen; the crisis room map shows them
    st.markdown("**Roads closed**")
    cl = live.closures()
    cl = cl[cl.municipality == muni]
    for r in cl.itertuples():
        a, b = st.columns([5, 1])
        a.markdown(f"**{r.name or r.osm_id}** · {'auto, in the 2021 water' if r.auto else 'by ' + r.by}"
                   f"{' · ' + r.note if r.note else ''}")
        b.button("Reopen", key=f"reopen{r.id}", on_click=live.reopen, args=(r.id,))
    if cl.empty:
        st.caption("No road closed in this town.")
    roads = [f["properties"]["name"] for f in EDGES["features"] if f["properties"]["municipality"] == muni
             and f["properties"]["name"]]
    with st.form(f"close_{muni}", border=False):
        a, b, c3 = st.columns([3, 2, 1], vertical_alignment="bottom")
        road = a.selectbox("Road", list(dict.fromkeys(roads)), index=None, accept_new_options=True,
                           placeholder="Busiest evacuation roads first, or type a name")
        note = b.text_input("Why", placeholder="e.g. bridge under water")
        if c3.form_submit_button("Close road", icon=":material/block:") and road:
            f = next((f for f in EDGES["features"] if f["properties"]["name"] == road), None)
            xy = f["geometry"]["coordinates"][0] if f else [None, None]
            if isinstance(xy[0], list):
                xy = xy[0]
            live.close_road(road, muni, by="fire crew", note=note, lon=xy[0], lat=xy[1])
            st.rerun()
    no_addr = int((~here.has_address).sum())
    st.caption(f"{fmt(len(here))} doors to check: {fmt(int(here.buildings.sum()))} homes in the 2021 water, grouped by "
               f"address (several buildings can share one); {fmt(no_addr)} have no OpenStreetMap address and are "
               "listed by map point" + (" (most Venlo-area homes)" if here.municipality.str.contains("(NL)", regex=False).any()
                                        else "") + ". 'Reached by alert': BE-Alert SMS delivery reports or "
            "call results would plug in here; cell broadcast cannot confirm delivery. Order: help requests, then homes "
            "with no news, single-storey first.")


with crew:
    if st.button("Clear simulated check-ins", icon=":material/restart_alt:"):
        live.clear_drill(muni)
    st.fragment(crews, run_every=3 if live.clock()["playing"] else None)()
