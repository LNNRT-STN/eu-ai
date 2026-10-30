# AI sheet

| Field         | Answer |
| ------------- | ------ |
| Team number   | [fill in] |
| AI tools used | Claude Code (Claude Opus) as co-analyst and coder, including background subagents for desk research and independent reviews; Claude with the team's book library for method references; Claude Haiku 5.5 through the Claude API inside the tool, only to word briefing drafts (every number comes from our engine). LightGBM was tested as a machine-learning technique and left out of the tool. |

## 1. How you used AI at each stage

| Stage                              | No AI | Team led, AI assisted or checked | AI and team together | AI did most of it | AI misled us here |
| ---------------------------------- | ----- | -------------------------------- | -------------------- | ----------------- | ----------------- |
| 1. Understanding the case and data |       |                                  | ✔                    |                   | ☒                 |
| 2. Loading and preparing data      |       |                                  |                      | ✔                 | ☐                 |
| 3. Analysis and code               |       |                                  |                      | ✔                 | ☒                 |
| 4. Maps and charts                 |       |                                  |                      | ✔                 | ☒                 |
| 5. Desk research and sources       |       |                                  | ✔                    |                   | ☒                 |
| 6. Interpreting results            |       | ✔                                |                      |                   | ☒                 |
| 7. Recommendation and brief        |       | ✔                                |                      |                   | ☐                 |
| 8. Policy tool                     |       |                                  | ✔                    |                   | ☒                 |

**1. Understanding the case and data.** We turned the case sheet into a project brief (`CHALLENGE_BRIEF.md`) with Claude and marked every unconfirmed point [VERIFY]. Claude profiled each dataset before any analysis. It first repeated the data catalogue's claim that GHS-OBAT has no building area. We checked the actual file fields and the official OBAT documentation (p.19-20), which showed a footprint area and a height. Our shelter capacity model is built on that correction.

**2. Loading and preparing data.** Claude wrote the pipeline (`notebooks/pipeline.py`, `osm_extract.py`, `dq_report.py`), and the team set the cleaning rules: overlapping flood shapes dissolved, a building counted once, missing values reported rather than filled, outliers capped and listed by name. When the public OpenStreetMap server kept timing out, we switched to official GISCO borders and local Geofabrik extracts. Every script ran on the smallest area (Schleiden) first. Automatic checks (people add up, no negatives, no shelter over capacity) caught three bugs before the full run.

**3. Analysis and code.** Claude wrote most of the code. The team chose each method by comparing options on evidence. We ran two population methods side by side and reported the 5-17x gap between them rather than hiding it. We replaced Claude's greedy shelter allocation with maximum flow after reading *Introduction to Algorithms* (ch.26). We tested a LightGBM flood model with leave-one-area-out validation and 95 % bootstrap intervals. It did not beat the official EFAS map, so we left it out. The final forecast uses the return-period rule that EFAS uses (a Gumbel fit to 1997-2025 annual peaks). July 2021 serves as a backtest, with thresholds fitted only on data up to 2020.

**4. Maps and charts.** Claude produced the charts and maps (`src/build_charts.py`, `notebooks/report_charts.py`, the 3D MapLibre view). We checked them with a palette validator and by rendering every page at desktop and phone width. The validator rejected the first red/orange palette. The renders showed numbers that added observed and modelled flood areas together, map circles covering half the region, and a stale cache serving old numbers. All of these were fixed. Observed and modelled numbers are now never added together on screen.

**5. Desk research and sources.** Research agents wrote sourced tables (`docs/BUDGETS.md`, `docs/TIMELINE_2021.md`, `docs/INFRA_2021.md`), with a URL on every row and each row marked verified, partly verified or not found. We did not trust search summaries. We opened the primary sources ourselves: the Wallonia press release of July 2022, bpb 2023, the RLP parliamentary paper 18/5776 and the Walloon inquiry report. A second AI pass checked the roles and translations against official sites and corrected three role rows. Lists of which district each town belongs to turned out wrong in eight or more places.

**6. Interpreting results.** The team led this stage. Where our numbers differed from published 2021 figures, we explained why instead of tuning them to match. For example, we count 7,202 buildings in the Ahr against "over 9,000" destroyed or damaged (bpb), because the satellite captured a snapshot, not the peak. Confidence intervals changed two planned claims: "terrain helps on the Ahr" was dropped because the gain was not significant. Interpolated hourly replay times made the tool look 24 hours earlier than the real Ahr order, so the screen now shows only the day.

**7. Recommendation and brief.** The team wrote the recommendation and chose the headline: evacuate before the river rises, because in narrow valleys most escape routes cross the 2021 water. Claude drafted text and charts for the brief. We checked every figure against the output files. Statements without a source stayed marked [VERIFY] or were removed, such as "often older residents".

**8. Policy tool.** Claude Code built the Streamlit tool in short steps. Several agents worked in parallel, each owning separate files, and the team set every product decision: action first, one first action, role launch screen, scenario replay, privacy by design for check-ins and spare beds. Each step was rendered in a real browser and the engine has automated tests (18 pass). Fresh AI reviewers with no prior context reviewed the tool twice against the data. They found 22 issues, 7 of them serious, and the lead checked each fix again.

## 2. Where did AI make the biggest difference to your work, and where did it let you down most?

AI made the biggest difference in speed and scope. In two days, a small team built a cross-border data pipeline, a shelter allocation model, a road simulation, a sourced 2021 timeline and a six-page tool with a live replay. Without AI this would have taken weeks. It also helped when we asked it to argue against itself: fresh reviewers and confidence intervals removed claims we would otherwise have presented. It let us down most where an output looked right but rested on something unverified: a data-catalogue sentence repeated as fact, a plausible district list, and an address search that gave a false all-clear. None of these produced an error message; we found them only by checking against the source or the screen.

## 3. Where the AI got it wrong

| # | Stage | What went wrong (one line) | How you noticed (one line) |
| - | ----- | -------------------------- | -------------------------- |
| 1 | 1. Understanding the data | Repeated the catalogue's "OBAT has no building area" and built a capacity model on it. | Profiled the real file fields and read the official OBAT documentation (p.19-20). |
| 2 | 3. Analysis and code | Optimal shelter allocation (max-flow) came out below the simple greedy one, which is impossible. | Our automatic check (max-flow ≥ greedy) fired; cause was rounding people to 0.1 per building. |
| 3 | 6. Interpreting results | Interpolated hourly replay times showed "evacuate" for the Ahr about 24 h before the real order, a gain that was not real. | An independent reviewer and our check of the daily river data against the RLP inquiry times. |
| 4 | 5. Desk research | Assigned towns to the wrong district (e.g. Maastricht under the Province of Liège), so briefings went to the wrong authority. | Listed every town per study area and read the result. |
| 5 | 8. Policy tool | Resident lookup told someone in a flooded single-storey home that their street was not in the 2021 water. | Typed the demo address "Ahrstraße 28" on screen before writing the demo script. |

## 4. Three key prompts

| # | Prompt | Tool | Why it worked (one line) |
| - | ------ | ---- | ------------------------ |
| 1 | "A teammate's dashboard used other choices. Decide on evidence, not by matching either side: test both methods on the Ahr, Erftstadt and Venlo and keep the one that holds." | Claude Code | Asked for a test, not agreement, which exposed physically impossible densities in both original methods. |
| 2 | "Review every page at desktop and phone width with no context from us: can Anna name her first action in under a minute, is every number the same everywhere, is anything claimed that the data does not show?" | Claude Code (fresh subagent) | A reviewer not anchored on our work found errors we had stopped seeing, such as observed and modelled numbers added together. |
| 3 | "Use the return periods in the forecast, not solely the 2021 floods; this is more a backtest; implement a forecast for the real-life use case with the available data." | Claude Code | Turned a hindsight replay into a forecast method EFAS also uses, with 2021 as an honest test on thresholds fitted before 2021. |

## 5. How you verified the results

- **Outside view first:** compared our counts with published 2021 figures opened at the source, not search summaries (Wallonia government July 2022, bpb 2023, RLP and Walloon inquiry reports).
- **Automatic checks in the code:** people buckets add up, no negatives, no shelter over capacity, max-flow ≥ greedy, walk + transport + no place = residents per town; 18 automated engine tests.
- **Smallest area first:** every script ran on one small area before the full run.
- **Statistics before claims:** leave-one-area-out validation and 95 % bootstrap intervals; claims without a significant gain were dropped.
- **Validation of the model proxy:** EFAS zones compared building by building with the observed flood in the Ahr and Liège (42 % and 75 % recall), so modelled numbers are shown as an order of magnitude.
- **Seeing it on screen:** every page rendered in a real browser at 1440 and 390 px; numbers checked across pages for the same town.
- **Independent AI reviews:** two fresh reviewers with no context; every finding re-checked by the lead in code or on screen.
- **Logged:** every AI step, its check and the team's decision are in `ai_log.md` (37 entries).

## 6. Limits and uncertainty

- **Satellite gaps:** the Copernicus EMS map misses most of the Vesdre (about 200 buildings mapped vs about 48,000 hit in Wallonia). The Vesdre figures there come from the EFAS model and are an order of magnitude only.
- **Model proxy:** EFAS zones ignore dikes (Meuse numbers are an upper bound) and underestimate narrow valleys (Bad Neuenahr-Ahrweiler: 4,214 modelled vs 15,933 observed in the water). Kall, Bad Münstereifel and Kelmis have no EFAS zone.
- **Backtest:** daily, modelled river flows give the day, not the hour, and they are hindsight. The modelled Altenahr peak is about 250 m³/s against a reconstructed 750-1,000.
- **Shelters:** candidate buildings from OpenStreetMap, capacity estimated from footprint and storeys. Their real availability, and free beds in receiving hospitals, are unknown. Distances are straight lines or road estimates.
- **Population:** spread over buildings by floor volume; the method spread is kept as a range (e.g. Venlo 206-525).
- **Still unverified:** who gives the order per town and the district list (team summary, to confirm with each emergency plan); warning messages need a native speaker; the care-home deaths line and two other 2021 failure lines are still [VERIFY]; some budget rows are only partly verified. Unit costs for flood-proofing could not be found.
- **No personal data:** we have no age or income data, so vulnerability is estimated from buildings (single-storey homes, care sites), not from people.
