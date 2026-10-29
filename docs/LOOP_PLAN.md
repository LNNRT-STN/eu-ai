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
3. Long term page (`src/views/long_term.py`) from docs/BUDGETS.md: gap → measure → money, partly-verified badges.
4. Offer a bed (`src/views/host.py`): solidarity register, no personal data, local file; beds within 10 km on the plan.
5. Housing age + 3D single-storey view in "Evacuate first" and the plan download.
6. Getting out (road sim: time to leave the water, to the shelter, routes back through water, busiest road, trains) + map layers; rail row on Long term.

## In progress (delegated, background agents; each writes only its own files)
- Addresses: `outputs/data/addresses.parquet` (`notebooks/addresses.py`): OSM street + house number per flooded
  building (bid). → Safe check-in page + door-knock list.

## Backlog (highest value first)
- Distill the Evacuation plan: it is long now. One-minute read: call list, verdict, three numbers, getting out, map. Consider
  moving 'Getting out' details into a tab, keep one line in view.
- NEXT (owner request): Safe check-in + door-knock list. Residents report "evacuated, I'm at X"; fire brigade sees
  buildings in the water with no check-in, single-storey first, by sector, exportable. No names; local file only.
- Wire each agent's output in as it lands; render; verify totals against app_towns.
- "Better prepared than 2021?" one line on the page: brief Q2/Q4 asks it; only verified facts, else say "not verified".
- Map: avoid label overlap of numbered shelters (town centre now marked).
- Impeccable detector: clean on evacuate.py (re-run after big changes).
- Shelters shared by several towns: one line naming the shelters that need an agreement between municipalities.
- Check the "All towns and care sites" page still reads well under "More" (title, first line).
- Mobile pass at 390 px after all changes.

## Limits to keep stating
Satellite counts are a floor; Vesdre modelled (EFAS 500-year); shelters are OSM candidates; distances straight-line
from the town centre; roles and message are team text to verify locally; no age / income data.
