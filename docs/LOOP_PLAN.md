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

## Done
1. Evacuation plan page: town → walk / transport / no place, shelters from the 10 km plan, tabs (evacuate first, who
   gives the order, message, plan and drill), HTML download. Roles + translations fact-checked by an agent. `e19040f`
2. River outlook line per town (nearest GloFAS point ≤ 15 km, else "follow official centre"); first-action call list
   (top 6 towns by residents with no shelter on foot, district/province to call, care sites; click opens the plan).

## In progress (delegated)
- Agent: `outputs/data/housing_age.csv` + `notebooks/housing_age.py` (residential pre-1980 and non-residential
  buildings in the flood, per town). When it lands: show it in "Evacuate first" and the plan download; flag in call list.

## Backlog (highest value first)
- Wire housing age into the page (after the agent reports).
- "Better prepared than 2021?" one line on the page: brief Q2/Q4 asks it; only verified facts, else say "not verified".
- Map: mark the town centre (distances are measured from it); avoid label overlap of numbered shelters.
- Run the impeccable detector on `src/views/evacuate.py`; fix findings.
- Shelters shared by several towns: one line naming the shelters that need an agreement between municipalities.
- Check the "All towns and care sites" page still reads well under "More" (title, first line).
- Mobile pass at 390 px after all changes.

## Limits to keep stating
Satellite counts are a floor; Vesdre modelled (EFAS 500-year); shelters are OSM candidates; distances straight-line
from the town centre; roles and message are team text to verify locally; no age / income data.
