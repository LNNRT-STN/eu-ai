# CLAUDE CODE PROJECT BRIEF: Cross-Border Flood Preparedness Challenge

> Read this whole file before doing anything. It is the single source of truth for the project.
> Version 2: corrected against the official case sheet (photo of page 2). Where the case sheet and the kickoff speech differ, **the case sheet wins**.
> Items marked **[VERIFY]** are still unconfirmed and must be checked against the annexes (Google Drive).

---

## 1. Context

- **Event:** 2-day "AI for the common good" hackathon organised by the **European Commission Joint Research Centre (JRC)** and **FARI** (Brussels AI institute).
- **Today:** Thursday 29 Oct 2026. Presentation to the jury is **tomorrow (Fri 30 Oct)**.
- **Team profiles:** coders (data analysis), researchers (desk research), communicators (policy brief). Everyone helps everyone.
- **AI tool:** Claude, through the dedicated event account (participant + number). Use a separate browser or incognito.
- **Organisers' purpose:** test what can be done with **public European data + widely available AI tools** (sovereignty angle).

### The scenario

- **July 2021:** floods hit the cross-border region of **Liège (BE), Limburg (BE), Dutch Limburg (NL), and Aachen / Ahr (DE)**. Case-sheet focus areas: **Ahr, Vesdre and Meuse**. Two months of rain fell in a few days: billions of euros of damage, **200+ deaths**.
- **We work for "Anna", a cross-border crisis coordinator.** In the 2026 scenario she receives an **early flood warning bulletin** (fictional). Ministers and mayors are calling her.
- She has 2021 data but **no single tool** answering "after everything that happened, are we better prepared?", and no way to present the evidence.
- **Only stakeholder is Anna** (a policymaker, not a technical expert).

---

## 2. Goal (exact wording from the case sheet)

> Give Anna an evidence-based, easy-to-understand answer to: **"Are we better prepared than in 2021, where are we still exposed, and what is the FIRST action I should take in response to this flood warning?"**

### 2a. The task in one line (key, from the case sheet)

> Produce a **present-state assessment** of the July 2021 floods: **what the water covered**, **what has been done
> in those areas since**, and **how the region would do if the same event returned tomorrow**.

Three time layers, and every page of the tool must sit in one of them and say which:

| Layer | Question | Evidence type |
|---|---|---|
| **Then** (July 2021) | Q1: what the water covered | Observed (Copernicus EMS) + modelled where the satellite was blind (Vesdre: EFAS 500-year), never summed |
| **Since** (2021 → Oct 2026) | Q2: what has been done | Desk research, every row sourced and marked verified / partly / unverified |
| **Tomorrow** (same event, today's buildings) | Q3: can we shelter them; Q4: where we still stand exposed, first action | Simulation on today's buildings, roads and shelters; replay of the 2021 river flows |

### 2b. Our stance: the tool fixes what went wrong in 2021

We do not only describe the 2021 flood: the tool is built to correct the failures that turned it into a disaster.
Each failure below must be backed by a cited source (`docs/TIMELINE_2021.md` for times, `docs/INFRA_2021.md`,
`docs/BUDGETS.md`). Lines marked **[VERIFY]** still need their source.

| 2021 failure | What the tool does instead | Where |
|---|---|---|
| EFAS warned on 10-13 July (flash-flood notices for the Ahr and Liège regions on 13 Jul, 11:25-11:26); NRW received none (`docs/TIMELINE_2021.md`) | River flow per town → status (watch / warn / evacuate) → a briefing for the mayor and fire brigade, drafted at once | Crisis room (`src/views/crisis.py`, `src/live.py`) |
| Evacuation orders came late: Vesdre 14 Jul 17:57, Ahr 14 Jul 23:09 (prosecutor: needed from 21:00), Erftstadt-Blessem 15 Jul ~08:10 (`docs/TIMELINE_2021.md`) | Replay shows when the tool would have said "evacuate" next to when the 2021 order came (day of the daily river flow, hindsight; stated on screen) | Crisis room replay |
| Warnings said "flood" but not what to do or where to go **[VERIFY]** | Ready warning message per town in the local language, with the shelter and the route | Town plan → Warning message |
| Unclear who gives the order across municipalities **[VERIFY]** | "Who gives the order" per town: mayor, then Kreis / governor / safety region | Town plan → Who gives the order |
| People who could not leave alone died (e.g. care home in Sinzig) **[VERIFY]** | Evacuate first: care sites in the water, single-storey homes (no upper floor to flee to) | Town plan → Evacuate first, 3D view |
| No shelter or route planned; roads and bridges went under | Dry candidate shelters within reach, capacity, who has no place; routes that cross 2021 water; rail and bridges cut | Town plan, Getting out |
| No overview of who is safe and who still needs a door knock | Resident check-in, crew door-knock list, road closures shared live | Check-ins and door-knock list, Do I need to leave? |
| Recovery money exists but is not tied to the gaps | Gap → measure → cited budget line | Long term (`docs/BUDGETS.md`) |

### 2c. Where each question is answered (for the jury and the brief)

| Question | In the tool | Evidence files | Known gaps to say |
|---|---|---|---|
| Q1 what the water covered | 2021 and today §1; All towns and care sites; Crisis room counters | `outputs/data/area_summary.csv`, `municipalities.csv`, `critical_sites.csv` | Satellite count is a floor; Vesdre modelled; residents an order of magnitude |
| Q2 what has been done since | 2021 and today §2; Long term | `docs/BUDGETS.md`, `docs/INFRA_2021.md` | Many measures announced, not verified as built |
| Q3 shelter with today's buildings | Town plan (walk / bus / no place, shelter map), Do I need to leave?, Offer a bed | `outputs/data/shelters.geojson`, `evac_towns.csv`; low / central / high capacity in `area_summary.csv` | OSM candidates, not official shelters; capacity estimated; distances are minimums |
| Q4 still exposed, first action | Crisis room (live replay, first towns to evacuate); Town plan first action line; Long term measures | `outputs/data/q4_ranking.csv`, `docs/ML.md` §8-9 | Replay uses hindcast flows, not the forecasts of the day; statuses by day (daily flows) |

---

## 3. Deliverables

| # | Deliverable | Key requirements |
|---|---|---|
| 1 | **Policy tool** (main evidence) | A non-expert understands it in **under 1 minute**. Must answer **"What is Anna's first action?"** Format free (interactive map, dashboard, one-page visual, web page). Creativity rewarded. |
| 2 | **Policy brief** | **2 pages**, printable, non-expert audience. **Use the provided template** **[VERIFY format/limits]**. The case sheet says Q4 is "where your policy brief lands its arguments". |
| 3 | **AI summary** | How AI was used as co-analyst. Assessed on whether output was **checked, directed and verified**, NOT on how much AI was used. |
| 4 | **5-minute presentation** (Fri) | Presents the policy tool to the jury. |

### Scoring
- Each of the 4 questions: **max 20 points** (80 total), scored by the jury tomorrow.
- Prizes: 1st = paid visit to JRC Ispra (Lake Maggiore, incl. European Crisis Management Laboratory); 2nd = unpaid FARI internship; 3rd = announced tomorrow.
- JRC principles: **evidence-based policy**, **trustworthy analysis** (findings based on data and facts), usefulness to ministers/mayors. A further criterion was cut off in the kickoff **[VERIFY]**.

---

## 4. The four questions (official wording and starting points from the case sheet)

```
   Q1                 Q2                    Q3                      Q4
 What did the     What has been done     Could we shelter the    Where do we still
 2021 floods      in those areas         exposed people, using   stand exposed?
 cover?           since?                 buildings standing      -> recommendation
                                         today?                  -> FIRST ACTION
   |                 |                      |                       |
 map + count      desk research          spatial + capacity      synthesis
 (coders)         (researchers)          (coders+researchers)    (everyone)
   \_________________|______________________|_______________________/
                  Q1 is the baseline: every other question builds on it
```

### Q1. What did the 2021 floods cover?
Map what the 2021 flood hit. Take the flood extent and lay it over maps of where people lived and what was built. Count what sat inside the water: **how many people, how many buildings, which towns and villages.** This is the baseline for every other question.
**Starting point:** Clip the **CEMS Rapid Mapping July 2021 extent** against gridded population (**GHS-POP**) and building points (**GHS-OBAT**).

### Q2. What has been done in those areas since?
Answered mainly through **desk research**; work in parallel with Q1. In the areas the 2021 flood hit, what has changed? Look for:
- new or reinforced **flood defences**
- buildings **rebuilt or left abandoned**, changes to **land use**
- **revised evacuation or shelter plans**
- **critical infrastructure**: were hospitals, care homes, power, water, telecoms flood-proofed?
- **risk communication and awareness**: flood-risk information campaigns, school programmes, community and volunteer networks, household preparedness

Gather what the public record shows, and **be honest about what you can't verify.**
**Starting point:** official recovery reports, regional government and water-authority sources, and news coverage for the **Ahr, Vesdre and Meuse** areas.

### Q3. Could we shelter the exposed people, using the buildings standing today?
**If the 2021 flood returned**, could Anna get the exposed population to safety using buildings that exist now? Identify safe places still standing: **sports halls, schools, community and civic buildings** large enough to take people. Work out **how many exposed residents actually have one within reach.**
**Starting point:**
- The people inside the 2021 flood zone (from Q1) are the group needing shelter.
- From **OpenStreetMap**, pull candidate shelters (schools, sports halls, similar).
- Cross-check or complement with other sources: building data (e.g. GHS-OBAT or national building registers) and official lists of schools, hospitals and designated emergency shelters.
- Shelters must be **outside the flood zone** and **big enough**. Estimate rough capacity.
- Work out how many people have a shelter within reach and **how many don't.**
- **Flag any hospitals or schools that sit inside the flood zone themselves.**

### Q4. Where do we still stand exposed?
Bring all findings together into a recommendation. Given what flooded, what has been done since, and where the shelter gaps are: **which areas remain most exposed, and what actions should Anna take first?**
**Starting point:** let the recommendation fall directly out of the findings. **Name the areas** that are still exposed and under-covered after **five years of recovery**, and **name the action.**

---

## 5. Data

Access instructions are in **Annex 1** (Google Drive). Data is several GB; use the provided notebook locally or **Google Colab**. Kickoff GitHub presentation (QR code) has links. **[VERIFY exact paths/filenames from Annex 1.]**

| Dataset | Source | Type / format | Content | Role in questions |
|---|---|---|---|---|
| **2021 flood extent** (CEMS Rapid Mapping, July 2021) | Copernicus On-Demand Mapping | Vector, Shapefile | **Real observed** flooded areas | **Q1 baseline, Q3 exposed group** |
| **Population grid (GHS-POP)** | GHSL, exposure mapping | Raster GeoTIFF | Residents per grid cell, **2020** and **2025 projection** | People counts (Q1, Q3, Q4) |
| **Building attribute table (GHS-OBAT)** | GHSL, exposure mapping | Vector GeoPackage (building points per case sheet) | Height, residential vs non-residential, etc. Reference year **2020** | Building counts (Q1), shelter candidates / capacity (Q3) |
| **Flood hazard maps** | EFAS, floods component | Raster GeoTIFF | Modelled scenarios, **10/100/500-year** return periods (500-year = 0.2% yearly probability) | Not named in the case-sheet starting points. **Optional** for Q4: forward-looking exposure for the 2026 warning, and sanity check against the 2021 extent |
| **OpenStreetMap** (external, public) | OSM | Vector | Schools, sports halls, civic buildings, hospitals | **Q3 candidate shelters** |
| **Official lists** (schools, hospitals, designated shelters, national building registers) | National/regional authorities | Various | Cross-check for Q3 | **Q3** |

Example overlay shown at kickoff: flood layer x building layer shows which buildings flooded (residential vs non-residential).

---

## 6. Step-by-step plan

### Phase 0: Setup (~15 min)
1. Read the case sheet and Annex 1 in the shared Drive; resolve every **[VERIFY]**.
2. Open the Colab notebook from Annex 1; confirm data loads.
3. Folder structure:
   ```
   project/
   ├── CHALLENGE_BRIEF.md
   ├── data/            (raw, never edited)
   ├── notebooks/       (one per question)
   ├── outputs/         (maps, charts, tables, final tool)
   ├── docs/            (policy brief draft, AI summary)
   └── ai_log.md        (section 8, keep updating)
   ```
4. Use **one metric CRS** for all analysis (e.g. EPSG:3035, or UTM 31N/32N = EPSG:32631/32632). EPSG:4326 only for web display.

### Phase 1: Q1, What did 2021 cover? (coders)
1. Load the **CEMS July 2021 flood extent**. Check CRS, repair invalid geometries, clip to study area (Ahr, Vesdre, Meuse).
2. Load **GHS-OBAT** buildings; spatial join with the flood polygons. Count flooded buildings, split residential / non-residential.
3. Load **GHS-POP (2020)**; mask with the flood polygons; sum to get **people in the flood zone** (handle partially covered cells by area-weighting; document the method).
4. Aggregate **by town/village/municipality** (use admin boundaries, e.g. GISCO/LAU **[VERIFY source]**). Produce a ranked table.
5. Output: baseline map + headline numbers (people, buildings, towns). Save the flood-zone population and building layers; **Q3 and Q4 reuse them.**

### Phase 2: Q2, What has been done since? (researchers lead)
1. Research per area (Ahr, Vesdre, Meuse; e.g. Verviers, Pepinster, Liège, Ahrweiler, Dutch Limburg) across the five categories in section 4 (defences, rebuilt/abandoned/land use, evacuation and shelter plans, critical infrastructure flood-proofing, risk communication and awareness).
2. Sources: official recovery reports, regional governments, water authorities, reputable news. **Record title, URL, date for every fact.**
3. Build an **evidence table**: area | what changed | category | source | confidence (verified / partly / unverified).
4. Explicitly list **what could not be verified** (the case sheet asks for honesty about this).
5. If coordinates exist, map defences / new shelters to overlay with Q1/Q3.
6. Optional data angle: compare 2020 vs 2025 population in flood zones (are people moving back?). Label as a modelled projection.

### Phase 3: Q3, Could we shelter the exposed? (coders + researchers)
1. **Exposed group** = people in the 2021 flood zone (from Q1), by area.
2. **Candidate shelters:** pull from OpenStreetMap (schools, sports halls, community/civic buildings, hospitals) for the study area; supplement/cross-check with GHS-OBAT, official school/hospital lists and designated shelters. De-duplicate across sources.
3. **Filter:** keep only buildings **outside** the 2021 flood zone and **large enough** (set and document a minimum size).
4. **Capacity estimate** (state assumptions clearly): e.g. footprint area x floors (from height) x usable fraction / m² per person. Mark as a rough estimate; test sensitivity (low/central/high).
5. **"Within reach":** define and justify a threshold (e.g. walking distance or travel time; use network distance if feasible, straight-line as fallback). Count exposed residents with at least one shelter within reach, and **how many have none**; also check whether local capacity is enough, not just proximity.
6. **Flag hospitals and schools inside the flood zone** themselves (list + map).
7. Output: shelter map, table of covered vs uncovered people by area, flagged-facility list.

### Phase 4: Q4, Where do we still stand exposed? (everyone)
1. Combine: people/buildings in the flood zone (Q1), verified improvements and unverified gaps (Q2), shelter coverage gaps (Q3).
2. Build a transparent **exposure-gap ranking** per area (e.g. uncovered people, flooded critical facilities, little evidence of improvement). Keep it simple and explainable; show the inputs.
3. Optional: overlay the **10/100/500-year hazard maps** to show that exposure goes beyond the 2021 footprint.
4. **Name the areas** still exposed and under-covered after five years, and **name the FIRST action** (specific, quantified, tied to evidence), plus 2-3 follow-up actions.

### Phase 5: Policy tool
- Passes the **1-minute test**: someone outside the team says "what should Anna do first?" within 60 seconds, or simplify.
- Suggested form: one interactive page: big headline action, 3 key numbers, map of exposed vs covered areas, "2021 vs now" comparison, sources.
- Design: one message per screen, plain language, honest uncertainty, labelled sources.

### Phase 6: Policy brief (2 pages, communicators lead)
| Section | Do | Don't |
|---|---|---|
| **Key takeaways** (top bullets) | 3-4 quantified findings/recommendations | Vague abstract or general statements |
| **Introduction** | Short; why it is **urgent** (200+ deaths in 2021, warning received now) | Research gap, "this paper will..." |
| **What science tells us** | **3 key insights**, one subsection each, concrete, quantified, **sourced** (natural fit: Q1 baseline, Q2 what changed, Q3 shelter gap) | Theory, long methods |
| **Policy implications** | Call to action, linking to the problem and **every** insight; Q4 recommendation lands here | Generic "more collaboration is needed" |

No methods section. Every number traceable to data or a cited source.

### Phase 7: AI summary
Write from `ai_log.md`: what AI was used for, what humans directed, what was checked and how, what AI got wrong and how it was caught.

### Phase 8: 5-minute presentation (Fri)
Flow: Anna's problem (30s) > Q1 baseline + Q2 changes (75s) > Q3 shelter gap (60s) > tool demo + **first action** (90s) > how we verified AI work (45s). Rehearse with a timer.

---

## 7. Verification rules (this is what gets graded)

AI is a co-analyst, not an oracle. For every result:
1. **Sanity-check scale and units** against published 2021 figures (deaths, damaged buildings, affected people).
2. **Cross-check independently** (official statistics, news, JRC reports); explain differences.
3. **Check CRS and geometry validity** before every spatial operation.
4. **Reproducibility:** every number in the brief comes from a re-runnable notebook cell.
5. **Visual spot-check:** zoom into 2-3 places and confirm joins/overlays on a map.
6. **State limitations:** GHS-POP is modelled (2025 is a projection); building data is 2020 (does not reflect rebuilding/demolition since); OSM completeness varies by country; capacity and "within reach" are assumptions; flood extent is an observed 2021 snapshot.
7. **No invented facts.** If it cannot be sourced, write "unverified".
8. **Log AI errors and corrections** in `ai_log.md`.

---

## 8. AI log (`ai_log.md`)

```
## [time] Topic
- Prompt/intent:
- AI output (short):
- How we checked it:
- Result: correct / corrected / rejected (+ what was wrong)
- Decision taken by the team:
```

---

## 9. Timeline

| Time | Activity |
|---|---|
| Thu 10:00-12:30 | Setup, Q1 analysis, start Q2 research. Coaches circulate. |
| Thu 12:30 | Short lunch |
| Thu afternoon | Deeper work (Q3, Q4), share progress between teams, start tool + brief |
| Thu evening / Fri morning | Finish tool, brief, AI summary; rehearse |
| Fri | 5-minute jury presentation (4 questions x 20 pts) |

Coaches today include Martin (JRC data expert), Veronica Herrera (Univ. of Liège), Francisco Rios (data scientist), Maxime Degé (mayor of Verviers, arriving later). Use them for local knowledge and sanity checks.

---

## 10. Instructions for Claude Code

1. Start by checking the project folder for Annex 1 paths, the case sheet and the brief template; resolve **[VERIFY]** items.
2. Work **one phase at a time**; show intermediate maps/tables and plain-language summaries for the team to validate.
3. Prefer Python: **geopandas, rasterio, shapely, pandas, osmnx (or Overpass), folium/plotly**. Clip early to the study area and read rasters in windows to save memory.
4. Never modify `data/`. Save outputs in `outputs/`. Keep code in notebooks/scripts.
5. Explain every number: how computed, what assumption, what uncertainty.
6. Keep `ai_log.md` updated.
7. Optimise for the 1-minute comprehension test and the goal sentence in section 2.

---

## 11. Open items

- [ ] Exact data paths/filenames (Annex 1) and whether GHS-OBAT is points or polygons in the provided file
- [ ] Study area boundary and admin boundary source
- [ ] Policy brief template format/limits and language (English assumed)
- [ ] Policy tool format constraints and how it is shown to the jury
- [ ] Third evaluation criterion (cut off in kickoff)
- [ ] Whether the 2026 warning specifies a scenario (case sheet Q3 uses "if the 2021 flood returned"; hazard maps are optional)
