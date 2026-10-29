# Platform spec: "Anna's First Action"

Version 1, Thu 29 Oct 2026. Owner: data team. Built on `outputs/data/` produced by `notebooks/pipeline.py` and `notebooks/q4_ranking.py`.

## 1. Purpose
Give Anna (cross-border crisis coordinator, not a technical expert) an evidence-based answer, in under one minute, to:
**"Are we better prepared than in 2021, where are we still exposed, and what is the FIRST action I take on this warning?"**

Pass/fail test (brief, phase 5): someone outside the team opens the page and says Anna's first action within 60 seconds.

## 2. Design principles (team book library)
| Principle | Source | What it means here |
|---|---|---|
| Lead with the ending: start with the call to action | *Storytelling with Data* p.182 | First action is the first thing on screen |
| One Big Idea sentence: point of view + what is at stake | *Storytelling with Data* p.44-45 | Page title is a full sentence with numbers |
| Explanatory, not exploratory ("the pearls, not the 100 oysters") | *Storytelling with Data* p.36 | Show 3 numbers and 1 ranking; raw layers sit in a drawer |
| Grey everything else, one accent colour | *Storytelling with Data* p.111, 141 | Grey basemap; red only for "no shelter" and flooded critical sites |
| Key numbers as large as possible | *Big Book of Dashboards* p.250 | 3 big numbers under the action |
| Geographic data does not have to be a map | *Big Book of Dashboards* p.332 | Ranked town list beside the map; small towns stay visible |
| Diagnosis, guiding policy, coherent actions | *Good Strategy Bad Strategy* p.60 | Page order: action, why (diagnosis), follow-up actions |
| Calibrated uncertainty, outside view first | *Superforecasting* p.84-86, 188; *Scout Mindset* p.80 | Every number shows a range; our counts sit next to official 2021 figures |

## 3. Screen, top to bottom
1. **Big Idea title** (sentence, from `q4_headline.json`).
2. **FIRST ACTION card**: one sentence, then one line of "why", then the evidence chips.
3. **Three big numbers**, each with a low-high range and a click-through to source and method:
   residents in the 2021 flood with **no shelter in reach**; **hospitals and care homes** in the flood zone; **people more sheltered by a coordinated plan**.
4. **Map + ranked town list**, side by side, linked on hover/click. Map layers: flood (observed blue, modelled hatched), shelters (green), flooded critical sites (red), "not mapped by satellite" (grey hatch).
5. **Town panel** (on click): residents, sheltered, no shelter split into "too far" / "shelters full", flooded sites with % under water, data source, Q2 evidence chips, call card button.
6. **"Are we better prepared?" strip** (Q2): five categories per area with verified / partly / unverified tags. Shows "pending" until the researchers' table arrives. Never filled with invented content.
7. **Reality check**: our counts next to official 2021 figures (outside view), with the gap explained.
8. **Limits**, stated plainly (section 7).

## 4. Interactions
| Control | Options | Data |
|---|---|---|
| Flood map | **main** (satellite PRODUCT) / **worst case** (+ later monitoring images) | `variant` in all tables |
| Assumptions | low / central / high (walk 1 / 1.5 / 2.5 km; 5 / 4 / 3 m2 per person; 40 / 50 / 60 % usable) | `low_*`, `central_*`, `high_*` in `area_summary.csv` |
| Area focus | Ahr, Vesdre, Eifel, Meuse, all | bounding boxes |
| Click any number | source, method, uncertainty, script to re-run | static table in the app |

Presets only, no free sliders: every number shown must exist in a re-runnable output (brief, verification rule 4).

## 5. Data contract (inputs, all in `outputs/data/`)
| File | Used for |
|---|---|
| `q4_headline.json` | title, three numbers, ranges, coordination gain |
| `q4_ranking.csv` | ranked town list, town panel |
| `area_summary.csv` | variant / assumption switching, totals |
| `critical_sites.csv` | red markers, "% of site under water" (show only `share_of_site_flooded >= 0.05`) |
| `shelters.geojson` | green markers with capacity |
| `flood_<area>_<main|worst>.geojson` | flood layers (Vesdre = modelled) |
| `dq_report.csv`, `qc_and_validation.json` | limits section, AI summary |
| `q2_evidence.csv` (to come, researchers) | "are we better prepared" strip |

**Stack: Python + Streamlit** (team decision). The app reads these files directly; the map uses folium inside Streamlit; Claude calls run server-side, so the key never reaches the browser. Product context lives in `PRODUCT.md`; UI/UX follows the Impeccable skill (`.claude/skills/impeccable/`, Operate mode, code-first).

## 6. AI features (Claude API, team key with spending limit, called from Python only)

Grounded in *Hands-On Large Language Models* (Alammar & Grootendorst, "HOLLM") and *Transformers: The Definitive Guide* (Koenigstein).
Rule zero: **the LLM writes words; our scripts produce every number.** "LLMs are notoriously bad at mathematical problems" and do better when given a tool (HOLLM p.240).

### 6.1 Call cards (must have)
One 30-second briefing per top town, in FR / NL / DE / EN, pre-generated and cached so the demo works offline.
- **Prompt anatomy** (HOLLM p.200): persona (crisis-cell analyst), instruction (brief a mayor in 30 seconds), context (2026 warning, 2021 baseline), format (fixed JSON: situation, gap, sites at risk, first step, caution), audience (a mayor, not a technical expert), tone (calm, factual, no alarm), data (the town's row from `q4_ranking.csv` and its flooded sites, nothing else).
- **Order matters:** models favour the start and end of a prompt and forget the middle (primacy and recency, HOLLM p.199). Instruction first; the "use only these numbers, say 'not in the data' otherwise" rule repeated last.
- **Low temperature** for predictable, conservative output; translation also low temperature (HOLLM p.194, Table 6-1).
- **Validate, don't trust** (constrained output and guardrails, HOLLM p.216): the output must parse as the JSON schema, and an automatic **number check** rejects any card containing a number that is not in its input row. Rejected cards are regenerated or written by hand.
- Every card reviewed by a human before it ships; labelled "AI-drafted, numbers from our model".

### 6.2 "Ask the data" (nice to have)
A box where Anna asks, for example, "what if the Pepinster sports hall is closed?".
- **Agent with tools** (HOLLM p.240-241, ReAct: thought, action, observation): Claude may only call our functions, such as `get_town(name)`, `rank_towns(by, variant)`, `compare(variant | assumptions)`, `flooded_sites(town)` and `sources(metric)`. It reads their results and phrases the answer.
- **Grounded answers with citations** (RAG, HOLLM p.249, 272-273): each sentence cites the table, row or file it came from, which is shown under the answer. No supporting row means "not in the data".
- Clearly labelled AI; falls back to a canned message if the API is unreachable on stage.

### 6.3 Q2 evidence helper (for the researchers)
Researchers paste or upload the official reports and articles they found. Claude extracts candidate statements per area into the five Q2 categories, **each with its quote and source**.
- **Self-consistency** (Koenigstein p.63): classify each statement three times and keep the majority. Any disagreement is flagged "needs human review", never auto-filled.
- Nothing reaches the platform until a researcher sets the confidence (verified / partly / unverified).

### 6.4 How AI output is evaluated (feeds the graded AI summary)
HOLLM p.279 lists four axes: **fluency**, **perceived utility**, **citation recall** (share of statements fully supported by their citation) and **citation precision** (share of citations that support their statement), plus **faithfulness** to the provided context.
- Automatic: JSON validity, the number check, and citation-to-row matching.
- Human: one reviewer scores every call card and a sample of "Ask" answers on those axes. An LLM-as-judge second opinion is optional; the human verdict is final (HOLLM p.279: "human evaluation is always preferred").
- Scores and every rejected output are logged in `ai_log.md`.

### 6.5 Not allowed
AI-generated numbers; AI-filled Q2 evidence without a source and a human check; the API key anywhere in the browser.

## 7. Limits shown on the page
- The satellite flood map is a snapshot (not the peak) and covers only requested areas; the Belgian layer misses most of the disaster (about 200 buildings mapped vs about 48,000 hit, Wallonia 2022).
- The Vesdre is **modelled** (EFAS 100-year): in the Ahr the model caught 42% of buildings that really flooded; along the Meuse it ignores flood walls. Treat as an order of magnitude.
- Population is modelled (GHS-POP 2020); buildings date from 2020 and miss rebuilding since.
- Shelters come from OpenStreetMap (volunteer data), not official lists; capacity and walking reach are assumptions; distance is a straight line.
- No age data: people who cannot walk 1.5 km are not modelled separately.

## 8. Acceptance tests
- [ ] 60-second test passed by someone outside the team.
- [ ] Every number has a source and a range on click; no number is hard-coded in the HTML.
- [ ] Vesdre always carries the "modelled" label; unmapped areas never look safe.
- [ ] A site that only touches the flood edge is not presented as flooded.
- [ ] Works offline (demo on stage), in light and dark mode, at phone width.
- [ ] No demo or invented data remains.

## 9. Open decisions (team)
1. Which flood map leads: our outside-view check says the **worst-case map is closer to reality in the Ahr** (7,202 vs official >9,000 buildings; main map 3,300).
2. Final wording of the first action after Q2 evidence (have the flooded hospitals been flood-proofed since 2021?).
3. Whether to build "Ask the data" or stop at call cards.
