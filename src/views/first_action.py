"""Home page: Anna's first action. All mapped areas (Ahr, Vesdre, Meuse, Eifel, Erft), shelter capacity per town.
Numbers come from outputs/data/ (notebooks/pipeline.py, q4_ranking.py); nothing is computed here beyond selection."""
import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import about, fmt

head, towns, crit, shel, flood, summary, qc = anna.load()

core.header("First action",
            "If the July 2021 flood came back tomorrow: who would have no shelter in reach, which care sites sit in the "
            "water, and what to do first. Every mapped area: Ahr, Vesdre, Meuse, Eifel and Erft.")

v = st.segmented_control("2021 flood map", list(anna.VARIANT), format_func=anna.VARIANT.get, default="worst",
                         required=True, help="All satellite passes is closer to the official 2021 figures (Ahr: 7,202 "
                                             "buildings in the water, against over 9,000 reported). The first pass alone "
                                             "is a lower bound.")
H, T = head[v], towns[towns.variant == v].copy()
obs, mod, sites = H["observed"], H["modelled_vesdre"], H["sites"]
C = crit[crit.share_of_site_flooded.ge(.05) & crit["in_worst_flood" if v == "worst" else "in_main_flood"].astype(bool)]
care = C[C.type.isin(["hospital", "care home"])]

# 1. the action, one sentence, then why
where = f", {sites['top_town_count']} of them in {anna.town(sites['top_town'])}" if sites["top_town"] else ""
core.banner(core.EVACUATE, f"Start evacuating the {sites['vulnerable']} hospitals and care homes that sat in the 2021 "
                           f"water{where}.",
            "Their residents cannot walk to a shelter and need the most time to move. Before acting, check with each "
            "site whether it was flood-proofed after 2021: that evidence is still being collected.", note=False)
st.space("small")

core.facts([
    (about(obs["no_shelter"]), f"<strong>people would find no shelter place</strong> where the satellite saw the 2021 "
                               f"water. {about(obs['no_shelter_range'][0])} to {about(obs['no_shelter_range'][1])} with "
                               "stricter or looser assumptions."),
    (about(mod["no_shelter"]), "<strong>more in the Vesdre valley</strong>, modelled. The satellite missed this valley, "
                               "so the EFAS 100-year zone stands in: an order of magnitude."),
    (fmt(len(care)), f"<strong>hospitals and care homes</strong> sit in the 2021 water, with {fmt((C.type == 'school').sum())} "
                     "schools."),
    (about(obs["full"]), "<strong>of them have a shelter within walking reach, but it is full.</strong> The gap is "
                         "space, not distance."),
], "Source · Copernicus EMS 2021 · EFAS 100-year (Vesdre) · GHS-POP 2020 · GHS-OBAT 2020 · OpenStreetMap shelters, "
   "capacity at 4 m² per person, 50 % of floor usable, 1.5 km on foot")
st.space("small")

# 2. follow-up steps, derived from the same table
far = T[T.no_reach > T.full].nlargest(2, "no_reach")
full = T[T.full >= T.no_reach].nlargest(3, "full")
core.group([
    ("<b>Assign streets to shelters</b>", "Plan who goes where instead of letting everyone head to the nearest hall: "
     f"{about(obs['coordination_gain'])} more people sheltered where the satellite saw the water, "
     f"{about(mod['coordination_gain'])} more in the Vesdre (modelled).", f"+{about(obs['coordination_gain'])}"),
    ("<b>Send buses where shelters are too far</b>",
     ", ".join(f"{r.label}: {about(r.no_reach)}" for r in far.itertuples()) + " people beyond 1.5 km on foot.",
     about(far.no_reach.sum())),
    ("<b>Open overflow space where shelters are full</b>",
     ", ".join(f"{r.label}: {about(r.full)}" for r in full.itertuples()) + " people with a shelter in reach but no room.",
     ""),
], "Then")
st.space("medium")

# 3. where the gap is: towns ranked, and the map
left, right = st.columns([5, 6], gap="medium")
T["no_shelter"] = T.no_reach + T.full
top = T.nlargest(12, "no_shelter")
with left:
    st.html("<div class='gh'>Towns with the most people and no shelter</div>")
    long = top.melt(id_vars=["label", "no_shelter", "people"], value_vars=["no_reach", "full", "covered"],
                    var_name="state", value_name="n")
    names = {"no_reach": "Too far: no shelter within 1.5 km", "full": "Shelter in reach but full", "covered": "Sheltered"}
    long["state"] = long.state.map(names)
    order = list(names.values())
    bars = alt.Chart(long).mark_bar(height=16, stroke="#fff", strokeWidth=2).encode(
        y=alt.Y("label:N", sort=list(top.label), title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X("n:Q", stack="zero", title="Residents in the 2021 water", axis=alt.Axis(format=",.0f", grid=True)),
        color=alt.Color("state:N", scale=alt.Scale(domain=order, range=[anna.TOO_FAR, anna.FULL, anna.SHELTERED]),
                        legend=None),
        order=alt.Order("rank:Q"),
        tooltip=[alt.Tooltip("label:N", title="Town"), alt.Tooltip("state:N", title=" "),
                 alt.Tooltip("n:Q", format=",.0f", title="Residents")],
    ).transform_calculate(rank=f"indexof({order}, datum.state)")
    text = alt.Chart(top).mark_text(align="left", dx=6, fontSize=12, color="#1d1d1f").encode(
        y=alt.Y("label:N", sort=list(top.label)), x=alt.X("people:Q"),
        text=alt.Text("no_shelter:Q", format=",.0f"))
    st.altair_chart(alt.layer(bars, text).properties(height=34 * len(top), background="#ffffff",
                                                     padding={"left": 12, "right": 40, "top": 10, "bottom": 8})
                    .configure_view(stroke=None).configure_axis(labelColor="#1d1d1f", titleColor="#6e6e73",
                                                                gridColor="#ececf0", domain=False, ticks=False),
                    width="stretch")
    core.legend("".join(core.swatch(c, lab) for c, lab in zip([anna.TOO_FAR, anna.FULL, anna.SHELTERED], order))
                + "<span>Number = people with no shelter</span>")

with right:
    pick = st.selectbox("Town", [None, *top.municipality], format_func=lambda m: "All mapped areas" if m is None else
                        top.set_index("municipality").label[m], label_visibility="collapsed",
                        placeholder="Pick a town to see its sites and shelters")
    sel = None if pick is None else T[T.municipality == pick].iloc[0]
    layers = []
    for a in anna.AREA:
        modelled = a in anna.MODELLED
        layers.append(pdk.Layer("GeoJsonLayer", flood[(a, v)], filled=True, stroked=modelled,
                                get_fill_color=[0, 113, 227, 45 if modelled else 95],
                                get_line_color=[0, 113, 227, 160], line_width_min_pixels=1))
    pts = T[T.no_shelter > 0].assign(
        r=lambda d: (d.no_shelter ** .5) * .32 + 3,          # area ~ people: 11,000 -> ~37 px, 200 -> ~8 px
        tip=lambda d: [f"<b>{x.label}</b><br>{fmt(x.no_shelter)} of {fmt(x.people)} residents with no shelter"
                       f"<br>{fmt(x.no_reach)} too far · {fmt(x.full)} shelter full" for x in d.itertuples()])
    layers.append(pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                            get_fill_color=core.rgb(anna.TOO_FAR, 150), get_line_color=[255, 255, 255],
                            line_width_min_pixels=1, stroked=True, pickable=True))
    layers.append(core.points(care.assign(tip=[f"<b>{n}</b><br>{t} · {w}<br>{s:.0%} of the site under water"
                                               for n, t, w, s in zip(care.name, care.type, care.town,
                                                                     care.share_of_site_flooded)]),
                              core.rgb(core.EVACUATE), 6))
    # whole study area (Rochefort to Venlo, Liège to Sinzig) in one frame, or the picked town
    vs = (pdk.ViewState(longitude=6.25, latitude=50.78, zoom=7.25) if sel is None else
          pdk.ViewState(longitude=sel.lon, latitude=sel.lat, zoom=11.5))
    core.deck(layers, vs, 520)
    core.legend(core.swatch("rgba(0,113,227,.37)", "2021 water, satellite")
                + core.swatch("rgba(0,113,227,.18)", "Vesdre, 100-year model")
                + core.swatch(anna.TOO_FAR, "People with no shelter (circle size)", True)
                + core.swatch(core.EVACUATE, "Hospital or care home in the water", True))

# 4. one town, one level deeper
if sel is not None:
    st.space("medium")
    a, b = st.columns(2, gap="medium")
    with a:
        core.group([
            ("<b>Residents in the 2021 water</b>", "Order of magnitude: GHS-POP 2020 spread over homes by floor volume",
             f"≈ {about(sel.people)}"),
            ("<b>Sheltered</b>", "Best plan, shelters within 1.5 km on foot", fmt(sel.covered)),
            ("<b>Shelter in reach but full</b>", "Needs overflow space or a coordinated plan", fmt(sel.full)),
            ("<b>Too far</b>", "No shelter within 1.5 km: needs transport", fmt(sel.no_reach)),
            ("<b>Evidence</b>", "Modelled: EFAS 100-year zone, the satellite missed this valley" if sel.area in anna.MODELLED
             else "Observed: Copernicus EMS satellite map, July 2021", ""),
        ], sel.label)
    with b:
        here = C[(C.town == sel["name"]) & (C.area == sel.area)].sort_values("share_of_site_flooded", ascending=False)
        core.group([(f"<b>{r.name}</b>", r.type, f"{r.share_of_site_flooded:.0%} under water") for r in here.itertuples()]
                   or [("No hospital, care home or school in the water", "", "")], "Sites in the water")
        st.space("small")
        near = shel[(shel.town == sel["name"]) & (shel.area == sel.area)].nlargest(5, "capacity_central")
        core.group([(f"<b>{r.name if isinstance(r.name, str) else 'Unnamed ' + r.cat}</b>", r.cat,
                     f"≈ {about(r.capacity_central)} places") for r in near.itertuples()]
                   or [("No candidate shelter inside the town", "Look at neighbouring towns", "")],
                   "Largest dry candidate shelters in the town",
                   "OpenStreetMap schools, sports halls and civic buildings, dry in 2021 and in the 100-year model. "
                   "Capacity is an estimate: confirm with the commune.")

st.html("<p class='asof'>How each number was checked against the official 2021 figures: Data &amp; limits.</p>")
