"""Resident: type your street, pick your house, see at once whether to leave and where to go; tell the fire brigade
you have left or need help; or offer a bed. Three tabs, the only page the Resident role sees (no sidebar Town picker:
the town comes from the address typed in the first tab, shared through st.session_state.res_home).
Homes in the 2021 water: outputs/data/addresses.parquet (OSM addresses matched to GHS-OBAT buildings). Where to go:
the town's 10 km shelter plan (bus_plan.csv), nearest shelter that takes people from this town; walking or bus by
straight-line distance × 1.3 (road / straight ratio measured 1.2-1.4 in notebooks/evac_sim.py). Spare beds offered
by residents: data/host_offers.csv. Nothing typed in the address box is stored; a check-in stores only the address,
where people are and how many (src/live.py)."""
import json
import math
import re

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
import live
from views import checkin, host

WALK_KMH, BUS_KMH, ROAD = 4, 30, 1.3


@st.cache_data
def homes():
    a = pd.read_parquet(core.DATA / "addresses.parquet")
    a = a[(a.use == 1) & a.label.astype(bool) & a.street.notna()].copy()
    a["town"] = a.municipality.map(anna.town)
    a["single"] = (a.storeys == 1) & (a.height_m != 2.5)
    return (a.groupby(["municipality", "town", "street", "housenumber"], as_index=False)
            .agg(lon=("lon", "mean"), lat=("lat", "mean"), single=("single", "any"), area=("area", "first")))


@st.cache_data
def shelter_town():
    """Shelter name → its municipality (outputs/data/shelters.geojson), so an opaque OSM name gets a place."""
    g = json.loads((core.DATA / "shelters.geojson").read_text())["features"]
    return {f["properties"]["name"]: f["properties"]["muni"] for f in reversed(g) if f["properties"].get("muni")}


@st.cache_data
def addresses():
    """'Street 12, Town' for every home in the water, for the address box's autocomplete."""
    H = homes()
    return sorted(H.street + " " + H.housenumber + ", " + H.town)


EXAMPLES = {  # demo addresses for the address box, one per kind of answer
    "Ahrstraße 28, Ahrbrück": "Ahr, in the 2021 water",
    "Ahruferstraße 29, Bad Neuenahr-Ahrweiler": "Ahr, single storey",
    "Avenue Albert Ier 3, Pepinster": "Vesdre, modelled",
    "Quai Saint-Paul de Sinçay 126, Liège": "Liège",
    "Aachener Straße 10, Schleiden": "Schleiden",
    "An der Schwarzau 11, Erftstadt": "Erftstadt",
    "Kirchstraße 3, Altenahr": "dry in 2021",
}
KIND = {"civic":"civic building", "school": "school", "sports hall": "sports hall"}
LEAVE, LEFT, BED = ("Do I need to leave?", "I have left / I need help", "Offer a bed")


def norm(x):
    return x.casefold().replace("ß", "ss").strip()


def method(modelled=False):
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(
            "- **Homes in the water.** Homes inside the July 2021 satellite flood map" + (
                " (here the EFAS 500-year model, as the satellite missed the Vesdre)" if modelled else
                " (and the modelled Vesdre zone)") + " that have an OpenStreetMap address. The satellite missed water "
            "in narrow valleys, so a home not on the list is not guaranteed safe.\n"
            f"- **Where to go.** The nearest candidate shelter that takes people from your town in the 10 km shelter "
            "plan: a school, sports hall or civic building that stayed dry in 2021 and in the 100-year model. Not an "
            "official shelter: follow the municipality's instructions.\n"
            f"- **How long.** Road distance taken as straight line × {ROAD}; on foot up to 1.5 km at {WALK_KMH} km/h, "
            f"further by bus or car at {BUS_KMH} km/h. A minimum.\n"
            "- **Upper floor.** Single-storey homes from the GHS-OBAT building heights.\n"
            "- **Sources.** Addresses: OpenStreetMap (ODbL). Buildings: GHS-OBAT. Map: © CARTO, © OpenStreetMap "
            "contributors.")


def alert(muni, town):
    """Has the alert come? The town's status at the scenario clock (sidebar), so a resident sees the replay too."""
    k = live.clock()
    S = live.towns_status().sort_values("level").drop_duplicates("municipality", keep="last")  # worst status
    s = S.set_index("municipality").status.get(muni, "none")
    when = (f"Replay of the 2021 forecast, {live.drill(k['t']):%a %-d %b, %H:%M}" if k["mode"] == "replay"
            else f"Live forecast, {k['t']:%a %-d %b, %H:%M}")
    if s == "evacuate":
        st.error(f"**{when}: {town} is told to evacuate. Leave now.**", icon=":material/directions_run:")
    elif s == "warn":
        st.warning(f"**{when}: {town} is warned. Pack and get ready to leave.**", icon=":material/notifications_active:")
    elif s == "watch":
        st.info(f"**{when}: the river near {town} is rising.** No alert yet; stay tuned.", icon=":material/water:")
    else:
        st.caption(f"{when}: no alert for {town}." + (" No river point near this town in our data."
                                                       if s == live.NO_POINT else ""))


def lookup():
    """Address → verdict, then where to go. Sets st.session_state.res_home for the other tabs."""
    H = homes()
    # one box that autocompletes: demo examples first, then every home in the water; any other address can be typed
    q = st.selectbox("Your address", list(EXAMPLES) + [a for a in addresses() if a not in EXAMPLES], index=None,
                     format_func=lambda a: f"{a}  ·  {EXAMPLES[a]}" if a in EXAMPLES else a,
                     accept_new_options=True, key="res_q", placeholder="Start typing, or pick an example",
                     help="Street and number, and the town if you like. Nothing you type here is stored.") or ""

    # People type whole addresses ("Ahrstraße 28, Ahrbrück", "5 rue de la Station"): split off the number and the
    # town, or the street would not match and the page would wrongly say the home was dry.
    n = re.search(r"\b\d+\s?[a-zA-Z]?\b", q)
    typed_num = n.group().replace(" ", "").lower() if n else None
    parts = [p.strip() for p in ((q[:n.start()] + q[n.end():]) if n else q).split(",") if p.strip()]
    q_street, q_town = (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")
    hit = H[H.street.map(norm).str.contains(norm(q_street), regex=False)] if len(q_street) >= 3 else H.iloc[0:0]
    if q_town and hit.town.map(norm).str.contains(norm(q_town), regex=False).any():
        hit = hit[hit.town.map(norm).str.contains(norm(q_town), regex=False)]
    streets = (hit.drop_duplicates(["street", "town"]).assign(k=lambda d: d.street + ", " + d.town)
               .sort_values("k").k.tolist()[:30])
    st.session_state.res_home = None

    if len(q_street) >= 3 and not streets:
        st.success("**Your street was not in the 2021 water.** You are most likely outside it. Stay alert to official "
                   "warnings.", icon=":material/check_circle:")
        st.markdown(f":green[:material/bed:] If your home stayed dry, you can offer a bed to a neighbour who has to "
                    f"leave: see **{BED}** above.")
        st.caption("Not on the list does not guarantee safety: the satellite missed water in narrow valleys.")
        method()
        return
    if not streets:
        return

    c1, c2 = st.columns([3, 1])
    # with a typed number, start on the first street-and-town that has that number
    has = [i for i, k in enumerate(streets) if typed_num and
           (hit[(hit.street + ", " + hit.town) == k].housenumber.str.replace(" ", "").str.lower() == typed_num).any()]
    street_town = c1.selectbox("Your street", streets, index=has[0] if has else 0, label_visibility="collapsed")
    street, town = street_town.rsplit(", ", 1)
    nums = H[(H.street == street) & (H.town == town)]
    nums = nums.assign(o=nums.housenumber.str.extract(r"(\d+)", expand=False).fillna(0).astype(int)).sort_values(
        ["o", "housenumber"])
    numbers = nums.housenumber.tolist()
    known = [i for i, x in enumerate(numbers) if typed_num and str(x).replace(" ", "").lower() == typed_num]
    num = c2.selectbox("Number", numbers, index=known[0] if known else (None if typed_num else 0),
                       placeholder="Number", label_visibility="collapsed")
    if num is None:
        st.info(f"Number {typed_num} is not among the homes in the 2021 water on {street}. Pick your number if it is "
                "listed; if not, your home was most likely outside the water. Follow official warnings.",
                icon=":material/info:")
        return
    h = nums[nums.housenumber == num].iloc[0]
    st.session_state.res_home = dict(municipality=h.municipality, street=street, number=num)
    modelled = h.area in anna.MODELLED

    # where to go: shelters this town's people are sent to in the 10 km plan, nearest to this home first
    bus = anna.load_moves()[1]
    plan = bus[bus.municipality == h.municipality].groupby(["shelter", "cat", "s_lon", "s_lat"],
                                                           as_index=False).people.sum()
    plan = plan[plan.people >= .5]
    plan["km"] = core.km(h.lon, h.lat, plan.s_lon, plan.s_lat) * ROAD
    go = plan.nsmallest(1, "km").iloc[0] if len(plan) else None

    st.error(f"**{street} {num}, {town} was in the 2021 water{' (modelled)' if modelled else ''}. Leave when the "
             "alert comes, before the water rises.**" + (" Your home has no upper floor to escape to: leave early."
                                                         if h.single else ""), icon=":material/warning:")
    st.fragment(alert, run_every=3 if live.clock()["playing"] else None)(h.municipality, town)
    if go is not None:
        walk = go.km <= 1.5
        mins = go.km / (WALK_KMH if walk else BUS_KMH) * 60
        c = st.columns(3)
        where = shelter_town().get(go.shelter)
        c[0].metric(":green[:material/home_health:] Go to", go.shelter, border=True, delta_color="off",
                    delta_arrow="off", delta=KIND.get(go["cat"], go["cat"]) + (f", {anna.town(where)}" if where else ""),
                    help="Candidate shelter from OpenStreetMap, dry in 2021: not an official shelter")
        c[1].metric(":blue[:material/directions_walk:] How" if walk else ":blue[:material/directions_bus:] How",
                    "On foot" if walk else "By bus or car", border=True,
                    help="On foot up to 1.5 km by road; further away, the municipality's buses (book a seat via the "
                         "help line).")
        c[2].metric(":blue[:material/schedule:] About", f"{mins:.0f} min", border=True,
                    help=f"{go.km:.1f} km by road (straight line × {ROAD}); "
                         f"{'walking ' + str(WALK_KMH) if walk else 'bus ' + str(BUS_KMH)} km/h. A minimum.")
        pts = pd.DataFrame({"lon": [h.lon, go.s_lon], "lat": [h.lat, go.s_lat],
                            "c": [core.rgb(core.EVACUATE), core.rgb(core.SHELTER)]})
        leg = pd.DataFrame([{"a": [h.lon, h.lat], "b": [go.s_lon, go.s_lat]}])
        st.pydeck_chart(pdk.Deck(
            layers=[pdk.Layer("LineLayer", leg, get_source_position="a", get_target_position="b",
                              get_color=[29, 29, 31, 160], get_width=3, width_units="'pixels'"),
                    pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_fill_color="c", get_radius=9,
                              radius_units="'pixels'", get_line_color=[255, 255, 255], line_width_min_pixels=2,
                              stroked=True)],
            initial_view_state=pdk.ViewState(longitude=(h.lon + go.s_lon) / 2, latitude=(h.lat + go.s_lat) / 2,
                                             zoom=max(10, min(15, 13.5 - math.log2(max(go.km, .3))))),
            map_style=pdk.map_styles.CARTO_LIGHT), height=320)
        st.caption(":red[●] Your home · :green[●] Your shelter: a candidate (dry school, sports hall or civic "
                   "building), not an official one. Follow the municipality's instructions.")
    else:
        st.warning("No dry shelter within 10 km in our data: ask the municipal help line where to go.")

    o = host.offers()
    towns = anna.load()[1]
    o = o[o.municipality.isin(towns.municipality)] if len(o) else o
    if len(o):
        ctr = towns.drop_duplicates("municipality").set_index("municipality")
        d = core.km(h.lon, h.lat, ctr.loc[o.municipality, "lon"].values, ctr.loc[o.municipality, "lat"].values)
        near = o[d <= 10]
        if len(near):
            st.info(f"**{int(near.beds.sum())} spare bed{'s' if near.beds.sum() != 1 else ''} offered by residents "
                    "within 10 km.** If you are older, ill or have small children, ask the help line for one instead "
                    "of a hall.", icon=":material/bed:")
    st.markdown(f":orange[:material/how_to_reg:] Once you have left, or if you need help to leave, tell the fire "
                f"brigade: see **{LEFT}** above.")
    method(modelled)


def checkin_form():
    """Resident check-in: "I have left, I'm at X" or "I need help leaving", by street and house number. The town comes
    from the address typed in the first tab (res_home), or from the town picker here."""
    D = checkin.doors()
    munis = checkin.munis()
    home = st.session_state.get("res_home") or {}
    hm = home.get("municipality")
    muni = st.selectbox("Your town", munis, format_func=anna.town, index=munis.index(hm) if hm in munis else None,
                        placeholder="Pick your town", key=f"ci_town_{hm}")
    if muni is None:
        return
    here = D[D.municipality == muni]
    streets = sorted(here.loc[here.has_address, "street"].dropna().unique())
    if not streets:
        st.info("No street addresses in OpenStreetMap for the flooded homes here. Call the municipal help line "
                "instead.")
        return
    mine = home if hm == muni else {}
    c1, c2 = st.columns([3, 1])
    street = c1.selectbox("Your street", streets, placeholder="Type to search", key=f"ci_street_{muni}_{mine.get('street')}",
                          index=streets.index(mine["street"]) if mine.get("street") in streets else None)
    nums = sorted(here.loc[here.street == street, "number"].dropna().unique(),
                  key=lambda n: (int("".join(filter(str.isdigit, n)) or 0), n)) if street else []
    number = c2.selectbox("Number", nums, placeholder="No.", disabled=not street,
                          key=f"ci_num_{muni}_{street}_{mine.get('number')}",
                          index=nums.index(mine["number"]) if street == mine.get("street")
                          and mine.get("number") in nums else None)
    choice = st.radio("Your situation", [":green[:material/check_circle:] I have left my home",
                                         ":red[:material/sos:] I am still at home and need help to leave"],
                      key="ci_choice")
    help_ = "need help" in choice
    where = None
    if not help_:
        shelters = anna.load_moves()[1].query("municipality == @muni").sort_values(
            "people", ascending=False).shelter.drop_duplicates().tolist()
        where = st.radio("Where are you now?", checkin.WHERE, key="ci_where")
        if where == "A shelter" and shelters:
            where = st.selectbox("Which shelter?", shelters, key="ci_shelter")
    people = st.number_input("How many people from this home are with you?" if not help_ else
                             "How many people need help?", 1, 20, 1, key="ci_people")
    if st.button("Send", type="primary", disabled=not (street and number), icon=":material/send:", key="ci_send"):
        door = f"{street} {number}"
        live.add_checkin(muni, door, "needs help" if help_ else "safe", where or "", int(people), False)
        if help_:
            st.error(f"Help request sent for {door}: it is now first on the crews' list. If water is rising, go "
                     "upstairs and call 112.", icon=":material/sos:")
        else:
            st.success(f"Thank you. {door} is marked as left, so crews can skip it.", icon=":material/check_circle:")
    st.caption("No name or phone number is stored.",
               help="Only the address, where you are and how many people. In a real roll-out this form is reached "
                    "from the link in the BE-Alert or NL-Alert SMS, or by phone through the municipal help line.")


st.title("Am I at risk?")
st.html("<style>[data-testid=stTabs] [role=tablist]{flex-wrap:wrap;row-gap:.25rem}</style>")  # all 3 tabs on a phone
t1, t2, t3 = st.tabs([f":blue[:material/home_pin:] {LEAVE}", f":orange[:material/how_to_reg:] {LEFT}",
                      f":green[:material/bed:] {BED}"])
with t1:
    lookup()
with t2:
    st.markdown("**Tell the fire brigade where you are, so crews go first to those still at home.**")
    checkin_form()
with t3:
    host.render((st.session_state.get("res_home") or {}).get("municipality"))
