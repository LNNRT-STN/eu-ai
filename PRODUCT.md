# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python + Streamlit (user's choice), calling the Claude API from the Python side so the key never reaches the browser.
Map component inside Streamlit still to choose (folium / pydeck). Data comes from `outputs/data/` (pipeline scripts in `notebooks/`).

## Users

- **Primary: Anna**, a cross-border crisis coordinator (Liege BE, Limburg BE/NL, Aachen / Ahr DE). She has just received an early flood warning, and ministers and mayors are calling her. She is a policymaker, not a technical expert. Her job: decide and justify the FIRST action, then answer "are we better prepared than in 2021?".
- **First real viewers: the hackathon jury** (JRC and FARI, "AI for the common good"), seeing the platform projected during a 5-minute presentation. They score evidence-based policy, trustworthy analysis, and how AI output was checked.

## Product Purpose

One place that answers, in under one minute: are we better prepared than in 2021, where are we still exposed, and what is the first action. Success = someone outside the team names Anna's first action within 60 seconds (brief, phase 5).

## Positioning

Built only on public European data (Copernicus EMS, EFAS, GHSL GHS-POP and GHS-OBAT, Eurostat GISCO) plus OpenStreetMap, with every number traceable to a re-runnable script and shown with its uncertainty. It separates observed from modelled evidence and says where the data is silent (the Vesdre is not in the satellite flood map).

## Operating Context

- Scene: a lit conference room, the page projected on a large screen, read from several metres away for about 90 seconds while a presenter talks.
- Later scene (secondary): Anna at a desk during a warning, clicking into a town to brief a mayor.
- Delivered alongside a 2-page policy brief, an AI summary, and a 5-minute presentation.

## Capabilities and Constraints

- Confirmed: Q1 exposure and Q3 shelter coverage for 10 areas by municipality; Q4 ranking; 65 hospitals, care homes and schools in the flood zone; observed vs modelled flood; main vs worst-case flood map; low / central / high assumptions; data-quality report; outside-view comparison with official 2021 figures.
- Pending: Q2 evidence ("what changed since 2021") from the team's researchers. Never filled with invented content.
- Every number shown must exist in a re-runnable output; no number computed only in the UI.
- AI (Claude API): explains and drafts from our numbers; never produces a number itself; every AI text labelled and human-checked; logged in `ai_log.md`.
- Undecided: product name and identity (user: "nothing for now").

## Evidence on Hand

- `outputs/data/`: area_summary, municipalities, q4_ranking, q4_headline, critical_sites, shelters.geojson, flood_<area>_<main|worst>.geojson, dq_report, qc_and_validation.
- Official 2021 figures verified at source: Wallonia press release (July 2022), bpb (10 Jul 2023). See `ai_log.md`.
- Absent, must not be fabricated: Q2 evidence, official shelter lists, per-town published damage figures, any logo or endorsement.

## Product Principles

1. The first action leads; everything else is the evidence for it.
2. Every number carries its source and its range; observed and modelled are never mixed silently.
3. Unmapped is not safe: data gaps are shown, not hidden.
4. Calm command, not alarm: urgency comes from facts, not from styling.
5. Less on screen: if it cannot be understood in a minute, it moves one click deeper.

## Accessibility & Inclusion

Projected use: high contrast (WCAG AA minimum), large type, meaning never carried by colour alone (labels next to every colour).
