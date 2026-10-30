# Methodology: data, libraries, methods and assumptions

Technical companion to the [README](../README.md). It describes what the code in `src/` does, step by step, so the
team can check it, defend it to the jury and fill in the AI sheet (Annex 7). It contains no result figures: run the
build scripts and read `src/out/meuse/summary.json` for those.

## 1. Scope

- **Area:** the five Copernicus EMS areas of interest (AOIs) that drain to the Meuse:

  | AOI | Area |
  |---|---|
  | `EMSR518_AOI01` | Meuse / Vesdre / Ourthe around Liège (BE) |
  | `EMSR518_AOI02` | Lesse, Rochefort (BE) |
  | `EMSR520_AOI01` | Meuse in Limburg, Venlo (NL) |
  | `EMSR517_AOI09`, `EMSR517_AOI10` | Inde and Rur, Eschweiler and Wassenberg (DE) |

- **Excluded:** the other German AOIs (Ahr, Erft, …: Rhine basin) and the Hasselt arrondissement (`BE_71`), which
  lies inside the Liège AOI but drains to the Demer (Scheldt basin).
- **Unit of analysis:** OBAT building points, aggregated per commune (LAU 2021) and per GHS-POP cell (~1 km).

## 2. Data

### Challenge data (Annex 2), in `data/working_data/`

| Dataset | Files used | Used for |
|---|---|---|
| Copernicus EMS Rapid Mapping: EMSR517 (DE), EMSR518 (BE), EMSR520 (NL) | `ems_*/…/*_areaOfInterestA_*.shp`, `*_observedEventA_*.shp`, `*_builtUpP*.shp` (DE grading products) | Mapped areas, observed 2021 flood extent, damage grading |
| CEMS-EFAS flood hazard | `cems-efas/Europe_RP{10,100,500}_filled_depth.tif` | Modelled flood zones (RP100 in the dashboard; RP10/RP500 in the prototype) |
| GHS-OBAT | `obat_{be,de,nl}/*/*.gpkg` (columns `id`, `use`, `epoch`, `height`) | Buildings as points; `use == 1` = residential |
| GHS-POP | `ghs_pop/GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0` | Residents per ~1 km cell. E2020 chosen as closest to July 2021; E2025 is a projection and is not used |

### External data

| Source | How it is fetched | Used for |
|---|---|---|
| Eurostat GISCO LAU 2021, 1:1M (© EuroGeographics) | Downloaded once by `build_meuse.py` to `src/out/raw/` | Commune boundaries, names, `POP_2021` |
| Open-Meteo Flood API (GloFAS v4, 0.05°) | Live, no key; `forecast.py` | 30-day river discharge forecast, reference flows 2011–2021 |
| Open-Meteo Forecast API | Live, no key | 7-day rain forecast |
| Open-Meteo Archive API (ERA5) | Live, no key | Rain 13–15 July 2021 |
| CARTO basemap | Live, no key | Map background |

No Claude API calls are made by the code; no personal data is processed.

## 3. Libraries

Pinned in `requirements.txt` (Python 3.12):

| Library | Role |
|---|---|
| `geopandas`, `shapely`, `pyogrio` | Vector reading (with spatial filters), spatial joins, geometry repair and simplification |
| `rasterio` | Windowed reads of EFAS and GHS-POP rasters, raster → polygon for the RP100 zone |
| `exactextract` | Area-weighted population sums over flood polygons (`build.py`) |
| `numpy`, `pandas`, `pyarrow` | Arrays, tables, Parquet outputs |
| `requests` | GISCO download, Open-Meteo calls |
| `streamlit`, `pydeck`, `altair` | Dashboard, maps, charts |
| `Pillow` | EFAS overlay PNGs in `build.py`. **Not in `requirements.txt`**: it arrives as a Streamlit dependency (13.0.0 here); pin it if you want the build independent of Streamlit |

Theme and colours: `.streamlit/config.toml`.

## 4. Pipeline

Run in this order; each step writes to `src/out/`.

```
build.py ──► build_meuse.py ──► build_regions.py ──► build_sites.py ──► dashboard.py
                                forecast.py (once) ──┘   (+ live Open-Meteo calls, cached 3 h)
```

### 4.1 `build.py`: buildings in the observed 2021 flood (all EMS AOIs)

1. Reads every EMS `areaOfInterestA` and `observedEventA` layer; activation, AOI and product are parsed from the
   file name.
2. Keeps flood polygons with notation **"Flooded area"** or **"Flood trace"** (drops "Mass Movement"), repairs
   geometries, and **unions the first product with all monitoring updates** per AOI.
3. Reads OBAT points per AOI using the flood polygon as a spatial filter, then keeps points that fall exactly
   inside it (point-in-polygon).
4. Samples EFAS depth (RP10/100/500) at each point, plus the wettest of the surrounding 3×3 cells (~90 m), to
   tolerate small misalignments. Nodata is treated as dry.
5. Residents in the flood: GHS-POP summed over the flood polygons with `exactextract` (partially covered cells
   weighted by covered fraction). Overall totals deduplicate buildings in overlapping AOIs.
6. Areas in km² use ETRS89-LAEA (EPSG:3035). Map geometry is simplified (~5 m tolerance).

Outputs: `buildings.parquet`, `aoi.geojson`, `flood.geojson`, `summary.json`, `efas_rp{100,500}.png`.

### 4.2 `build_meuse.py`: Meuse scope, two views

1. Takes **all** OBAT buildings inside the five Meuse AOIs (not only flooded ones).
2. Joins each building to a LAU 2021 commune. The **commune decides the country**, because the national OBAT files
   overlap at borders; duplicates are dropped. Some Walloon communes listed under Dutch names in GISCO are renamed
   to their French name (e.g. Luik → Liège).
3. Two flags per building:
   - `obs`: the building is one of the `build.py` buildings in the observed 2021 flood.
   - `rp100`: the EFAS 100-year cell **directly under the point** is wet (no 3×3 neighbourhood here).
4. **Residents (dasymetric):** each GHS-POP 2020 cell's population is spread **equally** over the residential
   (`use == 1`) buildings in that cell. Equal weights were chosen over floor-area weights because a few very large,
   probably misclassified footprints absorbed whole cells. Cells with no residential building contribute nothing.
5. Sums buildings, residential buildings and residents per commune and per ~1 km cell, for each view.
6. The RP100 zone is polygonised, clipped to the mapped AOIs (so both views cover the same area) and simplified.

Outputs in `src/out/meuse/`: `communes.parquet`, `cells.parquet`, `flood.geojson`, `aoi.geojson`,
`rp100.geojson`, `summary.json`.

> Note: residents per commune/cell here use the dasymetric method, while `build.py` uses area-weighted
> `exactextract`. The two totals will not match exactly; the dashboard uses the dasymetric numbers.

### 4.3 `build_regions.py`: 2021 impact class per commune

1. Keeps communes with **≥ 10 % of their area** inside the mapped AOIs (area share in EPSG:3035).
2. For communes with at least one flooded building, computes three percentile ranks among those communes:
   residents in the water, flooded buildings, and residents in the water ÷ `POP_2021`.
3. Score = mean of the three ranks; split into **quartiles**: Low, Moderate, High, Severe. Communes with no flooded
   building: "Not reached by mapped water".
4. EMS damage grading (destroyed / damaged / possibly damaged) is counted per commune for the two German AOIs and
   shown in tooltips, **not** used in the score (Belgium and the Netherlands have no grading).
5. Pepinster, Verviers, Chaudfontaine, Trooz and Liège are flagged `under_detected` and drawn grey.

Output: `regions.geojson`.

### 4.4 `forecast.py`: live outlook

- **River points:** 19 GloFAS 0.05° cells, each picked by hand as the highest-flow cell in a 3×3 neighbourhood
  near the town (coordinates in `GAUGES`).
- **Return-period thresholds** (run once, paced at 20 s per request for the free tier) → `annual_max.json`: annual
  peak flow per point, GloFAS v4 reanalysis 1997–2025; Gumbel fit by L-moments → 2-, 5-, 20- and 100-year flows,
  the way EFAS and GloFAS set theirs. Each point is rated on its own model record, which cancels the model's bias
  at that spot. The July 2021 peak (`gauge_refs.json`) is kept for scale only.
- **Rating** of the ensemble (control + 50 runs): each run's peak over the next 10 days; Normal → Above 2-year →
  Above 5-year → Above 20-year flood when at least 30 % of the runs reach it (the EFAS notification rule). Towns take
  their river point's level as watch / warn / evacuate (`impact.py`), with people expected from the EFAS zone of the
  forecast return period.
- **Planning scenario (the dashboard's plan):** not the outlook but a return period the crisis room switches on: the
  EFAS 10-, 100- or 500-year zone (`outputs/rp/`, README "Run it"). The outlook is context for that choice.
- **Rain:** 7-day forecast for four headwater points, largest 2-day total, vs. ERA5 total for 13–15 July 2021.
- The dashboard caches these calls for 3 hours and works offline without the outlook.

## 5. Assumptions

Each is a choice the team made; challenge it if the evidence says otherwise.

| # | Assumption | Why | Effect if wrong |
|---|---|---|---|
| A1 | A building is "in the water" if its OBAT **point** is inside the EMS flood polygon | OBAT gives points, not footprints | Buildings partly flooded but with the point outside are missed, and vice versa |
| A2 | Union of all EMS products and monitoring updates = 2021 flood extent | Each image captures a different moment | Still a floor: no image caught the peak everywhere |
| A3 | "Flood trace" counts as flooded | Traces show where water was | Slight over-count if traces are ambiguous |
| A4 | GHS-POP 2020 represents July 2021 population | Closest epoch | Small; population changes slowly |
| A5 | Residents are spread **equally** over residential buildings in a ~1 km cell | Robust to misclassified large footprints | Over-counts small houses, under-counts flats; order of magnitude only |
| A6 | Being in the water ≠ damaged | No damage data in BE/NL | Counts measure exposure, not loss |
| A7 | EFAS cell under the point decides the 100-year view | Simple, transparent | ~30 m cells mis-place buildings near the edge of the zone |
| A8 | Model-vs-model comparison (GloFAS forecast vs GloFAS's own return periods) | Like for like, as EFAS does; cancels the model's bias at each point | A storm the model misses entirely is still missed |
| A9 | 29 years (1997–2025) and a Gumbel fit give usable 2- to 20-year flows | The record Open-Meteo serves | 100-year flows are uncertain; beyond them only "above 100-year" is shown |
| A10 | Impact classes are **relative** (quartiles among hit communes) | No absolute damage threshold is available across countries | "Severe" ≠ a fixed level of damage |
| A11 | The five under-detected communes were badly flooded despite the satellite map | **Team judgement, not challenge data** | Must be backed by a cited external source in the brief |

## 6. Known limits

See the README "Limits" section. In short: 2021 counts are a floor (radar, overpass timing, narrow valleys);
EFAS ignores dikes and small streams (< 500 km²); GloFAS is weak in small valleys such as the Vesdre; the outlook
is a heads-up, not an official warning; ERA5 smooths rain peaks.

## 7. Reproducibility

- Data access: local environment, Annex 1 option 2. Paths are relative to the repo (`data/working_data/`).
- Outputs are gitignored: each teammate runs the build steps once.
- Live outlook values change by the hour; screenshot and date any figure quoted in the brief.
- `enrich.py` fetches OSM facilities for all mapped areas; `build_sites.py` turns them into candidate shelters and
  care sites at risk for the dashboard.

## 8. AI use

Code and this document were written with Claude (Claude Code) under Annex 3. For the AI sheet (Annex 7), record
which steps the team checked by hand (e.g. AOI selection, gauge coordinates, the under-detected list, sample
building counts against the map).
