# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python + Streamlit (`streamlit run src/dashboard.py`), pydeck and Altair for maps and charts. Any Claude API call runs on the Python side so the key never reaches the browser.

## Users

- **Primary (the challenge case): Anna**, a cross-border crisis coordinator for Liège BE, Limburg BE/NL and Aachen / Ahr DE. She has just received an early flood warning; ministers and mayors are calling her. A policymaker, not a technical expert. Her job: decide and justify the FIRST action, and answer "are we better prepared than in 2021?".
- **Crisis and risk managers** in provincial or municipal crisis cells (Meuse basin: Liège/Vesdre/Ourthe, Lesse, Dutch Limburg, Rur/Inde; Rhine side: Ahr, Erft, Eifel) who decide whom to warn, which sites to evacuate first and where people can go. Used in quiet weeks (preparedness) and in the days before a flood (response).
- **First real viewers: the hackathon jury** (JRC and FARI), seeing the tool projected during a 5-minute presentation.

## Product Purpose

Turn the July 2021 flood evidence and a live river outlook into actions: is a flood coming, which communes and care sites are exposed, whether the exposed people can be sheltered in buildings standing today, and what the first action is. Success: someone outside the team names Anna's first action within 60 seconds.

## Positioning

Built only on public European data plus OpenStreetMap. Ties a live GloFAS ensemble river outlook, rated on each river's own 2-, 5- and 20-year floods (backtested on July 2021), to the people and sites that sat in the 2021 water, with shelter capacity per town and every number traceable to a re-runnable script. Separates observed from modelled evidence and says where the data is silent (the Vesdre is not in the satellite flood map).

## Operating Context

European AI Challenge 2026 hackathon deliverable (policy tool), judged on evidence, policy usefulness, clarity, and how AI output was checked. Streamlit app run locally; shown projected in a lit room. Official warnings come from SPW, Rijkswaterstaat and the German state flood centres; this tool is a heads-up and a planning aid.

## Capabilities and Constraints

- Challenge data: Copernicus EMS rapid mapping, EFAS 10/100/500-year hazard, GHS-OBAT buildings, GHS-POP. External: Eurostat GISCO LAU communes, Open-Meteo (GloFAS, rain), OpenStreetMap facilities.
- Two pipelines: `src/` (Meuse scope, outlook, priority score, candidate sites) and `notebooks/` (all mapped areas incl. Ahr, shelter capacity from OBAT footprint x storeys, max-flow shelter allocation, Q4 ranking, EFAS validation, data-quality report).
- Shelters are candidate sites from OSM, not official shelters; capacity is an estimate with low / central / high assumptions.
- 2021 counts are a floor (the radar missed the Vesdre valley and central Liège). Residents are an order of magnitude.
- AI writes words, never numbers; every AI text is labelled and human-checked; logged in `ai_log.md`.
- Works offline without the outlook. Product name and identity: undecided.

## Evidence on Hand

`src/out/meuse/` (summary, communes, cells, regions, sites, priority, replay), `outputs/data/` (area_summary, municipalities, q4_ranking, q4_headline, critical_sites, shelters, flood layers, dq_report, qc_and_validation), `docs/METHODOLOGY.md`, `ai_log.md`. Official 2021 figures verified at source (Wallonia July 2022, bpb July 2023). Absent, never fabricate: official shelter lists, measured gauge data, Q2 evidence until the researchers deliver it, any logo or endorsement.

## Product Principles

1. Lead with the decision, then the evidence.
2. Every number names its source, its range and its limit; observed and modelled are never mixed silently.
3. Disclose depth progressively: verdict, then list, then detail.
4. Unmapped is not safe; candidate is never presented as official.
5. Calm command, not alarm: urgency comes from facts, not from styling.

## Accessibility & Inclusion

Projected use: high contrast (WCAG AA minimum), meaning never carried by colour alone (labels or icons next to every colour); red/green pairs avoided or backed by labels.
