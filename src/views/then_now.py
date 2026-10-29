import pandas as pd
import streamlit as st

import core
from core import about, fmt

d = core.load()
a = d["areas"][d["areas"].variant == "worst"]
obs, vesdre = a[a.area != "vesdre"].sum(numeric_only=True), a[a.area == "vesdre"].iloc[0]
rank, sites = d["rank"], d["sites"]

from measures import DONE, GAPS, MEASURES, PLANNED, STATUS, UNDERWAY, UNVERIFIED  # noqa: F401  Q2 desk research

core.header("2021 and today", "What the July 2021 flood hit, and what the public record shows has changed in "
                               "those places since.")
st.space("small")
core.banner(core.EVACUATE, f"2021 reached at least {fmt(obs.buildings)} buildings in {fmt((~rank.modelled).sum())} "
            "municipalities. Five years on, most structural protection is still being built.",
            f"Repairs are done. The works that give rivers room (Vesdre), the Maas dikes (Limburg) and the retention "
            f"basins (Inde) run to 2027–2050. The Vesdre valley, missed by the satellite, holds ≈ "
            f"{about(vesdre.people_2020)} residents in the modelled 500-year zone.", note=False)
st.space("small")

# Q1 ------------------------------------------------------------------------------------------------------------
st.subheader("1 · What the 2021 flood hit")
care = sites[sites.in_worst_flood & (sites.type != "school")]
core.facts([
    (fmt(obs.buildings), f"<strong>buildings inside the mapped water</strong>, {fmt(obs.residential)} of them homes"),
    (about(obs.people_2020), "<strong>residents inside the water</strong>, an order of magnitude"),
    (fmt(obs.flood_km2), "<strong>km² of water</strong> mapped by the satellite across nine areas"),
    (fmt(len(care)), f"<strong>hospitals and care homes</strong> in the water, plus "
                     f"{fmt((sites.in_worst_flood & (sites.type == 'school')).sum())} schools"),
], "Source · " + core.AS_OF["obs"] + " · all satellite passes")
st.caption("A floor, not a total: the satellite saw little in the narrow Vesdre valley and central Liège. Ahr: "
           f"{fmt(a.set_index('area').buildings['ahr'])} buildings here vs over 9,000 reported (bpb, 2023). Press "
           "figures for the Vesdre run far higher (Verviers alone: about 10,000 people displaced, Etopia 2025).")

named = {c for *_, cs, _, _, _ in MEASURES for c in cs}
hit = rank.assign(name=core.plain(rank.municipality)).assign(
    seen=lambda d: d.modelled.map({True: "Missed by satellite · modelled", False: "Mapped"}),
    found=lambda d: d.name.isin(named).map({True: "See below", False: "–"}),
    country=lambda d: d.country.map(core.COUNTRY)).sort_values("people", ascending=False)
st.dataframe(hit[["municipality", "country", "seen", "people", "people_first_pass", "found"]],
             hide_index=True, height=360, column_config={
                 "municipality": "Municipality", "country": "Country", "seen": "July 2021",
                 "people": st.column_config.NumberColumn("Residents in the water", format="localized",
                                                         help="All satellite passes"),
                 "people_first_pass": st.column_config.NumberColumn("First pass only", format="localized"),
                 "found": st.column_config.TextColumn("Change on record", help="Named in a measure in section 2.")})
st.space("small")

# Q2 ------------------------------------------------------------------------------------------------------------
st.subheader("2 · What has changed since")
st.caption("Desk research, October 2026: official, water-authority and press sources. Status is what the source "
           "reports, not checked on the ground.")
core.legend("".join(core.swatch(c, lab) for lab, c in STATUS.items()))
pill = lambda lab: (f"<span class='pill' style='background:{STATUS[lab]};color:"
                    f"{'#1d1d1f' if lab == PLANNED else '#fff'}'>{lab}</span>")
areas = list(dict.fromkeys(a.split(" · ")[1] for a, *_ in MEASURES))
for tab, cc in zip(st.tabs([core.COUNTRY[c] for c in areas]), areas):
    with tab:
        core.group([(f"<b>{theme}</b> · {area.split(' · ')[0]}",
                     f"{what} <a href='{url}' target='_blank'>{src}</a>", pill(status))
                    for area, theme, what, _, status, src, url in MEASURES if area.endswith(cc)])
st.space("small")
core.group([(f"<b>{t}</b>", d, pill(UNVERIFIED)) for t, d in GAPS], "What we could not verify",
           "Absence in our search is not proof nothing was done: ask the commune, SPW, Waterschap Limburg or WVER.")
