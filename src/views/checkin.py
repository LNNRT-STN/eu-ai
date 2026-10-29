"""Safe check-in and door-knock list. Residents of the 2021 flood zone report "I have left, I'm at X" (or "I need help
leaving") by street and house number; fire crews see every home in the water with no news, those who asked for help
first, then single-storey homes. Addresses: OpenStreetMap matched to GHS-OBAT buildings (notebooks/addresses.py, ODbL).
No names or phone numbers are stored: only the address, where people are and how many. Check-ins stay on this machine
(data/checkins.csv, gitignored). A drill fills simulated check-ins, tagged DRILL, removable in one click."""
from datetime import datetime

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import fmt

FILE = core.DATA.parents[1] / "data" / "checkins.csv"
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


def checkins():
    try:
        return pd.read_csv(FILE)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=COLS)


def save(df):
    FILE.parent.mkdir(exist_ok=True)
    df.to_csv(FILE, index=False)


D = doors()
munis = (towns[towns.variant == "worst"].sort_values("people", ascending=False).municipality
         .drop_duplicates().loc[lambda m: m.isin(D.municipality)].tolist())

core.header("Safe check-in", "Residents say they have left. Fire crews see who has not, and go there first.")
st.space("small")
muni = st.selectbox("Town", munis, format_func=anna.town, key="ci_town")
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
            save(pd.concat([checkins(), pd.DataFrame([row])]))
            if help_:
                st.error(f"Help request sent for {door}: it is now first on the crews' list. If water is rising, go "
                         "upstairs and call 112.")
            else:
                st.success(f"Thank you. {door} is marked as left, so crews can skip it.")
    st.html("<p class='asof'>No name or phone number is stored. In a real roll-out this form is reached from the link in "
            "the BE-Alert or NL-Alert SMS, or by phone through the municipal help line.</p>")

# ------------------------------------------------------------------ crews
with crew:
    ci = checkins()
    last = (ci[ci.municipality == muni].sort_values("when").groupby("door").last()
            if len(ci) else pd.DataFrame(columns=COLS).set_index("door"))
    L = here.merge(last[["status", "where", "people", "drill"]], left_on="door", right_index=True, how="left")
    L["status"] = L.status.fillna("no news")
    L["alert"] = "no feed yet"
    order = {"needs help": 0, "no news": 1, "safe": 2}
    L = L.assign(o=L.status.map(order), s=~L.single).sort_values(["o", "s", "street", "door"]).reset_index(drop=True)
    is_drill = bool(len(last) and last.drill.fillna(False).astype(bool).any())

    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button("Run a drill", icon=":material/play_arrow:", help="Simulate check-ins: about 60 % left, 3 % need help"):
        rng = np.random.default_rng()
        r = rng.random(len(here))
        sim = here[r < .63].reset_index(drop=True)
        status = np.where(r[r < .63] < .03, "needs help", "safe")
        rows = pd.DataFrame(dict(when=datetime.now().isoformat(timespec="minutes"), municipality=muni,
                                 door=sim.door.values, status=status, where=np.where(status == "safe", "DRILL", ""),
                                 people=1, drill=True))
        save(pd.concat([checkins(), rows]))
        st.rerun()
    if b2.button("Reset drill", icon=":material/restart_alt:", disabled=not is_drill):
        c = checkins()
        save(c[~c.drill.astype(bool)])
        st.rerun()
    if is_drill:
        st.warning("DRILL: the check-ins below are simulated, not real.", icon=":material/science:")

    n = L.status.value_counts()
    single_open = int((L.single & (L.status == "no news")).sum())
    st.html("<div class='ev-n'>"
            f"<div><b style='color:{core.EVACUATE}'>{fmt(n.get('needs help', 0))}</b><span><i>need help</i>: go "
            "first</span></div>"
            f"<div><b style='color:{core.PEOPLE}'>{fmt(n.get('no news', 0))}</b><span><i>no news</i>, "
            f"{fmt(single_open)} of them single-storey</span></div>"
            f"<div><b style='color:{core.SHELTER}'>{fmt(n.get('safe', 0))}</b><span><i>have left</i></span></div></div>")
    st.space("small")
    color = {"needs help": core.rgb(core.EVACUATE), "no news": core.rgb(core.PEOPLE, 210), "safe": core.rgb(core.SHELTER, 150)}
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
        core.legend(core.swatch(core.EVACUATE, "Needs help", True) + core.swatch(core.PEOPLE, "No news", True)
                    + core.swatch(core.SHELTER, "Has left", True))
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
    no_addr = int((~here.has_address).sum())
    st.html(f"<p class='asof'>{fmt(len(here))} homes in the 2021 water here; {fmt(no_addr)} have no OpenStreetMap address "
            "and are listed by map point (Venlo area: most homes). 'Reached by alert': BE-Alert SMS delivery reports or "
            "call results would plug in here; cell broadcast cannot confirm delivery. Order: help requests, then homes "
            "with no news, single-storey first.</p>")
