import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

import core
from core import about, fmt

USABLE = 0.5  # share of floor area people can sleep on (corridors, stairs, toilets, furniture take the rest)
SPACE = {3.5: "3.5 m² · Sphere minimum, several days", 2.0: "2 m² · one night, tightly packed",
         4.5: "4.5 m² · Sphere cold climate / longer stays"}
FULL = "#c4501f"


@st.cache_data
def inputs():
    d = core.DST
    return (pd.read_parquet(d / "shelters.parquet"), pd.read_parquet(d / "shelter_edges.parquet"),
            pd.read_parquet(d / "shelter_cells.parquet"), pd.read_parquet(d / "at_risk.parquet"))


@st.cache_data(show_spinner="Planning who goes where…")
def plan(lens, reach, m2):
    """Capacitated transport problem: shelter as many residents as possible, then keep total person-km lowest.
    Variables x_e = people sent along cell→shelter edge e (road km ≤ reach). Rows: a cell sends ≤ its residents,
    a shelter takes ≤ its capacity. Cost km − 1,000 per person, so one more person sheltered always beats distance."""
    sh, edges, cells, _ = inputs()
    cap = (sh.floor * USABLE / m2).to_numpy()
    c = cells[cells.lens == lens].reset_index(drop=True)
    e = edges[(edges.lens == lens) & (edges.km <= reach)].merge(c[["cell"]].reset_index(names="row"), on="cell")
    flow = np.zeros(len(e))
    if len(e):
        n = len(e)
        a = coo_matrix((np.ones(2 * n), (np.r_[e.row, len(c) + e.sid], np.r_[np.arange(n), np.arange(n)])),
                       shape=(len(c) + len(sh), n))
        r = linprog(e.km - 1000, A_ub=a.tocsr(), b_ub=np.r_[c.residents, cap], bounds=(0, None), method="highs")
        flow = r.x if r.success else flow
    e = e.assign(people=flow)[flow > 0.05]
    c["sheltered"] = c.cell.map(e.groupby("cell").people.sum()).fillna(0)
    c["reachable"] = c.cell.isin(edges[(edges.lens == lens) & (edges.km <= reach)].cell)
    s = sh.assign(capacity=cap, load=sh.sid.map(e.groupby("sid").people.sum()).fillna(0))
    return c, s, e


sh, edges, cells, risk = inputs()
s_all, *_, geo = core.load()
core.header("Shelter plan", "If the water comes back, where does everyone go? Residents of each ~1 km block are sent to "
                            "the nearest dry building with room left, until every bed within reach is taken.")

c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="bottom")
lens = c1.segmented_control("Who needs shelter", list(core.LENS), format_func=core.LENS.get, required=True,
                            default="obs" if st.query_params.get("view") == "observed" else "rp100")
reach = c2.select_slider("Furthest trip by road", [2, 5, 10, 15, 20, 25], value=10, format_func="{} km".format,
                         help="Straight-line distance × 1.3 for the road network. 2 km ≈ a walk, 10 km ≈ a bus run.")
m2 = c3.selectbox("Space per person", list(SPACE), format_func=SPACE.get,
                  help=f"Capacity = floor area × {USABLE:.0%} usable ÷ space per person.")

c, s, e = plan(lens, reach, m2)
need, got = c.residents.sum(), c.sheltered.sum()
out_reach = c[~c.reachable].residents.sum()
full = need - got - out_reach
used = s[s.load > 0.5]
avg_km = (e.people * e.km).sum() / got if got else 0
core.facts([(about(need), "residents to move, " + ("inside the July 2021 mapped water" if lens == "obs"
                                                  else "inside the modelled 100-year zone")),
            (f"{got / need:.0%}" if need else "–", f"get a bed within <strong>{reach} km</strong> "
                                                   f"(≈ {about(got)} people, {avg_km:.1f} km on average)"),
            (about(need - got), f"left over: {about(out_reach)} with no shelter in reach, {about(max(full, 0))} "
                                "because the shelters in reach are full"),
            (fmt(len(used)), f"shelters to open, of {fmt(len(s))} dry sites · {fmt(s.capacity.sum())} beds in all")],
           core.AS_OF["zone" if lens == "rp100" else "obs"] + " · " + core.AS_OF["osm"] + " footprints")

c["left"] = c.residents - c.sheltered
left, right = st.columns([3, 2], gap="medium")
with left:
    big = e.people.max() if len(e) else 1
    pos = s.set_index("sid")[["lon", "lat"]]
    arcs = e.merge(c[["cell", "lon", "lat"]], on="cell").join(pos, on="sid", rsuffix="_to")
    arcs["w"] = 1 + 5 * np.sqrt(arcs.people / big)
    arcs["tip"] = [f"<b>{about(p)} people</b> → {n}<br>{k:.1f} km by road"
                   for p, n, k in zip(arcs.people, s.set_index("sid").name.reindex(arcs.sid), arcs.km)]
    s["r"] = 3 + 9 * np.sqrt(s.capacity / s.capacity.max())
    s["fill"] = [core.rgb(FULL) if l >= cap - 0.5 and l > 0 else core.rgb(core.SHELTER) if l > 0.5
                 else core.rgb(core.OFFLINE, 160) for l, cap in zip(s.load, s.capacity)]
    s["tip"] = [f"<b>{n}</b><br>{t} · {cm}<br>{about(l)} of {about(k)} beds used"
                for n, t, cm, l, k in zip(s.name, s.type, s.commune, s.load, s.capacity)]
    lost = c[c.left >= 1].assign(r=lambda d: 3 + 9 * np.sqrt(d.left / max(d.left.max(), 1)),
                                 tip=lambda d: [f"<b>{about(l)} residents without a bed</b><br>{cm}"
                                                + ("" if rc else f"<br>no shelter within {reach} km")
                                                for l, cm, rc in zip(d.left, d.commune, d.reachable)])
    layers = core.water(geo, lens) + [
        pdk.Layer("LineLayer", arcs, get_source_position=["lon", "lat"], get_target_position=["lon_to", "lat_to"],
                  get_color=[36, 138, 61, 150], get_width="w", width_units="'pixels'", pickable=True),
        pdk.Layer("ScatterplotLayer", s, get_position=["lon", "lat"], get_fill_color="fill", get_radius="r",
                  radius_units="'pixels'", stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1,
                  pickable=True),
        pdk.Layer("ScatterplotLayer", lost, get_position=["lon", "lat"], get_fill_color=core.rgb(core.EVACUATE, 220),
                  get_radius="r", radius_units="'pixels'", stroked=True, get_line_color=[255, 255, 255],
                  line_width_min_pixels=1, pickable=True)]
    core.deck(layers, core.view(s_all), 560)
    core.legend(core.swatch(core.SHELTER, "Shelter in use", True) + core.swatch(FULL, "Shelter full", True)
                + core.swatch(core.OFFLINE, "Dry site, not needed", True) + core.swatch(core.EVACUATE, "Residents without a bed", True)
                + core.swatch("rgba(36,138,61,.6)", "Trip, thicker = more people"),
                core.swatch("rgba(0,113,227,.4)", "Observed 2021 water" if lens == "obs" else "Modelled 100-year zone"))

with right:
    t = used.assign(pct=used.load / used.capacity).sort_values("load", ascending=False)
    st.dataframe(t[["name", "type", "commune", "load", "capacity", "pct"]], hide_index=True, height=420, column_config={
        "name": "Shelter to open", "type": st.column_config.TextColumn("Type", width="small"), "commune": "Commune",
        "load": st.column_config.NumberColumn("People", format="%.0f", width="small"),
        "capacity": st.column_config.NumberColumn("Beds", format="%.0f", width="small"),
        "pct": st.column_config.ProgressColumn("Full", format="percent", min_value=0, max_value=1, width="small")})
    trips = arcs.assign(shelter=s.set_index("sid").name.reindex(arcs.sid).to_numpy(),
                        commune=c.set_index("cell").commune.reindex(arcs.cell).to_numpy())
    st.download_button("Download plan (block → shelter)", trips[["commune", "lon", "lat", "shelter", "lon_to", "lat_to", "people", "km"]]
                       .round(4).to_csv(index=False), f"shelter_plan_{lens}_{reach}km.csv", icon=":material/download:",
                       type="tertiary", width="stretch")

gap = c.groupby("commune").agg(residents=("residents", "sum"), left=("left", "sum"),
                               no_reach=("residents", lambda r: r[~c.loc[r.index, "reachable"]].sum()))
gap = gap[gap.left >= 1].sort_values("left", ascending=False)
st.subheader("Where the plan falls short", anchor=False)
if gap.empty:
    st.success(f"Every resident has a bed within {reach} km.", icon=":material/check_circle:")
else:
    core.group([(f"<b>{cm}</b>", f"{about(g.no_reach)} have no shelter within {reach} km · "
                 f"{about(max(g.left - g.no_reach, 0))} find the shelters in reach full",
                 f"<b>{about(g.left)}</b> of {about(g.residents)}") for cm, g in gap.head(8).iterrows()],
               foot="Fixes: a longer bus run (raise the trip slider), pre-agree extra sites with the neighbouring "
                    "commune, or ask the province for a regional reception centre.")

st.subheader("Schools and care sites in the flood zone", anchor=False)
st.caption("These cannot be used as shelters, and hospitals and care homes need their own evacuation first.")
st.dataframe(risk[["name", "type", "commune", "flood_2021", "model_zone"]], hide_index=True, column_config={
    "name": "Site", "type": st.column_config.TextColumn("Type", width="small"), "commune": "Commune",
    "flood_2021": "July 2021", "model_zone": "Model"})

with st.expander("How the plan is made"):
    st.markdown(f"""
1. **Who moves.** GHS-POP residents in each ~1 km block inside the {'July 2021 mapped water' if lens == 'obs' else 'EFAS 100-year zone'}.
2. **Where to.** OpenStreetMap schools, sports halls, community centres and town halls that stayed dry in July 2021
   (not within 100 m of the water), sit outside the EFAS 10- and 100-year zones, and have at least 300 m² of floor.
3. **How many fit.** Floor = building footprints × floors (OSM `building:levels`, 1 when missing).
   Beds = floor × {USABLE:.0%} usable ÷ {m2} m² per person.
4. **Who goes where.** One optimisation for the whole basin: first shelter as many people as possible, then keep the
   total distance travelled lowest. A shelter that fills up sends the next people to the next-nearest one.
   Road km = straight line × 1.3; no closed bridges or flooded roads.

**Limits.** Not an official shelter list: commune emergency plans (PLANU/PGUI in Belgium, Rampbestrijdingsplan in NL,
Katastrophenschutzplan in DE) name the real sites. OSM misses some buildings and many floor counts, so beds can be
over- or under-counted. Not everyone goes to a public shelter: in 2021 most people stayed with family or friends,
so this is a worst case. Toilets, showers, beds, heating, accessibility and staff are not modelled.
""")
