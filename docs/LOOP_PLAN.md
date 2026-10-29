# Evacuation-plan loop: working plan

Branch `evacuation-loop`. One focused step per iteration: build → render (Playwright, 1440 + 390 px) → check numbers →
commit → log in `ai_log.md`. Read this file first each iteration; update it last.

## Goal (grounded in CHALLENGE_BRIEF.md)
Anna names her first action in under a minute. The tool's job: get residents in the 2021 water to a dry shelter, and
close the 2021 governance gaps (roles, warning → instruction, plans and drills, people who cannot leave alone).

## Decisions (owner)
- Home = Evacuation plan (`src/views/evacuate.py`); older pages under "More".
- Features in: who-does-what chain, ready warning message, printable town plan, vulnerability flags.
- Older housing: compute from GHS-OBAT construction period (bucket, anonymous read).
- Questions to the owner: menu (multiple choice).
- Scope added 29 Oct, ~17:00: road evacuation sim (routes + road load, no time-stepped traffic), rail and bridges cut,
  3D "no upper floor" view (OBAT height), long-term page with real, cited budgets. Short term = damage control while
  evacuating; long term = repairs and preparedness, each tied to a funding line.
- ML: simulation, not ML, for evacuation; keep docs/ML.md (risk model tested, not shipped) as evidence of checking.

## Done
1. Evacuation plan page: town → walk / transport / no place, shelters from the 10 km plan, tabs (evacuate first, who
   gives the order, message, plan and drill), HTML download. Roles + translations fact-checked by an agent. `e19040f`
2. River outlook line per town (nearest GloFAS point ≤ 15 km, else "follow official centre"); first-action call list
   (top 6 towns by residents with no shelter on foot, district/province to call, care sites; click opens the plan).

## In progress (delegated, background agents; each writes only its own files)
- Housing: `outputs/data/housing_age.csv` + `buildings_3d_*.parquet` (`notebooks/housing_age.py`). → "Evacuate first",
  plan download, 3D view of single-storey homes in the water.
- Road sim: `outputs/data/evac_towns.csv`, `evac_edges.geojson` (`notebooks/evac_sim.py`): time to leave the water
  (4 and 3 km/h), time to shelter, busiest roads and bridges, routes through water. → map layer + numbers per town.
- Rail and bridges: `outputs/data/infra_in_flood.csv`, `infra_rail.geojson`, `docs/INFRA_2021.md`. → map layer
  (short term: no train evacuation) + long-term repair list.
- Budgets: `docs/BUDGETS.md` (cited). → long-term page.

## Backlog (highest value first)
- Page structure once data lands: Evacuation plan = short term (now / today); new page "Long term" = gaps → measures →
  funding (cited), per town and per area. Keep the home page one minute to read.
- Wire each agent's output in as it lands; render; verify totals against app_towns.
- "Better prepared than 2021?" one line on the page: brief Q2/Q4 asks it; only verified facts, else say "not verified".
- Map: mark the town centre (distances are measured from it); avoid label overlap of numbered shelters.
- Run the impeccable detector on `src/views/evacuate.py`; fix findings.
- Shelters shared by several towns: one line naming the shelters that need an agreement between municipalities.
- Check the "All towns and care sites" page still reads well under "More" (title, first line).
- Mobile pass at 390 px after all changes.

## Limits to keep stating
Satellite counts are a floor; Vesdre modelled (EFAS 500-year); shelters are OSM candidates; distances straight-line
from the town centre; roles and message are team text to verify locally; no age / income data.
