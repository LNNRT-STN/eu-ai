import pandas as pd
import streamlit as st

import core
from core import about, fmt

core.style()  # the older analyst pages keep their custom look; the main pages use the theme only

d = core.load()
a = d["areas"][d["areas"].variant == "worst"]
obs, vesdre = a[a.area != "vesdre"].sum(numeric_only=True), a[a.area == "vesdre"].iloc[0]
rank, sites = d["rank"], d["sites"]

# Q2 desk research, Oct 2026: (area, theme, what changed, communes named, status, source label, url).
# Status is what the source says, not what we checked on the ground.
DONE, UNDERWAY, PLANNED, UNVERIFIED = "Done", "Under way", "Planned", "Not verified"
STATUS = {DONE: core.SHELTER, UNDERWAY: "#eb6834", PLANNED: "#e8b13a", UNVERIFIED: core.MISSED}
MEASURES = [
    ("Vesdre · BE", "Defences", "Phase 1: about 50 urgent works, mainly repairs and rebuilt river banks.", [], DONE,
     "L'Avenir, 25 Jun 2026", "https://www.lavenir.net/actu/environnement/2026/06/25/cinq-ans-apres-les-inondations-cataclysmiques-en-wallonie-le-gouvernement-fait-le-bilan-de-ce-qui-est-fait-et-de-ce-quil-reste-a-faire-BKHPCUNNCJBRNMEVO2ZVCW6DJE/"),
    ("Vesdre · BE", "Defences", "Phase 2: 14 works that give the river room (riverbed, banks), €453 M of which €300 M "
     "EIB loan. Launched 2026.", ["Chaudfontaine", "Theux", "Spa", "Pepinster", "Limburg"], UNDERWAY,
     "La Libre, 25 Jun 2026", "https://www.lalibre.be/dernieres-depeches/2026/06/25/inondations-en-wallonie-apres-les-travaux-durgence-14-chantiers-structurants-lances-en-2026-UAE76R5FWRDUBDTNXUCWPWJ5CU/"),
    ("Vesdre · BE", "Defences", "Verviers, Eupen and Trooz wait for the hydraulic model to finish. No start date.",
     ["Verviers", "Eupen", "Trooz"], PLANNED, "L'Avenir, 25 Jun 2026",
     "https://www.lavenir.net/actu/environnement/2026/06/25/cinq-ans-apres-les-inondations-cataclysmiques-en-wallonie-le-gouvernement-fait-le-bilan-de-ce-qui-est-fait-et-de-ce-quil-reste-a-faire-BKHPCUNNCJBRNMEVO2ZVCW6DJE/"),
    ("Vesdre · BE", "Buildings", "Communes bought and demolished homes in risk zones to widen the river. No total "
     "count published.", ["Verviers"], UNVERIFIED, "RTBF, Jul 2026",
     "https://www.rtbf.be/article/cinq-ans-apres-les-inondations-la-longue-reconstruction-le-long-de-la-vesdre-se-poursuit-11737500"),
    ("Vesdre · BE", "Buildings", "New town buildings built to flood: sockets above 1.5 m (Pepinster), car park as "
     "storm basin (Trooz).", ["Pepinster", "Trooz"], DONE, "RTBF, Jul 2026",
     "https://www.rtbf.be/article/cinq-ans-apres-les-inondations-la-longue-reconstruction-le-long-de-la-vesdre-se-poursuit-11737500"),
    ("Wallonia · BE", "Land use", "River-basin plans written into the planning code (CoDT): the minister can refuse "
     "a commune plan that ignores them.", [], DONE, "L'Avenir, 25 Jun 2026",
     "https://www.lavenir.net/actu/environnement/2026/06/25/cinq-ans-apres-les-inondations-cataclysmiques-en-wallonie-le-gouvernement-fait-le-bilan-de-ce-qui-est-fait-et-de-ce-quil-reste-a-faire-BKHPCUNNCJBRNMEVO2ZVCW6DJE/"),
    ("Vesdre · BE", "Evacuation", "Verviers evacuation plan redrawn on the 2021 water (4,600+ people). The old map "
     "had about 30 homes in its red zone.", ["Verviers"], DONE, "Vedia",
     "https://www.vedia.be/info/un-nouveau-plan-devacuation-en-cas-dinondation-verviers/110793"),
    ("Wallonia · BE", "Warning", "Parliament inquiry: 161 recommendations. SPW reports a new coordination centre "
     "(CORTEX) and closer work with the RMI. Secondary source only.", [], UNVERIFIED, "RTBF, 2022",
     "https://www.rtbf.be/article/inondations-de-l-ete-2021-la-commission-d-enquete-du-parlement-wallon-fait-plus-de-150-recommandations-10960941"),
    ("Vesdre · BE", "Awareness", "“Rives” platform (Jun 2026): map of works plus risk-culture material. Vesdre only "
     "so far. Verviers police and ULiège run a risk-culture project with residents.", ["Verviers"], DONE, "Vedia",
     "https://www.vedia.be/info/verviers-de-la-tragedie-des-inondations-une-culture-du-risque-en-action/209814"),
    ("Vesdre · BE", "Residents", "Five years on, residents say they still wait for visible protection; Trooz has "
     "almost no flood-able green space yet.", ["Trooz"], UNDERWAY, "VRT, 14 Jul 2026",
     "https://www.vrt.be/vrtnws/fr/2026/07/14/les-habitants-de-la-vallee-de-la-vesdre-attendent-des-mesures-vi/"),
    ("Limburg · NL", "Defences", "Maas dikes under the national HWBP: Arcen (4.8 km) being built, Well (3 km) "
     "starts 2027, Roermond harbour dike in draft. Legal norm by 2050.", ["Venlo", "Roermond"], UNDERWAY,
     "HWBP", "https://www.hwbp.nl/projecten/overzicht-projecten/limburg/arcen"),
    ("Limburg · NL", "Defences", "Geul at Valkenburg: wider channel, bypass tunnel or retention basins studied. "
     "No decision found.", ["Valkenburg aan de Geul"], PLANNED, "Waterschap Limburg",
     "https://www.waterschaplimburg.nl/publish/pages/7013/analyse_overstroming_valkenburg.pdf"),
    ("Limburg · NL", "Evacuation", "Revised flood emergency plan for Limburg 2026–2029, public comment Jul–Aug 2026.",
     [], UNDERWAY, "VR Zuid-Limburg", "https://www.vrzl.nl/actueel/vernieuwd-rampbestrijdingsplan-hoogwater-ter-inzage"),
    ("Inde · DE", "Defences", "Repairs: 11 of 12 destroyed walls in Zweifall replaced by natural banks; flood "
     "gravel cleared from the Inde in Eschweiler.", ["Stolberg (Rhld.), Kupferstadt", "Eschweiler, Stadt"], DONE,
     "WVER, Jul 2023", "https://blog.wver.de/2023/07/05/schadensbeseitigung-schreitet-gut-voran/"),
    ("Inde · DE", "Defences", "Retention basins at Rott and Mulartshütte, called the key measure by the mayors; "
     "procedure sped up Feb 2025. No completion date.", ["Stolberg (Rhld.), Kupferstadt", "Eschweiler, Stadt"],
     PLANNED, "Stadt Eschweiler", "https://www.eschweiler.de/aktuelles/news/regenrueckhaltebecken/"),
    ("Inde · DE", "Land use", "Inde/Vicht masterplan with 63 possible measures; flood concept due end 2026. "
     "Eschweiler adds €16.2 M for retention.", ["Stolberg (Rhld.), Kupferstadt", "Eschweiler, Stadt"], PLANNED,
     "WVER, Jul 2024", "https://blog.wver.de/2024/07/12/hochwassergefahren-vorbeugen/"),
    ("Inde · DE", "Care sites", "St.-Antonius-Hospital Eschweiler: evacuated in 2021, reopened 4 Oct 2021, ~€110 M "
     "rebuild funding. Sheet-pile walls were considered; not confirmed built.", ["Eschweiler, Stadt"], UNVERIFIED,
     "SAH Eschweiler", "https://www.sah-eschweiler.de/ueber-uns/unser-haus/historie"),
]
GAPS = [
    ("Hospitals and care homes in BE and NL", "No public record found of flood-proofing in the Vesdre or Limburg."),
    ("Power, drinking water, telecoms", "No source names flood-proofed substations, pumping stations or masts."),
    ("Schools and households", "No school programme or household-preparedness campaign found for these valleys."),
    ("BE-Alert", "Recommended by researchers; no source confirms a reform since 2021."),
    ("Rebuilt vs. left empty", "No commune publishes how many 2021 homes were rebuilt, bought out or abandoned."),
    ("The Ahr and the Erft", "In the maps since the cleaned data (Oct 2026); no desk research on measures there yet."),
]

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
