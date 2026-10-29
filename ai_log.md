# AI log (Claude as co-analyst)

Format from CHALLENGE_BRIEF.md section 8. Entries in order, Thursday 29 Oct 2026. Every number the brief uses must trace to a
re-runnable script in `notebooks/` (`pipeline.py`, `osm_extract.py`, `dq_report.py`).

## 1. Tool ideas from the team's book library
- Prompt/intent: read the brief, search the team's book knowledge base, propose policy-tool ideas.
- AI output (short): 10 ideas; recommended an action-first page (headline action, 3 numbers, map + ranked table), citing *Storytelling with Data* ("lead with the ending", Big Idea) and *Good Strategy Bad Strategy* (diagnosis, guiding policy, coherent action).
- How we checked it: AI quoted page numbers; two data-viz books were not indexed at first and the AI said so before indexing them.
- Result: correct (ideas); the first demo dashboard used invented numbers and is labelled DEMO DATA.
- Decision taken by the team: action-first layout; real data before final design.

## 2. "OBAT has no building area" (from the data catalogue)
- Prompt/intent: understand the datasets before analysis.
- AI output (short): initially repeated Annex 2 ("points, not footprints: you cannot measure building area") and built a capacity model on that basis.
- How we checked it: profiled the actual GeoPackage fields; read the official GHS-OBAT documentation (p.19-20).
- Result: corrected. OBAT has `area` (Overture footprint, m2) and `height` (100 m grid mean, floored at 2.5 m). Codes confirmed: use 0/1/2 = outside built-up / residential / non-residential; epoch 1-5.
- Decision taken by the team: capacity = OBAT footprint x storeys (height / 3 m), floored heights counted as 1 storey.

## 3. First Q1 run gave ~0 flooded buildings in the Vesdre
- Prompt/intent: count buildings and people inside the 2021 flood, test window over Pepinster/Verviers.
- AI output (short): 0 buildings, 4-26 people.
- How we checked it: result was implausible; located every EMS product and measured distance from towns to the nearest flood polygon; plotted it.
- Result: rejected. The result was right for the data but the data has a gap: Belgian EMS polygons follow the Meuse and the Rochefort area; nearest polygon is 7-15 km from Pepinster, 11-14 km from Verviers.
- Decision taken by the team: the Vesdre is shown as "not mapped by satellite"; EFAS 100/500-year is used as a labelled modelled proxy, validated against observed floods in the Ahr and Liege.

## 4. Two population methods disagree
- Prompt/intent: people in the flood zone.
- AI output (short): area-weighted cells vs spreading residents over homes differed 5-17x in Belgium, 1.8x in the Ahr.
- How we checked it: ran both on 5 areas; inspected why (1 km cells vs narrow flood strips).
- Result: flagged, not hidden.
- Decision taken by the team: primary = residents spread over residential buildings by footprint; cross-check method reported.

## 5. Public OpenStreetMap server unusable
- Prompt/intent: pull schools, sports halls, hospitals, town borders.
- AI output (short): Overpass queries timed out repeatedly; server reported "at capacity".
- How we checked it: tested small vs large queries; read the server status message.
- Result: corrected. Switched to official Eurostat GISCO LAU 2021 borders (the brief's own example) and local Geofabrik OSM extracts.
- Decision taken by the team: no dependence on public query servers during the event.

## 6. Bugs caught by testing on the smallest area first
- AI output (short): (a) people-density check used map-shape area instead of the footprint column, so it found nothing; (b) a cache step needed a library that was not installed and lost a 10-minute read; (c) a pandas name clash crashed the run.
- How we checked it: run on Schleiden before the full run; automatic consistency checks (people buckets add up, no negatives, no shelter over capacity, not more people placed than exist).
- Result: corrected; each fix re-tested before the full run.

## 7. Shelter allocation method
- Prompt/intent: how many exposed residents can be sheltered.
- AI output (short): first version sent each person to the nearest shelter with room (greedy).
- How we checked it: *Introduction to Algorithms* ch.26 (p.669-670): many sources and capacitated sinks is a maximum-flow problem; greedy can block people. Verified the solver on a small textbook-style case.
- Result: corrected. Max-flow is the primary result; greedy kept as "everyone goes to the nearest shelter" for comparison.

## 8. Published 2021 figures for the sanity check
- Prompt/intent: outside view first (*Superforecasting* p.84-86).
- AI output (short): web search summaries gave figures for Wallonia and the Ahr.
- How we checked it: did not trust summaries; opened the Wallonia government press release (July 2022) and extracted the text: 39 deaths, 100,000 people affected, ~48,000 buildings (45,000 homes), 9,670 ha flooded, 209 of 262 municipalities. German Kreis PDF was image-only, so used bpb (10 Jul 2023): 135 deaths in the Ahr valley, over 9,000 buildings destroyed or heavily damaged, 17,000 people lost everything.
- Result: figures verified at source; comparison with our numbers pending the full run.

## 9. Max-flow came out below greedy (impossible)
- AI output (short): first full run stopped in 4 areas: "max-flow below greedy".
- How we checked it: the automatic check (max-flow must be >= greedy) fired; saved the failing case (Wassenberg: 81 vs 82 people).
- Result: corrected. Cause: the solver needs whole numbers; people were scaled to 0.1 person and small fractions per building were rounded away. Now 0.001 person; all areas re-run.

## 10. Is the EFAS model a fair stand-in for the Vesdre?
- Prompt/intent: validate the modelled proxy where the observed flood is known.
- AI output (short): Ahr: the 100-year model floods 42% of buildings the satellite saw flooded (500-year: 48%); 59% of model-flooded buildings were seen flooded. Liege: 75% recall, but the model floods ~76,000 buildings along the defended Meuse that the satellite did not map.
- How we checked it: building-level comparison inside the satellite areas of interest only.
- Result: the proxy is rough. In the Ahr, 2021 went well beyond the model; along the Meuse the model ignores defences. Vesdre numbers are labelled "modelled" and given as an order of magnitude.

## 11. Outside view: our counts vs published 2021 figures
- Ahr: we count 3,300 (main) to 7,202 (worst) buildings in the observed flood vs "over 9,000 buildings destroyed or heavily damaged" (bpb, 2023). Lower, as expected: satellite snapshot not peak, mapped areas partial.
- Wallonia: observed EMS polygons hold only ~200 buildings vs ~48,000 buildings hit (Wallonia, July 2022): the Belgian satellite layer misses most of the disaster. With the Vesdre model we reach ~8,500, still a fraction.
- Venlo: 216 buildings / 525 residents in the observed flood vs 10,700 residents evacuated (precautionary evacuation, not flooding).

## 12. Two pipelines, two methods: which is correct?
- Prompt/intent: a teammate's dashboard (branch `briefing-dashboard`) used other choices. Decide on evidence, not by matching either side.
- Flood extent: all satellite passes (PRODUCT + MONIT) is now the headline; first pass kept as a lower bound. Evidence: Ahr 7,202 buildings with all passes vs 3,300 with the first, against ">9,000" official (bpb 2023).
- Spreading residents over homes, tested on Ahr, Erftstadt and Venlo:
  - equal split: 1% of homes get 1 person per 2.5-5 m2 of footprint (p99 0.21-0.41 people/m2), physically implausible;
  - footprint weights: one building absorbs up to 1,197 people;
  - floor volume (footprint x storeys, extreme footprints capped): p99 0.03-0.05 people/m2, totals between the two.
- Result: floor volume chosen. Method spread kept as uncertainty (Ahr 19.8-21.0k, within 6%; Venlo 206-525).
- Decision taken by the team: one method for every number on the dashboard; the teammate's design and pages kept.

## Data-cleaning decisions (from *Python for Data Analysis* ch.7)
- Duplicates: overlapping flood shapes dissolved; OSM objects merged per campus; a building in two study areas counted once.
- Missing values: analysed and reported per area (book p.210), not silently filled.
- Outliers: shelter floor area above an extreme fence (log scale, Q3 + 3 IQR) is capped and listed by name (book p.223-224); storeys capped at 10.
- Data-quality indicators with thresholds, cause and owner: `outputs/data/dq_report.csv` (*Fraud Analytics* ch.7, p.345-347).

## 13. Dashboard integration, checked by rendering it
- Prompt/intent: add the First action page to the teammate's Streamlit app, inheriting its design (Impeccable: extend an established world), with charts per the data-viz skill.
- AI output (short): page, data loader, limits text, navigation; chart colours first proposed from the team palette (red + orange).
- How we checked it: palette validator (red vs orange failed the normal-vision floor, 13.6 < 15; replaced by grey / orange / dark brown, all checks pass); Streamlit test runner on every state (default, town picked, first pass only); real renders captured with Playwright in Edge at 1440 px and 390 px.
- Result: corrected four issues found in the renders: map circles covering half the region; fact 1 wording contradicting fact 4; two numbers that summed observed and modelled areas (removed); a stale data cache that kept serving old numbers after a rebuild (cache now keyed on file times).
- Decision taken by the team: First action is the default page; the teammate's Meuse pages stay, rebuilt with the same residents method.

## 14. "Where do people go if shelters are full?" (question from the team)
- Prompt/intent: the page said "shelters are full" without saying where evacuees go.
- AI output (short): two additions. (1) For each flooded hospital / care home, the 3 nearest dry sites of the same kind (OpenStreetMap; dry in 2021 and in the 100-year model). (2) A bus scenario: same capacity rules, reach 10 km instead of 1.5 km on foot, recording which shelter each town's people go to (max-flow).
- How we checked it: first receiving run found 58,744 "hospitals" and no match anywhere: a column called `type` clashed with GeoDataFrame.type (geometry type); renamed and re-ran (3,281 sites, median nearest 2.5 km). Bus plan checked against capacity (people per shelter <= places). Every view clicked through in the browser; a second `.cat` name clash (pandas accessor) and a Python 3.11 quote error were caught there and fixed.
- Result: with buses up to 10 km, about 29,800 of 29,950 people in the satellite-mapped areas get a place (about 100 still without). The gap is transport and coordination, not total space. Free beds in receiving hospitals are unknown.
- Decision taken by the team: page reorganised as Do now (evacuation + receiving sites) / Next (shelters, bus plan) / Context.
