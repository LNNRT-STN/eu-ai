---
version: 1
slug: "src-dashboard-py"
primary_target: "src/dashboard.py"
related_targets: []
---

## Scope
Meuse crisis dashboard (src/dashboard.py + src/views/). Mode: Operate. Audience: crisis and risk managers. Job: decide whether to act, find exposed communes and care sites, find dry candidate shelters.

## Direction contract
THESIS: An action console, not a report. Each screen opens with a one-sentence verdict and its next step; evidence sits one disclosure level down. Refuses the KPI-tile wall and the single scroll of charts.
OWN-WORLD: Apple HIG system grammar: system font stack, grouped inset lists on a light grouped background (#f2f2f7 / white), hairline separators, systemBlue for action only, flood-status colours reused from forecast.LEVELS, residents in the existing orange ramp. Left sidebar navigation with SF-style material icons.
STORY: Overview tells the manager if a flood is coming and lists three next steps; Rivers, Risk areas and Shelters each answer one question; Data & limits closes.
FIRST VIEWPORT: Status banner (dot, verdict, 1-line context) at top; below, "Next steps" grouped list (3 rows, each linking to a page); right: compact facts list (people in 100-yr zone, care sites to evacuate, candidate shelters).
FORM: pinned by user brief (Apple HIG + shadcn-like, left nav); no seed roll.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Extension: First action page (src/views/first_action.py)
Default page. Inherits the world above (system font, grouped lists, banner, facts strip, one action blue); no new identity.
Covers every mapped area (Meuse, Vesdre modelled, Ahr, Eifel, Erft) from outputs/data/ (notebooks/ pipeline).
FIRST VIEWPORT: page header; flood-map control (all satellite passes / first pass only); red banner with the first action
sentence; facts strip (no shelter place, Vesdre modelled, hospitals and care homes in the water, shelter full); "Then" list.
Below: ranked stacked bars (too far / full / sheltered, palette validated: CVD 12.4, normal 18.0, contrast >= 3:1) beside
the map; one town opens its sites and largest candidate shelters. Observed and modelled numbers are never summed.
