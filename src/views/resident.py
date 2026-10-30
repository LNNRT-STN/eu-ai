"""Resident: type your address and see at once whether to leave, the exact place to go and the way there; then tell
the fire brigade "I am safe" or "I need help" in one tap, for that same address; or offer a bed. Two tabs, the only
page the Resident role sees (no sidebar Town picker: the town comes from the address typed in the first tab, shared
through st.session_state.res_home).
Homes in the 2021 water: outputs/data/addresses.parquet (OSM addresses matched to GHS-OBAT buildings). Where to go:
the town's 10 km shelter plan (bus_plan.csv), nearest shelter that takes people from this town, with its OSM street
address (anna.destinations, notebooks/shelter_addresses.py); walking or bus by
straight-line distance × 1.3 (road / straight ratio measured 1.2-1.4 in notebooks/evac_sim.py). Spare beds offered
by residents: data/host_offers.csv. Nothing typed in the address box is stored; a check-in stores only the address,
where people are and how many (src/live.py)."""
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
LEAVE, BED = ("Do I need to leave?", "Offer a bed")


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

    go = anna.destinations(h.municipality, pd.DataFrame({"lon": [h.lon], "lat": [h.lat]})).iloc[0]
    S = live.towns_status().sort_values("level").drop_duplicates("municipality", keep="last")  # worst status
    status = S.set_index("municipality").status.get(h.municipality, "none")
    has_go = bool(go.go)
    walk = has_go and go.go_km <= 1.5
    mins = go.go_km / (WALK_KMH if walk else BUS_KMH) * 60 if has_go else None
    how = (f"{'On foot' if walk else 'By bus or car'}, about {mins:.0f} min ({go.go_km:.1f} km)" if has_go else "")
    dest = f"{go.go}" + (f", {go.go_address}" if has_go and go.go_address else "")
    head, color = {
        "evacuate": (f"Leave now. Go to {go.go}." if has_go else "Leave now.", core.EVACUATE),
        "warn": (f"Get ready to leave. Your shelter: {go.go}." if has_go else "Get ready to leave.", "#c93400"),
        "watch": ("The river is rising. No order yet.", "#b38600"),
    }.get(status, ("No alert now.", "#4f6580"))
    detail = (f"{street} {num}, {town} was in the 2021 water{' (modelled)' if modelled else ''}. "
              + ("" if status in ("evacuate", "warn") or not has_go else f"If the order comes, go to {go.go}. ")
              + ("Your home has no upper floor: leave early." if h.single else ""))
    core.banner(color, head, detail, note=False)
    k = live.clock()
    st.caption((f"Replay of the 2021 forecast, {live.drill(k['t']):%a %-d %b, %H:%M}" if k["mode"] == "replay"
                else f"Live forecast, {k['t']:%a %-d %b, %H:%M}") + ". Follow the municipality's instructions.")

    if not has_go:
        st.warning("No dry shelter within 10 km in our data: ask the municipal help line where to go.")
    else:
        left, right = st.columns([3, 2], gap="medium")
        with right:
            st.markdown("**Where to go**")
            st.markdown(f"### {go.go}")
            st.markdown(f":material/location_on: **{go.go_address or 'No street address in OpenStreetMap'}**  \n"
                        f":material/{'directions_walk' if walk else 'directions_bus'}: {how}")
            st.link_button("Directions", icon=":material/directions:", width="stretch",
                           url=f"https://www.google.com/maps/dir/?api=1&destination={go.go_lat:.5f},{go.go_lon:.5f}"
                               f"&travelmode={'walking' if walk else 'driving'}")
            st.caption(f"A candidate {KIND.get(go.go_cat, go.go_cat)}, dry in 2021: not an official shelter.")
        with left:
            pts = pd.DataFrame({"lon": [h.lon, go.go_lon], "lat": [h.lat, go.go_lat],
                                "c": [core.rgb(core.EVACUATE), core.rgb(core.SHELTER)]})
            leg = pd.DataFrame([{"a": [h.lon, h.lat], "b": [go.go_lon, go.go_lat]}])
            st.pydeck_chart(pdk.Deck(
                layers=[pdk.Layer("LineLayer", leg, get_source_position="a", get_target_position="b",
                                  get_color=[29, 29, 31, 160], get_width=3, width_units="'pixels'"),
                        pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_fill_color="c",
                                  get_radius=10, radius_units="'pixels'", get_line_color=[255, 255, 255],
                                  line_width_min_pixels=2, stroked=True)],
                initial_view_state=pdk.ViewState(longitude=(h.lon + go.go_lon) / 2, latitude=(h.lat + go.go_lat) / 2,
                                                 zoom=max(10, min(15, 13.5 - math.log2(max(go.go_km, .3))))),
                map_style=pdk.map_styles.CARTO_LIGHT), height=300)
            st.caption(":red[●] Your home · :green[●] Your shelter")

    safe_now(h.municipality, f"{street} {num}", dest if has_go else "")

    o = host.available()  # placed guests and withdrawn offers no longer count
    towns = anna.load()[1]
    o = o[o.municipality.isin(towns.municipality)] if len(o) else o
    if len(o):
        ctr = towns.drop_duplicates("municipality").set_index("municipality")
        d = core.km(h.lon, h.lat, ctr.loc[o.municipality, "lon"].values, ctr.loc[o.municipality, "lat"].values)
        near = o[d <= 10]
        if len(near):
            st.caption(f":material/bed: {int(near.beds.sum())} spare bed{'s' if near.beds.sum() != 1 else ''} still "
                       "free with residents within 10 km. Older, ill or with small children? Ask the help line for one.")
    method(modelled)


def safe_now(muni, door, dest):
    """'I am safe' in one tap, for the address already found: crews then skip this home."""
    st.markdown("**Tell the fire brigade**", help="Crews go first to homes with no news. No name or phone number is "
                "stored: only the address, where you are and how many. In a real roll-out this is reached from the "
                "link in the BE-Alert or NL-Alert SMS.")
    done = st.session_state.get("res_done", {})
    if done.get("door") == door:
        if done["status"] == "safe":
            st.success(f"**{door} is marked safe.** Crews will skip it. Thank you.", icon=":material/check_circle:")
        else:
            st.error(f"**Help request sent for {door}.** You are first on the crews' list. If water is rising, go "
                     "upstairs and call 112.", icon=":material/sos:")
        st.button("Change", type="tertiary", on_click=lambda: st.session_state.pop("res_done", None))
        return
    places = ([f"At {dest}"] if dest else []) + checkin.WHERE[1:]
    a, b, c = st.columns([3, 1, 2], vertical_alignment="bottom")
    where = a.selectbox("Where are you now?", places, key=f"res_where_{door}")
    people = b.number_input("People", 1, 20, 1, key=f"res_people_{door}")

    def send(status):
        live.add_checkin(muni, door, status, where if status == "safe" else "", int(people), False)
        st.session_state.res_done = {"door": door, "status": status}

    c.button("I am safe", type="primary", icon=":material/check_circle:", width="stretch", on_click=send,
             args=("safe",), key="res_safe")
    st.button("I am still at home and need help to leave", icon=":material/sos:", on_click=send,
              args=("needs help",), key="res_help")


st.title("Am I at risk?")
# the verdict banner draws with core's classes; take those, not its page padding or sidebar rules
st.html(re.sub(r"\.block-container\{[^}]*\}|\[data-testid=st(Sidebar|SidebarNav|NavSectionHeader)\][^{]*\{[^}]*\}", "",
               core.CSS))
st.html("<style>[data-testid=stTabs] [role=tablist]{flex-wrap:wrap;row-gap:.25rem}</style>")  # all 3 tabs on a phone
t1, t3 = st.tabs([f":blue[:material/home_pin:] {LEAVE}", f":green[:material/bed:] {BED}"])
with t1:
    lookup()
with t3:
    host.render((st.session_state.get("res_home") or {}).get("municipality"))
