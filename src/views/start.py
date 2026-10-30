"""Who leaves first: the opening page. Two questions side by side: which flood (EFAS 10-, 100- or 500-year zone),
then which town (or the whole map); then the map and, for a town, every home in the zone in the order to evacuate
it, with the dry shelter each one goes to, as a sortable table. Below the list, cards lead on to the
desk's next steps in order (town plan, door-knock list, crisis room), then residents and data & limits.
The flood chosen here is this visitor's own: it does not switch the crisis room's shared scenario (live.set_rps).
Numbers: outputs/rp/ (addresses.parquet: OSM addresses on GHS-OBAT buildings; app_towns; critical_sites;
receiving_sites; bus_plan via anna.destinations)."""
from html import escape as esc

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import about, fmt

ALL = "__all__"
RPS = {10: "10-year flood", 100: "100-year flood", 500: "500-year flood"}
CHANCE = {10: "10 % chance in any year", 100: "1 % chance in any year", 500: "0.2 % chance in any year"}
TIER = {1: "First", 2: "Next", 3: "Then"}
TIER_COL = {1: core.EVACUATE, 2: "#eb6834", 3: "#8e8e93"}  # red, the people orange, grey: always with the word
CARE = {"hospital", "care home"}

core.style()
st.html("""<style>
.q{font-size:1.15rem;font-weight:650;letter-spacing:-.01em;color:var(--label);margin:1.4rem 0 -.3rem}
.q small{display:block;font-size:.88rem;font-weight:400;color:var(--label2);margin-top:.2rem;letter-spacing:0}
.lf-note{color:var(--label3);font-size:.8rem;margin:.45rem 0 0;line-height:1.45}
.block-container{max-width:none;padding-left:2rem;padding-right:2rem}
</style>""")


@st.cache_data
def homes(area, muni, v):
    """One row per home address of a town in zone v; homes with no OSM address keep their map point."""
    a = pd.read_parquet(core.DATA / "addresses.parquet")
    a = a[(a.area == area) & (a.municipality == muni) & (a.use == 1) & a[f"in_{v}"]]
    a = a.assign(door=a.label.where(a.label.fillna("").astype(bool),
                                    [f"No street address ({y:.5f}, {x:.5f})" for x, y in zip(a.lon, a.lat)]),
                 single=(a.storeys == 1) & (a.height_m != 2.5))  # 2.5 m is OBAT's fill-in height: unknown
    return (a.groupby("door", as_index=False)
            .agg(street=("street", "first"), lon=("lon", "mean"), lat=("lat", "mean"), single=("single", "any"),
                 low=("in_rp10", "any"), first=("in_rp100", lambda x: 100 if x.any() else 500)))


def ranked(t, v):
    """Care sites and homes of town t in zone v, in the order to evacuate them, each with where it goes."""
    rp = int(v[2:])
    crit = anna.load()[2]
    cs = crit[(crit.area == t.area) & (crit.municipality == t.municipality) & crit.type.isin(CARE)
              & crit[f"in_{v}_flood"].astype(bool) & crit.share_of_site_flooded.ge(.05)]
    recv = anna.load_moves()[0].sort_values("km").drop_duplicates("from_name").set_index("from_name")
    care = pd.DataFrame({"tier": 1, "Address": cs.name.values, "lon": cs.lon.values, "lat": cs.lat.values,
                         "Why": [f"{k.capitalize()}: cannot leave alone" for k in cs.type],
                         "go": [recv.to_name.get(n, "No dry site of the same kind in reach") for n in cs.name],
                         "go_address": "Outside the 500-year zone",
                         "go_km": [recv.km.get(n) for n in cs.name], "go_lon": [recv.lon.get(n) for n in cs.name],
                         "go_lat": [recv.lat.get(n) for n in cs.name], "street": ""})
    h = anna.destinations(t.municipality, homes(t.area, t.municipality, v), v)
    first = h["first"].where(~h.low, 10).clip(upper=rp)
    h["tier"] = [1 if lo and s else 2 if lo or s else 3 for lo, s in zip(h.low, h.single)]
    h["Why"] = [f"Wet from a {f}-year flood" + (" · no upper floor" if s else "") for f, s in zip(first, h.single)]
    h = h.rename(columns={"door": "Address"})
    if "go" not in h or not h.go.astype(bool).any():
        h["go"], h["go_address"] = "No dry shelter within 10 km: ask the next town", ""
    L = pd.concat([care, h], ignore_index=True)
    L["care"] = L.index < len(care)
    return L.sort_values(["tier", "care", "street", "Address"], ascending=[True, False, True, True],
                         na_position="last").reset_index(drop=True)


def from_map():
    objs = [o for os_ in st.session_state.lf_map.selection.objects.values() for o in os_]
    rows = [o["row"] for o in objs if o.get("row") is not None]
    hit = [o.get("key") for o in objs if o.get("key")]
    if rows:
        st.session_state.lf_addr = int(rows[0])
    elif hit:
        st.session_state.lf_town = hit[0]


def pick_row(key):
    """A row picked in a table: a town opens its homes, an address flies the map to it; deselected, back to all."""
    rows = st.session_state[key].selection.rows
    ids = st.session_state[f"{key}_ids"]
    if key.startswith("lf_tbl"):
        st.session_state.lf_addr = ids[rows[0]] if rows else None
    elif rows:
        st.session_state.lf_town = ids[rows[0]]


def town_table(T, rp, key, height=320):
    """Every town in the zone, most residents first; sortable by any column, a row picked opens the town."""
    st.session_state[f"{key}_ids"] = T.index.tolist()
    st.dataframe(pd.DataFrame({"Town": T.label.values, "Region": T.area.map(anna.AREA).values,
                               "Residents": T.people.values, "Buildings": T.buildings.values}),
                 hide_index=True, key=key, on_select=lambda k=key: pick_row(k), selection_mode="single-row",
                 height=height, alt=f"Towns in the {rp}-year flood zone, most residents first",
                 column_config={
                     "Town": st.column_config.TextColumn("Town", width="medium", pinned=True),
                     "Residents": st.column_config.ProgressColumn(
                         f"Residents in the {rp}-year zone", format="localized", min_value=0,
                         max_value=int(T.people.max()), color="primary",
                         help="GHS-POP spread over homes: an order of magnitude"),
                     "Buildings": st.column_config.NumberColumn("Buildings", format="localized", width="small")})
    st.html("<p class='lf-note'>Click a row to open its homes; click a column header to sort.</p>")


# ================================================================== the questions
core.header("Who leaves first", "Pick a flood and a town: every home in the water, in the order to evacuate it, "
                                "and the dry shelter each one goes to.")

towns = anna.load()[1]
WHAT = {10: "the water that comes often and runs deepest", 100: "the usual planning flood",
        500: "the rare, widest one"}
c_rp, c_place = st.columns([2, 3], vertical_alignment="top")
with c_rp:
    rp = st.segmented_control("Which flood do you plan for?", list(RPS), key="lf_flood",
                              format_func=lambda k: f"{k}-year",  # short, so all three fit a narrow column
                              help="EFAS flood zones, every river at once, no dikes: a planning map, not a forecast.")
    st.caption(f"{CHANCE[rp]}: {WHAT[rp]}." if rp else
               "Not sure? Start with the 100-year, the usual planning flood. The 10-year comes often and runs "
               "deepest; the 500-year is the rare, widest one.")
if rp is None:  # the second question shows from the start, so the two steps read as one form
    c_place.selectbox("Which town?", [], index=None, disabled=True, placeholder="Pick a flood first")
    st.stop()
v = f"rp{rp}"
T = towns[(towns.variant == v) & (towns.people >= 10)].sort_values("people", ascending=False)
T = T.assign(key=T.area + "|" + T.municipality).set_index("key")
places = [ALL] + T.index.tolist()
if st.session_state.get("lf_town") not in places:
    st.session_state.lf_town = None
with c_place:
    place = st.selectbox("Which town?", places, key="lf_town", index=None,
                         placeholder=f"Search {len(T)} towns, or open the whole map",
                         format_func=lambda k: "Whole map · every town" if k == ALL else
                         f"{T.label[k]} · {anna.AREA[T.area[k]]} · about {about(T.people[k])} residents in the zone")
if place is None:
    st.html("<div class='q'>Most affected<small>The towns with the most people in the water, first. Pick one "
            "for its list of homes.</small></div>")
    town_table(T, rp, "lf_top")
    st.stop()
st.space("small")

# ================================================================== the map
zone = core.water(v)
tw = T.reset_index()
# in a town's view the other towns step back to grey, so orange only means "Next" homes
dot = core.towns(tw.assign(fill=[core.rgb(core.PEOPLE, 220) if place == ALL else core.rgb("#8e8e93", 70) for k in tw.key],
                           tip=[f"{n}\nabout {about(p)} residents in the {rp}-year zone\nClick to see its homes"
                                for n, p in zip(tw.label, tw.people)]), "people", "fill", 18)
dot.id = "towns"

if place == ALL:
    core.deck(zone + [dot], core.view(core.bbox(v)), 560, on_select=from_map, selection_mode="single-object",
              key="lf_map", scroll=False)
    core.legend(core.swatch(core.RP_COL[v], f"{rp}-year flood zone (EFAS model)")
                + core.swatch(core.PEOPLE, "Town, size = residents in the zone", True))
    st.html("<div class='q'>Most affected<small>Pick a town here or on the map for its list of homes.</small></div>")
    town_table(T, rp, "lf_all", 420)
    st.stop()

t = T.loc[place]
L = ranked(t, v)
first_n = int((L.tier == 1).sum())
n_care = int(L.care.sum())
st.html(f"<div class='banner' style='--c:{core.EVACUATE}'><div class='dot'></div><div>"
        f"<h2>{fmt(len(L) - n_care)} homes in {t.label}'s {rp}-year zone, about {about(t.people)} residents</h2>"
        f"<p>Start with the {fmt(first_n)} marked <b>First</b>: "
        + (f"{n_care} hospital or care home{'s' if n_care != 1 else ''}, then " if n_care else "")
        + "homes that flood even in a 10-year flood and have no upper floor to escape to.</p></div></div>")

MAP_H = 760
if st.session_state.get("lf_addr_town") != (place, v):  # a new town or flood: back to every home
    st.session_state.lf_addr, st.session_state.lf_addr_town = None, (place, v)
out = L.assign(Order=L.index + 1, Priority=L.tier.map(TIER))[
    ["Order", "Priority", "Address", "Why", "go", "go_address", "go_km"]]
c_list, c_map = st.columns([5, 7], gap="medium")

with c_list:
    st.html(f"<div class='q' style='margin-top:0'>Who leaves, and where to<small>{fmt(len(L))} addresses, first to "
            "last. Pick one to fly to it and its shelter.</small></div>")
    f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
    q = f1.text_input("Search", key="lf_q", placeholder="Street or shelter", label_visibility="collapsed",
                      icon=":material/search:")
    tier = f2.segmented_control("Priority", list(TIER), key="lf_tier", format_func=TIER.get,
                                label_visibility="collapsed")
    F = out
    if tier:
        F = F[L.tier == tier]
    if q:
        F = F[F.Address.str.contains(q, case=False, regex=False) | F.go.str.contains(q, case=False, regex=False)]
    key = f"lf_tbl-{tier}-{q}"  # a new filter starts with nothing picked in the table
    st.session_state[f"{key}_ids"] = F.index.tolist()
    st.dataframe(F.assign(Priority=F.Priority.map(lambda x: [x])), hide_index=True, height=MAP_H - 98, key=key,
                 on_select=lambda k=key: pick_row(k), selection_mode="single-row",
                 alt=f"Addresses in {t.label}'s {rp}-year zone, in the order to evacuate them",
                 column_config={
                     "Order": st.column_config.NumberColumn("#", width=48),
                     "Priority": st.column_config.MultiselectColumn(
                         "Priority", options=list(TIER.values()), color=list(TIER_COL.values()), width=78,
                         help="First: care sites, and homes in the 10-year zone with no upper floor. Next: homes "
                              "in the 10-year zone, or with no upper floor. Then: the rest of the zone."),
                     "Address": st.column_config.TextColumn("Address", width="medium"),
                     "Why": st.column_config.TextColumn("Why", width="medium"),
                     "go": st.column_config.TextColumn("Go to", width="medium",
                                                       help="The nearest dry shelter of the town's 10 km plan"),
                     "go_address": st.column_config.TextColumn("Shelter address", width="medium"),
                     "go_km": st.column_config.NumberColumn("km", format="%.1f", width=56,
                                                            help="By road, about: straight line × 1.3")})
    if F.empty:
        st.caption("No address matches.")

with c_map:  # one map that keeps its key: a picked home flies the view to it and fades the rest
    pick = st.session_state.get("lf_addr")
    pick = pick if pick is not None and pick < len(L) else None
    FLY = 1400  # ms: the camera move, and the marker and line gliding from the last pick to this one
    fade = {"getFillColor": 700}
    pts = L.assign(fill=[core.rgb(TIER_COL[k], 230 if pick is None else 45) for k in L.tier], row=L.index,
                   tip=[f"{a}\n{TIER[k]} · {w}\nGo to: {g}\nClick to follow it"
                        for a, k, w, g in zip(L.Address, L.tier, L.Why, L.go)])
    pts = pts.iloc[::-1]  # draw First on top
    sh = L[L.go_lon.notna()].drop_duplicates("go") if "go_lon" in L else L.iloc[:0]
    sh = sh.assign(lon=sh.go_lon, lat=sh.go_lat, fill=[core.rgb(core.SHELTER, 255 if pick is None else 50)] * len(sh),
                   tip=[f"{g}\n{a}\nDry shelter (candidate, not official)" for g, a in zip(sh.go, sh.go_address)])
    homes_l, shel_l = core.points(pts, "fill", 4, 0), core.points(sh, "fill", 9, 2 if pick is None else 0)
    homes_l.id, homes_l.transitions = "homes", fade
    shel_l.id, shel_l.transitions = "shelters", fade
    layers = zone + [homes_l, shel_l, dot]
    if pick is None:
        x0, y0, x1, y1 = L.lon.quantile(.02), L.lat.quantile(.02), L.lon.quantile(.98), L.lat.quantile(.98)
        pad = max(x1 - x0, y1 - y0, .01) * .25
        vs = core.view((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    else:  # the home, its shelter and the line between them, framed together
        g = L.loc[pick]
        has_go = "go_lon" in L and pd.notna(g.go_lon)
        glide = {"getPosition": FLY, "getSourcePosition": FLY, "getTargetPosition": FLY}
        if has_go:
            seg = pd.DataFrame({"src": [[g.lon, g.lat]], "dst": [[g.go_lon, g.go_lat]],
                                "tip": [f"{g.Address} → {g.go}" + (f"\nabout {g.go_km:.1f} km by road"
                                                                   if pd.notna(g.go_km) else "")]})
            line = pdk.Layer("LineLayer", seg, id="route", get_source_position="src", get_target_position="dst",
                             get_color=[29, 29, 31, 210], get_width=3, width_units="'pixels'", pickable=True,
                             transitions=glide)
            to = core.points(pd.DataFrame({"lon": [g.go_lon], "lat": [g.go_lat], "tip": [
                f"{g.go}\n{g.go_address}\nDry shelter (candidate, not official)"]}), core.rgb(core.SHELTER), 11, 3)
            to.id, to.transitions = "route_to", glide
            layers += [line, to]
        me = core.points(pd.DataFrame({"lon": [g.lon], "lat": [g.lat], "tip": [f"{g.Address}\n{TIER[g.tier]} · {g.Why}"]}),
                         core.rgb(TIER_COL[g.tier]), 9, 3)
        me.id, me.transitions = "route_from", glide
        layers.append(me)
        xs, ys = [g.lon] + ([g.go_lon] if has_go else []), [g.lat] + ([g.go_lat] if has_go else [])
        half = max(max(xs) - min(xs), (max(ys) - min(ys)) * 1.55, .008) * .7
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        vs = core.view((cx - half, cy - half / 1.55, cx + half, cy + half / 1.55))
    vs.transition_duration = FLY
    core.deck(layers, vs, MAP_H, on_select=from_map, selection_mode="single-object", key="lf_map", scroll=False)
    if pick is None:
        core.legend("".join(core.swatch(TIER_COL[k], f"{TIER[k]}", True) for k in TIER)
                    + core.swatch(core.SHELTER, "Dry shelter they go to", True)
                    + core.swatch(core.RP_COL[v], f"{rp}-year flood zone (EFAS model)"))
    else:
        core.legend(core.swatch(TIER_COL[g.tier], "This home", True)
                    + (core.swatch(core.SHELTER, "Its dry shelter", True) if has_go else "")
                    + core.swatch(core.RP_COL[v], f"{rp}-year flood zone (EFAS model)"))
        st.markdown(f"**{g.Address}** → {g.go}" + (f", about {g.go_km:.1f} km" if pd.notna(g.go_km) else "")
                    + f"  \n:gray[{TIER[g.tier]} · {g.Why}]")
        st.button("Show every home", icon=":material/zoom_out_map:", type="tertiary",
                  on_click=lambda: st.session_state.update(lf_addr=None))

st.caption("Shelters are candidate sites outside the zone, not official ones: confirm each with its owner.")
st.download_button("Download the list (CSV)", out.to_csv(index=False),
                   f"evacuation_order_{t['name'].replace(' ', '_')}_{rp}-year.csv", icon=":material/download:")
st.caption("Residents: GHS-POP spread over homes, an order of magnitude. Addresses: OpenStreetMap matched to "
           "GHS-OBAT buildings. No data on age, disability or who lives alone: add the municipality's own list.")


# ================================================================== what next: the desk's steps as cards
def open_desk(role, page):
    st.session_state.role = role
    st.session_state._town = st.session_state.town = t.municipality
    st.session_state._goto = page
    st.query_params["role"] = role


st.html(f"<div class='q'>What next for {esc(t.label)}<small>This list is steps 1 to 3. The desk takes it from "
        "here, in this order.</small></div>")
core.tiles([(core.PAGES[k][2], core.PAGES[k][3], f"Step {core.STEP[k][0]}", core.PAGES[k][1], core.STEP[k][1],
             (open_desk, ("manager", k))) for k in core.FLOW], "lf_next")
st.space("small")
core.tiles([(core.PAGES["resident"][2], core.PAGES["resident"][3], "", "For residents",
             "Am I at risk, where do I go?", (open_desk, ("resident", "resident"))),
            (core.PAGES["limits"][2], core.PAGES["limits"][3], "", "Data & limits",
             "Where every number comes from", (open_desk, ("manager", "limits")))], "lf_also", small=True)
st.caption("The desk follows the crisis room's shared flood scenario (the 100-year zone when none is on), not the "
           "flood picked here.")
