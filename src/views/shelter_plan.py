import altair as alt
import pandas as pd
import streamlit as st

import core
from core import about, fmt

d = core.load()
areas, rank, munis, shelters, sites = d["areas"], d["rank"], d["towns"], d["shelters"], d["sites"]
STATUS = {"Shelter place": core.SHELTER, "Shelters in reach full": core.GAP["Shelters full"][0],
          "No shelter in reach": core.GAP["No shelter in reach"][0]}

core.header("Shelter plan", "If the water comes back, can everyone in it walk to a dry shelter with room? People are "
                            "matched to shelters by the best possible plan for each area, every place within reach used.")

c1, c2 = st.columns([1, 1], vertical_alignment="bottom")
variant = c1.segmented_control("Who needs shelter", list(core.VARIANT), format_func=core.VARIANT.get, default="worst",
                               required=True)
case = c2.segmented_control("Assumptions", list(core.REACH), format_func=str.capitalize, default="central",
                            required=True, help=" · ".join(f"{k.capitalize()}: {v}" for k, v in core.REACH.items()))

a = areas[areas.variant == variant].assign(
    modelled=lambda x: x.area == "vesdre", people=lambda x: x.people_2020, covered=lambda x: x[f"{case}_covered"],
    no_reach=lambda x: x[f"{case}_no_reach"], full=lambda x: x[f"{case}_full"],
    gain=lambda x: x[f"{case}_covered"] - x[f"{case}_covered_nearest_first"])
obs, mod = a[~a.modelled].sum(numeric_only=True), a[a.modelled].iloc[0]
core.facts([(about(obs.people), "<strong>people to shelter</strong> in the observed water, " + core.REACH[case]),
            (f"{obs.covered / obs.people:.0%}", f"<strong>get a place in walking reach</strong> (≈ {about(obs.covered)})",
             core.SHELTER, True),
            (about(obs.no_reach + obs.full), f"<strong>left over</strong>: {about(obs.no_reach)} with no shelter in reach, "
                                             f"{about(obs.full)} because the shelters in reach are full",
             core.EVACUATE, True),
            (about(obs.gain), "<strong>more placed by coordinating</strong> than if everyone walks to the nearest "
                              "shelter")],
           f"Modelled Vesdre, kept apart: ≈ {about(mod.people)} people, {mod.covered / mod.people:.0%} placed. "
           "Source · " + core.AS_OF["obs"] + " · " + core.AS_OF["osm"])
st.space("small")

left, right = st.columns([1, 1], gap="medium")
with left:
    st.html("<div class='gh'>Per area · " + core.REACH[case] + "</div>")
    long = a.melt(id_vars=["name", "people"], value_vars=["covered", "full", "no_reach"], var_name="k", value_name="n")
    long["status"] = long.k.map({"covered": "Shelter place", "full": "Shelters in reach full",
                                 "no_reach": "No shelter in reach"})
    order = list(a.sort_values("people", ascending=False).name)
    st.altair_chart(alt.Chart(long).mark_bar(cornerRadius=2).encode(
        y=alt.Y("name:N", sort=order, title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X("n:Q", stack="zero", title="People"),
        color=alt.Color("status:N", scale=alt.Scale(domain=list(STATUS), range=list(STATUS.values())),
                        legend=alt.Legend(orient="bottom", title=None)),
        order=alt.Order("k:N"),
        tooltip=[alt.Tooltip("name:N", title="Area"), "status:N", alt.Tooltip("n:Q", format=",.0f", title="People")],
    ).properties(height=340, background="#ffffff").configure_view(stroke=None)
     .configure_axis(gridColor="#ececf0", domain=False, labelColor="#1d1d1f", titleColor="#6e6e73"), width="stretch")
    st.caption("Vesdre valley: modelled, not observed. Do not add it to the other areas.")

with right:
    m = munis[(munis.variant == variant) & (munis.no_shelter >= 1)].sort_values("no_shelter", ascending=False)
    layers = core.water(variant) + [
        core.points(shelters.assign(fill=[core.rgb(core.KIND[k], 200) for k in shelters.type],
                                    tip=[f"<b>{n}</b><br>{t} · ≈ {c:,.0f} places" for n, t, c in
                                         zip(shelters.name, shelters.type, shelters.capacity_central)]), "fill", 3, 0),
        core.towns(m.assign(tip=[f"<b>{x}</b><br>≈ {about(n)} without a place: {about(r)} too far, {about(f)} full"
                                 for x, n, r, f in zip(m.municipality, m.no_shelter, m.no_reach, m.full)]),
                   "no_shelter", core.rgb(core.EVACUATE, 220), 18)]
    core.deck(layers, core.view(core.bbox(variant)), 400)
    core.legend("".join(core.swatch(h, k, True) for k, h in core.KIND.items())
                + core.swatch(core.EVACUATE, "People without a place, central case", True),
                core.swatch(core.WATER, "2021 water") + core.swatch(core.MODEL, "Vesdre, modelled water"))

st.subheader("Where the plan falls short", anchor=False)
if m.empty:
    st.success("Every resident has a shelter place within walking reach.", icon=":material/check_circle:")
else:
    core.group([(f"<b>{x}</b>" + (" · modelled" if mo else ""), f"{about(r)} have no shelter within 1.5 km · "
                 f"{about(f)} find the shelters in reach full", f"<b>{about(n)}</b> of {about(p)}")
                for x, n, r, f, p, mo in m.head(8)[["municipality", "no_shelter", "no_reach", "full", "people",
                                                     "modelled"]].itertuples(index=False)],
               foot="Central assumptions, per municipality. Fixes: buses to sites further away, pre-agree extra sites "
                    "with the neighbouring commune, or ask the province for a regional reception centre.")
    st.download_button("Download shortfall per municipality", m.drop(columns=["lon", "lat"]).to_csv(index=False),
                       f"shelter_shortfall_{variant}.csv", icon=":material/download:", type="tertiary")

st.subheader("Care sites and schools in the water", anchor=False)
st.caption("These cannot be used as shelters, and hospitals and care homes need their own evacuation first.")
st.dataframe(sites[sites[f"in_{variant}_flood"]].sort_values("share_of_site_flooded", ascending=False)[
    ["name", "type", "municipality", "share_of_site_flooded"]], hide_index=True, column_config={
    "name": "Site", "type": st.column_config.TextColumn("Type", width="small"), "municipality": "Municipality",
    "share_of_site_flooded": st.column_config.ProgressColumn("In the water", format="percent", min_value=0,
                                                             max_value=1, width="small")})

with st.expander("How the plan is made"):
    st.markdown("""
1. **Who moves.** GHS-POP 2020 residents spread over the residential buildings inside the July 2021 water, by floor
   volume (footprint × storeys). Vesdre: EFAS 100-year zone (first-pass view) or 500-year zone (all passes).
2. **Where to.** OpenStreetMap schools, sports halls and civic buildings, merged per campus, at least 200 m² of
   floor, dry in the 2021 water and outside the EFAS 100-year zone.
3. **How many fit.** Floor area × usable share ÷ space per person: low 40 % and 5 m², central 50 % and 4 m²,
   high 60 % and 3 m².
4. **Who goes where.** Maximum flow per area: as many people as possible get a place within walking reach (1, 1.5
   or 2.5 km in a straight line). “More placed by coordinating” compares this with everyone walking to the nearest
   shelter.

**Limits.** Not an official shelter list: commune emergency plans (PLANU/PGUI in Belgium, Rampbestrijdingsplan in NL,
Katastrophenschutzplan in DE) name the real sites. Straight-line distance understates walks in steep valleys. Not
everyone goes to a public shelter: in 2021 most people stayed with family or friends, so this is a worst case. No age
data; toilets, heating, accessibility and staff are not modelled. Full method: outputs/data/README.md.
""")
