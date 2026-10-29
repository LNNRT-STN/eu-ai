# Cleaned data: 2021 flood exposure and shelter coverage

Built 29 Oct 2026 from the challenge data (Copernicus EMS, EFAS, GHS-OBAT, GHS-POP) plus Eurostat GISCO LAU 2021 and
OpenStreetMap (Geofabrik extracts, 29 Oct 2026). The scripts that produce these files (`notebooks/pipeline.py`,
`q4_ranking.py`, `dq_report.py`) live on branch `analysis-pipeline`. Method choices and every AI check: `ai_log.md`
on that branch.

## Areas
Ten study areas, one per Copernicus EMS area of interest: `ahr` (EMSR517 AOI15 + AOI03), `liege` (EMSR518 AOI01),
`rochefort` (EMSR518 AOI02), `venlo` (EMSR520 AOI01), `eschweiler`, `wassenberg`, `schleiden`, `euskirchen`,
`erftstadt` (EMSR517 AOI09, 10, 18, 08, 07), and `vesdre`. **`vesdre` is modelled** (EFAS 100-year zone, main;
500-year, worst): the satellite map has no flood polygons in the Vesdre valley.

## Two flood maps (`variant`)
- `worst` = all satellite passes (first product + monitoring updates). **Use this as the headline:** closer to the
  official 2021 figures (Ahr: 7,202 buildings vs over 9,000 reported by bpb, 2023).
- `main` = first satellite pass only. A lower bound.

## Files
| File | One row per | Key columns |
|---|---|---|
| `area_summary.csv` | area × variant | `flood_km2`, `buildings`, `people_2020`, `people_2025`; shelter results for `low` / `central` / `high` assumptions: `*_covered`, `*_no_reach` (no shelter within walking distance), `*_full` (shelter in reach but full), `*_covered_nearest_first` (if everyone goes to the nearest shelter) |
| `municipalities.csv` | area × variant × municipality | `people`, `covered`, `no_reach`, `full`, `buildings`, `people_2025` (central assumptions) |
| `app_towns.csv` | same as above, cleaned for display | adds `no_shelter`, `lon`, `lat` (municipality centroid), `source` (observed / modelled) |
| `q4_ranking.csv` | municipality | rank by `no_shelter` (all passes), `why` (too far / full), `*_first_pass` lower bound, `hospitals_carehomes_flooded`, `schools_flooded`, `vulnerable_sites` (names) |
| `q4_headline.json` | variant | totals kept apart for observed areas and the modelled Vesdre, ranges, flooded care sites |
| `critical_sites.csv` | hospital / care home / school touching the flood | `share_of_site_flooded` (0-1; below 0.05 = edge only, do not present as flooded), `in_main_flood`, `in_worst_flood`, `also_in_efas100`, `lon`, `lat` |
| `shelters.geojson` | usable candidate shelter (point) | `name`, `cat` (school / sports hall / civic), `gfa` (floor area m²), `capacity_central` (places), `area`, `muni` |
| `flood_<area>_<main|worst>.geojson` | flood extent (simplified 15 m, EPSG:4326) | |
| `dq_report.csv` | area × data-quality indicator | `value`, `warn_above`, `status` (PASS / WARN), `likely_cause`, `who_can_fix` |
| `qc_and_validation.json` | area | raw QC counts, EFAS-vs-satellite validation (Ahr, Liège), the decisions text |

## Method in one paragraph
Flood = EMS `observedEventA`, riverine flood only, invalid shapes repaired, dissolved. Buildings = GHS-OBAT points
inside it. Residents = GHS-POP 2020 cells spread over each cell's residential buildings by **floor volume**
(footprint × storeys, storeys = height / 3 m, 1-10; extreme footprints capped); 2025 is a projection. Shelters = OSM
schools, sports halls and civic buildings, merged per campus, at least 200 m² of floor, **dry in the 2021 flood and in
the EFAS 100-year model**. Capacity = floor area × usable share ÷ m² per person (central 50 % and 4 m²; low 40 % and
5 m²; high 60 % and 3 m²). Walking reach 1.5 km straight line (1 / 2.5 km). People are assigned to shelters by
**maximum flow** (the best possible plan); `covered_nearest_first` is the greedy comparison.

## Limits
Satellite counts are a floor (snapshot, partial coverage; the Belgian layer misses most of the disaster). Residents are
an order of magnitude. Shelters are candidates, not official. Straight-line distance understates walks in steep valleys.
No age data. Do not add observed and modelled (`vesdre`) numbers into one total.
