"""2021, today, next: the present-state assessment of the July 2021 floods in three layers (CHALLENGE_BRIEF.md
§2a-2c). What the water covered (with the per-municipality map from risk_areas.py), what has been done there since
(desk research below), and what to fix with the money that exists for it (long_term.py). July 2021 data only:
outputs/data/ (core.D2021), never the return-period scenario of the response pages."""
import re

import streamlit as st

import anna
import core
from core import about, fmt
from views import long_term, risk_areas

core.style()  # grouped lists, facts strip and banner

d = core.load(core.D2021)
a = d["areas"][d["areas"].variant == "worst"]
obs, vesdre = a[a.area != "vesdre"].sum(numeric_only=True), a[a.area == "vesdre"].iloc[0]
rank, sites = d["rank"], d["sites"]

from measures import DONE, GAPS, MEASURES, PLANNED, STATUS, UNDERWAY, UNVERIFIED  # noqa: F401  Q2 desk research


named = {c for *_, cs, _, _, _ in MEASURES for c in cs}
count = {s: sum(m[4] == s for m in MEASURES) for s in STATUS}
pill = lambda lab: core.chip(lab, STATUS[lab])
first = lambda t: re.split(r"(?<=\.) (?=[A-Z“])", t, maxsplit=1) + [""]  # headline sentence, then the rest
n = long_term.numbers()
care = sites[sites.in_worst_flood & (sites.type != "school")]
school = sites.in_worst_flood & (sites.type == "school")
sch_obs, sch_mod = (school & ~sites.area.isin(anna.MODELLED)).sum(), (school & sites.area.isin(anna.MODELLED)).sum()

core.header("2021, today, next", "What the July 2021 water covered, what has been done in those places since, and "
                                 "what to fix before it comes back, with the money that exists for it.")
st.space("small")
core.banner("#7b3fd1", f"2021 reached at least {fmt(obs.buildings)} buildings in {fmt((~rank.modelled).sum())} "
            "municipalities. Five years on, most structural protection is still being built, and the gaps are in "
            "prevention and preparedness, not in rebuilding money.",
            f"<b>Covered:</b> ≈ {about(obs.people_2020)} residents in the observed water, a floor; the Vesdre, missed "
            f"by the satellite, holds ≈ {about(vesdre.people_2020)} more in the modelled 500-year zone, never added. "
            f"<b>Since:</b> of {len(MEASURES)} measures on the public record, {count[DONE]} are done (mostly urgent "
            f"repairs), {count[UNDERWAY]} under way, {count[PLANNED]} planned and {count[UNVERIFIED]} not verified; "
            "the works that give rivers room, the Maas dikes and the retention basins run to 2027–2050. "
            f"<b>If it came back tomorrow:</b> ≈ {about(n['obs']['no_shelter'])} residents would have no shelter place "
            f"on foot (≈ {about(n['mod']['no_shelter'])} more modelled in the Vesdre) across {n['gap_towns']} towns, "
            f"and {n['care']} hospitals and care homes sit in the same water. About a fifth of Germany's rebuilding "
            "fund is paid out; the Ahr's three priority retention basins (about €300 m) have no funding.", note=False)
st.space("small")

t1, t2, t3 = st.tabs([":blue[:material/water:] What the water covered", ":orange[:material/construction:] What changed since",
                      ":red[:material/build:] What to fix"])

with t1:
    core.facts([
        (fmt(obs.buildings), f"<strong>buildings inside the mapped water</strong>, {fmt(obs.residential)} of them homes"),
        (about(obs.people_2020), "<strong>residents inside the water</strong>, an order of magnitude"),
        (fmt(obs.flood_km2), "<strong>km² of water</strong> mapped by the satellite across nine areas"),
        (fmt(len(care)), f"<strong>hospitals and care homes</strong> in the water, plus {fmt(sch_obs)} schools "
                         f"(+{fmt(sch_mod)} modelled in the Vesdre)"),
    ])
    st.caption(":orange[:material/info:] A floor, not a total: the satellite saw little in the narrow Vesdre valley and "
               "central Liège. The Vesdre is modelled and never added to observed counts.",
               help=f"Ahr: {fmt(a.set_index('area').buildings['ahr'])} buildings here vs over 9,000 reported (bpb, "
                    "2023). Press figures for the Vesdre run far higher (Verviers alone: about 10,000 people "
                    "displaced, Etopia 2025). The facts above use all satellite passes.")
    rp = {ar: (x["RP100"], x["RP500"]) for ar, x in d["qc"]["efas_validation"].items()}
    st.caption(f":blue[:material/compare:] 2021 against the return-period zones of the response pages: on the Ahr the "
               f"EFAS 100-year zone holds {rp['ahr'][0]['recall']:.0%} of the {fmt(rp['ahr'][0]['observed_flooded'])} "
               f"buildings the satellite saw flooded, the 500-year zone {rp['ahr'][1]['recall']:.0%}; in Liège "
               f"{rp['liege'][1]['recall']:.0%} of the {fmt(rp['liege'][1]['observed_flooded'])}.",
               help="Buildings inside both the satellite water and the EFAS zone, over the buildings in the satellite "
                    "water (outputs/data/qc_and_validation.json). On the Ahr the 2021 water reached well beyond the "
                    "modelled 500-year zone; in Liège the satellite saw little, so the share says little.")
    st.space("small")
    risk_areas.render(frozenset(named))
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(f"""
- **Water:** {core.AS_OF['obs']}. All satellite passes is the headline; first pass only is a lower bound.
- **Vesdre:** {core.AS_OF['model']}. The 100-year zone stands in for the first pass, the 500-year zone for all passes.
- **Sites:** {core.AS_OF['osm']}. Hospitals, care homes and schools count when at least 5 % of the site is in the water.
- **Residents:** GHS-POP grid spread over each cell's homes by floor volume: an order of magnitude, not a head count.
  “Same homes, 2025” uses the 2025 projection.
- **Change column:** the municipality is named in a measure under “What changed since”.
- **Map:** © CARTO, © OpenStreetMap contributors; municipalities Eurostat GISCO LAU 2021 (© EuroGeographics).""")

with t2:
    st.caption(":orange[:material/info:] Status is what the source reports, not checked on the ground.",
               help="Desk research, October 2026: official, water-authority and press sources. The Ahr and the Erft "
                    "are not yet researched.")
    core.legend("".join(core.swatch(c, f"{lab} · {count[lab]}") for lab, c in STATUS.items()))
    regions = list(dict.fromkeys(r.split(" · ")[1] for r, *_ in MEASURES))
    for tab, cc in zip(st.tabs([f"{core.COUNTRY[c]} · {sum(m[0].endswith(c) for m in MEASURES)}" for c in regions]),
                       regions):
        with tab:
            rows = [m for m in MEASURES if m[0].endswith(cc)]
            core.group([(f"<b>{theme}</b> · {area.split(' · ')[0]}", first(what)[0], pill(status))
                        for area, theme, what, _, status, _, _ in rows])
            with st.expander("Detail and sources", icon=":material/link:"):
                st.markdown("\n".join(
                    f"- **{theme} · {area.split(' · ')[0]}** ({status.lower()}). {what}"
                    + (f" Named: {', '.join(cs)}." if cs else "") + f" [{src}]({url})"
                    for area, theme, what, cs, status, src, url in rows))
    st.space("small")
    core.group([(f"<b>{t}</b>", g, pill(UNVERIFIED)) for t, g in GAPS], "What we could not verify",
               "Absence in our search is not proof nothing was done: ask the commune, SPW, Waterschap Limburg or WVER.")

with t3:
    long_term.render()
