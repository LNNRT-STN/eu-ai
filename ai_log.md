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

## 15. Evacuation plan page: residents to dry shelters, and the 2021 governance gaps
- Prompt/intent: make the tool about one job (get residents to a dry shelter) and answer the 2021 failures the team listed: unclear roles across levels, warnings that did not become instructions, missing local plans and drills, people who could not leave alone.
- AI output (short): new default page `src/views/evacuate.py`: pick a town, see walk / transport / no place (from `app_towns.csv`), the dry shelters each town's people go to with places and towns sharing them (from `bus_plan.csv`), care sites to evacuate first, who gives the order per country, a draft warning message (local language + English) and a printable town plan with a pre-season drill list.
- How we checked it: walk + transport + no place equals residents per town (Kall 79 + 1,600 + 100 ~ 1,780; `bus_plan` people per town match `bus_covered`, mean difference 1 person). Rendered at 1440 px and 390 px with Playwright (Bad Neuenahr-Ahrweiler, Pepinster modelled, Kall with a gap); download opened and read. Roles and translations checked by a second AI pass against official sources (centredecrise.be, wetten.overheid.nl, hochwasser.rlp.de, hochwasserportal.nrw, bbk.bund.de): three role rows and several translation phrases corrected.
- Result: roles and message are labelled as team text, not data, to be confirmed against the municipality's emergency plan and by a native speaker. Distances are straight lines from the town centre. No age or income data: stated on the page.
- Decision taken by the team: Evacuation plan is the home page; earlier pages under "More".

## 16. First action as a call list, and the river outlook per town
- Prompt/intent: ground the page in the brief's test (Anna names her first action in under a minute) and close the warning-to-action gap.
- AI output (short): a call list at the top (six towns with most residents lacking a shelter on foot, the district or province to call, care sites to evacuate; click opens the town plan) and one line per town with the nearest GloFAS outlook point within 15 km, or a pointer to the official centre.
- How we checked it: rendered and clicked (Schleiden: 1,200 walk + 2,300 transport = 3,500 residents, matching app_towns). The outlook was rate-limited by Open-Meteo during the test; the page now says "unavailable right now" instead of "offline". District/province per area is a team summary to verify.
- Result: the first action is the first thing on the home page.

## 17. Long term page: gaps, measures and real budgets
- Prompt/intent: link the short-term plan to long-term fixes, grounded in money that exists.
- AI output (short): desk research by an AI agent (docs/BUDGETS.md, a URL per row, verified yes/partly) and a page `src/views/long_term.py`: five gaps from our data (shelter reach, care sites, warning chain, homes in the water, too much water too fast) → measure → funding line; committed money since 2021.
- How we checked it: gap numbers read from q4_headline.json and app_towns.csv (19,000 observed / 6,500 modelled without a shelter on foot; 15 care sites; 44 schools; 13,100 / 8,800 buildings); amounts copied as published and never summed; "partly verified" shown on the page wherever the source is secondary. Headline reworded after the render showed it contradicted the payout figure ("money is flowing" vs a fifth paid out).
- Result: not found and said so: unit costs for flood-proofing a care home or shelter equipment; rescEU and ERDF regional amounts; an OVV report on Limburg 2021.

## 18. Offer a bed: a solidarity register (owner request)
- Prompt/intent: let residents outside the flood zone offer a room or spare bed to people who must leave, as a solidarity movement.
- AI output (short): page `src/views/host.py` (town, beds, who the host can take, "my home stayed dry" check, reference code, withdraw) and one line on the Evacuation plan with beds offered within 10 km.
- How we checked it: filled the form in the browser, read the stored row, saw the line appear for a town 10 km away, fixed plurals and a code-parsing bug (an all-digit code with a leading zero would not withdraw). The test offer was deleted.
- Result: privacy by design: no name, address or phone stored; offers stay on the local machine (data/, gitignored); not counted as shelter places. A real roll-out is run by the municipality under the GDPR.

## 19. Housing age and a 3D "no upper floor" view (GHS-OBAT)
- Prompt/intent: flag older riverside housing and homes with no upper floor to escape to.
- AI output (short): an agent read GHS-OBAT (BE, NL, DE) and wrote housing_age.csv (pre-1980, non-residential per town) and buildings_3d.parquet (21,969 buildings in the 2021 water, height, storeys); the page shows three counts per town and a 3D map (single-storey homes red).
- How we checked it: building totals match app_towns (21,949 vs 21,864; median gap 1 per town). Construction period is the 100 m cell's first built-up epoch, not the building's: labelled "neighbourhood age". 1,438 homes have OBAT's 2.5 m fill-in height: counted as "no reliable height", not single-storey (Schleiden 1,351 + 168 = the agent's 1,519). Removed an unsupported claim ("often older residents") after review.
- Result: water depth is not in the data, so "no upper floor" is a priority signal, not a drowning-risk estimate.

## 20. Road evacuation simulation and rail in the flood
- Prompt/intent: simulate people moving when an evacuation happens (owner chose routes + road load, not time-stepped traffic; simulation, not ML).
- AI output (short): two agents. `notebooks/evac_sim.py`: 14 towns with at least 300 residents in the water, today's OSM roads (Geofabrik extracts; Overpass was unreachable), residents spread evenly over the streets in the water, walk 4 km/h (3 km/h for older people), bus 30 km/h without boarding. `notebooks/infra.py`: rail, stations and bridges inside the 2021 water + desk research (docs/INFRA_2021.md).
- How we checked it: road vs straight-line distance median 1.2-1.4 in every town; people totals equal app_towns exactly; rail result compared with Deutsche Bahn's rebuild of the Ahr line (19 rail bridges in our layer, 22 rebuilt by DB). In the render an unnamed road showed as "tertiary" (OSM class) and was relabelled "an unnamed tertiary road"; plurals fixed.
- Result: the striking finding: in narrow valleys most routes go back through the 2021 water (Dernau 100 %, Trooz 95 %, Bad Neuenahr-Ahrweiler 37 %): evacuate before the river rises. Times are minimums. We do not show the simulation's walk/bus split, because it uses the 10 km plan and would contradict the walking plan's counts.

## 21. Distill and polish for a broad audience (impeccable)
- Prompt/intent: the home page had grown long; owner asked for simple UI and UX usable by a broad audience.
- AI output (short): first screen = call list → town → verdict → three numbers → map; "Getting out" moved into a tab, its key fact (share of routes crossing the water again) moved into the verdict, which turns red when it is 50 % or more.
- How we checked it: renders at 1440 and 390 px (Trooz, Bad Neuenahr-Ahrweiler); the impeccable detector is clean on all three new pages. Fixed copy where the card said "1.5–10 km away" but the list showed 11–12 km (10 km is from each home, the list from the town centre); dropped "0 stations".

## 22. Safe check-in and door-knock list (owner request)
- Prompt/intent: residents report they have left and where they are; fire crews see homes with no news and go there, single-storey first; alert delivery by SMS/phone shown where it would plug in.
- AI output (short): an agent matched OSM addresses to the flooded OBAT buildings (89 % matched; NL 13 %; 14.7 % of matches over 15 m), `notebooks/addresses.py`; page `src/views/checkin.py`: resident form (street, number, where now, people, or "I need help leaving"), crew list and map (needs help → no news, single-storey first → left), CSV for crews, "Reached by alert: no feed yet", drill button (simulated check-ins tagged DRILL) and reset.
- How we checked it: end-to-end in the browser: check-in saved; drill filled about 63 %; reset left only the real check-in. Found and fixed: drill rows stored numbers instead of addresses (index misalignment); 29 OSM addresses have a number but no street, now "House no. 23 (no street name)". Test data deleted.
- Result: no names or phone numbers stored; check-ins stay local (data/, gitignored).

## 23. Sidebar controls, native Streamlit, minimal CSS (owner request)
- Prompt/intent: easy controls in the left sidebar, Streamlit best practice, minimal custom CSS.
- AI output (short): one Town picker in the sidebar shared by Evacuation plan, Safe check-in and the 3D view (session-state pattern so the choice survives other pages); main pages rebuilt with st.title, st.metric(border), st.error/st.info, st.container(border), markdown tables, :orange-badge[] and :color[] legends; real checkboxes for the drill checklist. core.style() now runs only on the older "More" pages.
- How we checked it: all six pages rendered at 1440 and 390 px with no exception; impeccable detector clean on the four main pages. Caught in render: two escaped-newline syntax slips, and Material "circle" icons that ignore text colour (legend now uses filled marks inside :color[]).

## 24. 3D view (FireTrace as design reference, MapLibre instead of Mapbox)
- Prompt/intent: owner's prime example is FireTrace (firemap-two.vercel.app): clean 3D terrain dashboard that makes a homeowner feel the urgency. Free alternative to Mapbox requested.
- AI output (short): an agent built `src/views/view3d.py`: MapLibre GL JS 5.6.0 in a Streamlit component, AWS Terrain Tiles (Terrarium) for elevation, EOX Sentinel-2 cloudless 2021 (CC BY-NC-SA 4.0) or Esri World Imagery, the 2021 water, homes (single-storey red), shelters, roads, rail and care sites draped on the terrain; sidebar layer toggles; a July 2021 day slider with the GloFAS replay where a river point is within 15 km.
- How we checked it: FireTrace has no public repository and no licence, so it was used as a design reference only (no code, not its Mapbox token). Renders checked for Bad Neuenahr-Ahrweiler, Trooz (modelled, dashed edge) and Schleiden (town carried over from the sidebar). Single-storey count matches the Evacuation plan (264 Bad Neuenahr, 1,351 Schleiden). Relabelled "Care sites to evacuate" (18 in Bad Neuenahr) to "Care sites and schools": 11 of the 18 are schools, which close rather than evacuate. Found by the agent: MapLibre workers fail in Streamlit's null-origin iframe; loading from a blob: URL fixes it.
- Result: water opacity on the slider is a visual cue, not a flood simulation; homes are OBAT points drawn as blocks, not outlines; needs internet for tiles.

## 25. 3D map as the hero of the Evacuation plan (owner choice)
- Prompt/intent: make the 3D view the prime example; owner chose it as the hero of the home page.
- AI output (short): map code moved to `src/map3d.py` (one `render()` for the home hero and the 3D page); home order: title, one-line first action, town, verdict, 3D valley, three numbers, shelter map, then the full call list; legend folds on phones.
- How we checked it: renders at 1440 and 390 px, no exception. A first edit replaced the wrong `spare_beds()` (inside the def) and broke the file: reverted from git and redone with exact anchors. The legend change needed a server restart to show (stale imported module).
- Result: decision first (product principle 1), then the 3D valley in the first screen.

## 26. Independent review (fresh AI reviewer) and fixes
- Prompt/intent: a read not anchored on ours before the jury: one-minute test, same number everywhere, honesty, phones.
- AI output (short): one-minute test passed (~10 s to name the first action); residents, shelters, single-storey homes, care sites and no-shelter counts consistent across pages for Bad Neuenahr-Ahrweiler, Trooz and Kall. Ten issues reported.
- Fixed: (P0) "44 schools" summed observed and modelled: now 26 (+18 modelled); (P0) "walk" metric vs the shelter table came from two different plans: labelled "walking check" vs "10 km plan"; (P0) shelters up to 16 km "within 10 km": column is now "Centre km", the limit is from each home; (P0) check-in "homes" counted addresses: now doors vs homes, Venlo note only for Dutch towns; (P1) one first-action sentence (call + book buses + move care homes), the All towns page no longer says "Do now" for a different action; (P1) last good river outlook kept on disk and shown with its time when Open-Meteo is down; (P1) "Better prepared than 2021?" answered from sourced desk research (partly); (P2) care sites and schools one purple on every map; "2–10 km" → "1.5–10 km".
- Not changed: mobile tables still scroll sideways for the last columns (Streamlit dataframe); "Reached by alert" stays an explicit placeholder by owner decision.

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
