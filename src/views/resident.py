"""Resident: type your street, pick your house, see at once whether to leave and where to go, or whether you can host.
Homes in the 2021 water: outputs/data/addresses.parquet (OSM addresses matched to GHS-OBAT buildings). Where to go:
the town's 10 km shelter plan (bus_plan.csv), nearest shelter that takes people from this town; walking or bus by
straight-line distance × 1.3 (road / straight ratio measured 1.2-1.4 in notebooks/evac_sim.py). Spare beds offered
by residents: data/host_offers.csv. Nothing typed here is stored."""
import math
import re

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import fmt

WALK_KMH, BUS_KMH, ROAD = 4, 30, 1.3


@st.cache_data
def homes():
    a = pd.read_parquet(core.DATA / "addresses.parquet")
    a = a[(a.use == 1) & a.label.astype(bool) & a.street.notna()].copy()
    a["town"] = a.municipality.map(anna.town)
    a["single"] = (a.storeys == 1) & (a.height_m != 2.5)
    return (a.groupby(["municipality", "town", "street", "housenumber"], as_index=False)
            .agg(lon=("lon", "mean"), lat=("lat", "mean"), single=("single", "any"), area=("area", "first")))


def offers():
    try:
        return pd.read_csv(core.DATA.parents[1] / "data" / "host_offers.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=["municipality", "beds", "older"])


H = homes()
bus = anna.load_moves()[1]
towns = anna.load()[1]

st.title("Do I need to leave?")
st.caption("Type your street. Nothing you type is stored.")
q = st.text_input("Street", placeholder="e.g. Ahrstraße 28, Rue de la Station, Hauptstraße", label_visibility="collapsed")


def norm(x):
    return x.casefold().replace("ß", "ss").strip()


# People type whole addresses ("Ahrstraße 28, Ahrbrück", "5 rue de la Station"): split off the number and the town,
# or the street would not match and the page would wrongly say the home was dry.
n = re.search(r"\b\d+\s?[a-zA-Z]?\b", q)
typed_num = n.group().replace(" ", "").lower() if n else None
parts = [p.strip() for p in ((q[:n.start()] + q[n.end():]) if n else q).split(",") if p.strip()]
q_street, q_town = (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")
hit = H[H.street.map(norm).str.contains(norm(q_street), regex=False)] if len(q_street) >= 3 else H.iloc[0:0]
if q_town and hit.town.map(norm).str.contains(norm(q_town), regex=False).any():
    hit = hit[hit.town.map(norm).str.contains(norm(q_town), regex=False)]
streets = (hit.drop_duplicates(["street", "town"]).assign(k=lambda d: d.street + ", " + d.town)
           .sort_values("k").k.tolist()[:30])

if len(q_street) >= 3 and not streets:
    st.success("**Your street is not among the homes in the 2021 water.** You are most likely outside it. Stay alert "
               "to official warnings, and if your home stayed dry, you can offer a bed to a neighbour who has to "
               "leave.", icon=":material/check_circle:")
    st.page_link("views/host.py", label="Offer a bed", icon=":material/volunteer_activism:")
    st.caption("This list holds only homes inside the July 2021 satellite flood map (and the modelled Vesdre zone) "
               "that have an OpenStreetMap address. Not on it does not guarantee safety: the satellite missed water in "
               "narrow valleys. Follow official warnings.")
    st.stop()
if not streets:
    st.stop()

c1, c2 = st.columns([3, 1])
# with a typed number, start on the first street-and-town that has that number
has = [i for i, k in enumerate(streets) if typed_num and
       (hit[(hit.street + ", " + hit.town) == k].housenumber.str.replace(" ", "").str.lower() == typed_num).any()]
street_town = c1.selectbox("Your street", streets, index=has[0] if has else 0, label_visibility="collapsed")
street, town = street_town.rsplit(", ", 1)
nums = H[(H.street == street) & (H.town == town)]
nums = nums.assign(o=nums.housenumber.str.extract(r"(\d+)", expand=False).fillna(0).astype(int)).sort_values(["o", "housenumber"])
numbers = nums.housenumber.tolist()
known = [i for i, x in enumerate(numbers) if typed_num and str(x).replace(" ", "").lower() == typed_num]
num = c2.selectbox("Number", numbers, index=known[0] if known else (None if typed_num else 0),
                   placeholder="Number", label_visibility="collapsed")
if num is None:
    st.info(f"Number {typed_num} is not among the homes in the 2021 water on {street}. Pick your number if it is "
            "listed; if not, your home was most likely outside the water. Follow official warnings.",
            icon=":material/info:")
    st.stop()
h = nums[nums.housenumber == num].iloc[0]
modelled = h.area in anna.MODELLED

# where to go: shelters this town's people are sent to in the 10 km plan, nearest to this home first
plan = bus[bus.municipality == h.municipality].groupby(["shelter", "s_lon", "s_lat"], as_index=False).people.sum()
plan = plan[plan.people >= .5]
plan["km"] = core.km(h.lon, h.lat, plan.s_lon, plan.s_lat) * ROAD
go = plan.nsmallest(1, "km").iloc[0] if len(plan) else None

st.error(f"**{street} {num}, {town} was in the 2021 water{' (modelled)' if modelled else ''}. Leave when the alert "
         "comes, before the water rises.**" + (" Your home has no upper floor to escape to: leave early."
                                                if h.single else ""), icon=":material/warning:")
if go is not None:
    walk = go.km <= 1.5
    mins = go.km / (WALK_KMH if walk else BUS_KMH) * 60
    c = st.columns(3)
    c[0].metric("Go to", go.shelter, border=True)
    c[1].metric("How", "On foot" if walk else "By bus or car", border=True,
                help="On foot up to 1.5 km by road; further away, the municipality's buses (book a seat via the help "
                     "line).")
    c[2].metric("About", f"{mins:.0f} min", border=True,
                help=f"{go.km:.1f} km by road (straight line × {ROAD}); "
                     f"{'walking ' + str(WALK_KMH) if walk else 'bus ' + str(BUS_KMH)} km/h. A minimum.")
    pts = pd.DataFrame({"lon": [h.lon, go.s_lon], "lat": [h.lat, go.s_lat], "c": [core.rgb(core.EVACUATE),
                                                                                  core.rgb(core.SHELTER)]})
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
    st.caption(":red[●] Your home · :green[●] Your shelter. Candidate shelter (school, sports hall or civic building "
               "dry in 2021 and in the 100-year model), not an official one: follow the municipality's instructions.")
else:
    st.warning("No dry shelter within 10 km in our data: ask the municipal help line where to go.")

o = offers()
o = o[o.municipality.isin(towns.municipality)] if len(o) else o
if len(o):
    ctr = towns.drop_duplicates("municipality").set_index("municipality")
    d = core.km(h.lon, h.lat, ctr.loc[o.municipality, "lon"].values, ctr.loc[o.municipality, "lat"].values)
    near = o[d <= 10]
    if len(near):
        st.info(f"**{int(near.beds.sum())} spare bed{'s' if near.beds.sum() != 1 else ''} offered by residents within "
                "10 km.** If you are older, ill or have small children, ask the help line for one instead of a hall.",
                icon=":material/bed:")
st.page_link("views/checkin.py", label="I have left: tell the fire brigade", icon=":material/how_to_reg:")
st.caption(f"Home: {'single-storey' if h.single else 'has an upper floor'} (GHS-OBAT height). Address: OpenStreetMap "
           "(ODbL) matched to the satellite flood map of July 2021" + (" — here the EFAS 500-year model, as the "
           "satellite missed the Vesdre" if modelled else "") + ".")
