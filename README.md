# July 2021 flood dashboard

European AI Challenge 2026 · policy tool. A Streamlit dashboard for a crisis manager in the areas hit by the July 2021
floods (Belgium, the Netherlands, Germany: Meuse, Vesdre, Ahr, Erft, Rur, Inde). It answers three questions:

1. **Is a flood coming this month?** Live river and rain outlook for the Meuse basin, compared with July 2021.
2. **Who sat in the water in July 2021?** People, buildings and care sites inside the satellite-mapped flood, per municipality.
3. **Where can they go?** Dry candidate shelters, their capacity, and who has no place within walking distance.

## Run it

Data access: local environment (Annex 1, option 2). The dashboard reads the cleaned data in `outputs/data/` (see its
README for method and limits); only the river outlook uses `src/out/meuse/` (`gauge_refs.json`, `replay_2021.json`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python src/forecast.py         # once: river reference flows (~4 min, paced for the Open-Meteo free tier)
python src/build_priority.py   # July 2021 river replay for the Briefing (also needs the challenge files in data/working_data/)

streamlit run src/dashboard.py   # http://localhost:8501
```

Both outlook files are committed, so the two build steps are only needed to refresh them. Without internet the
dashboard still works, but without the live outlook.

## Files

| File | What it does |
|---|---|
| `src/dashboard.py`, `src/core.py`, `src/views/` | The action dashboard: Briefing (home: “If July 2021 happens again”), Rivers, Risk areas, Shelters, Shelter plan, 2021 and today, Data & limits. Reads `outputs/data/`. |
| `outputs/data/` | Cleaned exposure, shelter and data-quality files (built on branch `analysis-pipeline`); method in its README. |
| `src/build_charts.py` | Static charts and the action risk map for the brief → `outputs/charts/` (PNG + SVG). Reads only `outputs/data/`. |
| `src/build_priority.py` | Priority score per commune (rules in its docstring) → `out/meuse/priority.geojson`; GloFAS flows 10–20 July 2021 → `out/meuse/replay_2021.json`. |
| `src/build_sites.py` | Candidate shelters (OSM schools, town halls dry in 2021 and outside the 10/100-year zones) and care sites at risk → `out/meuse/sites.parquet`. |
| `src/forecast.py` | Open-Meteo calls: river forecast, rain forecast, reference flows (`python src/forecast.py` builds `out/meuse/gauge_refs.json`). |
| `src/build.py`, `src/build_meuse.py` | Clip OBAT buildings and GHS-POP residents to the flood extent and the EFAS zone; sum per commune and per cell. |
| `src/build_regions.py` | Commune polygons with the 2021 impact score and EMS damage counts → `out/meuse/regions.geojson`. |
| `src/enrich.py` | OSM facilities, waterways and NUTS3 for all mapped areas; makes the OSM facilities that `build_sites.py` needs. |

## Methods

Full detail (pipeline steps, libraries, assumption table): [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

**River outlook.** Ten points on the Meuse (Liège, Maastricht, Roermond, Venlo), Vesdre (Chaudfontaine, Verviers),
Ourthe, Lesse, Rur and Inde. Each is the highest-flow GloFAS 0.05° cell near the town. For the next 30 days the
dashboard shows the ensemble median and the wettest ensemble member, rated against reference flows from the same
model at the same cell:

| Level | Threshold |
|---|---|
| Normal | below the 2-year flood |
| Above 2-year flood | median annual peak 2011–2020 |
| Above half of July 2021 | half of the model's own July 2021 peak |
| At or above July 2021 | the model's own July 2021 peak |

Using the model's own 2021 peak (not measured values) keeps the comparison like for like. Only 10 years of history
are used because the free tier weighs requests by time span.

**Rain outlook.** 7-day forecast for four headwater areas (upper Vesdre, upper Ourthe, Eifel/upper Rur, Amblève),
with the largest 2-day total, next to the ERA5 reanalysis total for 13–15 July 2021.

**Residents in the water.** GHS-POP 2020 (~1 km cells) spread equally over the residential OBAT buildings in each
cell, then counted for buildings inside the water.

**Commune impact colours (2021).** Hit communes are ranked on residents in the water, flooded buildings and the share
of the commune's population hit. The three ranks are averaged and split into quarters: Low, Moderate, High, Severe.
Communes the mapped water did not reach are green. Communes with under 10 % of their area mapped are left out.

- **Relative, not absolute.** "Severe" means worst quarter in this area, not a damage threshold.
- **Damage is shown, not scored.** EMS damage grading exists only for Eschweiler and Wassenberg (Germany). Putting it in
  the score would make Belgium and the Netherlands look undamaged. Tooltips show destroyed / damaged / possibly
  damaged counts where graded.
- **Grey, not green, where the satellite missed the flood.** Pepinster, Verviers, Chaudfontaine, Trooz and Liège are
  drawn grey. This list is the team's judgement, not challenge data: add the source you rely on.

## Data sources

| Source | Type | Used for |
|---|---|---|
| Copernicus EMS Rapid Mapping EMSR518 (BE), EMSR520 (NL), EMSR517 (DE) | Challenge | 2021 flood extent, mapped areas, damage grading (DE) |
| CEMS-EFAS flood hazard, 100-year | Challenge | Modelled flood zone |
| GHS-OBAT 2020 | Challenge | Buildings (points, use) |
| GHS-POP 2020 | Challenge | Residents |
| Eurostat GISCO LAU 2021 (© EuroGeographics) | External | Commune boundaries and population |
| Open-Meteo Flood API (GloFAS v4) | External, live | River forecast and reference flows |
| Open-Meteo Forecast and Archive (ERA5) APIs | External, live | Rain forecast, July 2021 rain |
| CARTO basemap | External | Map background (no key needed) |

## Limits

- **2021 counts are a floor.** The radar-based satellite map shows water at overpass time, not at the peak, and saw
  little in narrow built-up valleys (Vesdre, central Liège).
- **EFAS 100-year zone** ignores dikes and flood walls (overstates exposure in Dutch Limburg) and skips streams with a
  catchment under 500 km².
- **GloFAS (~5 km grid) handles the Meuse well, small valleys poorly.** It puts the 2021 Vesdre peak far below what was
  observed, so a "normal" Vesdre reading is not reassurance.
- **The outlook is a heads-up, not a warning.** Official warnings: SPW (hydrometrie.wallonie.be), Rijkswaterstaat and
  the German state flood centres.
- **ERA5 smooths local rain peaks.** Rain gauges measured more in July 2021.
- **Residents are an order of magnitude only.** Buildings are points, not footprints. Inside the water ≠ damaged.
- **Red/green is hard to read for colour-blind viewers.** Tooltips name each class.

## AI use

Code was written with Claude (Claude Code), following Annex 3. Record what it did and what the team checked in the
AI sheet (Annex 7).
