# Machine-learning risk score: tested, not shipped

> Update 29 Oct: retried with terrain (section 8): a real pooled gain, no gain on the Meuse, still not used for
> alert levels. The live tool uses a flow-to-impact curve per town (section 9).

Question: can a LightGBM model give mayors a better flood-risk score per commune (or ~1 km cell) than the EFAS
100-year zone and the hand-made 0–10 priority score already in the dashboard?

**Answer: no.** On areas it never saw, the model ranks cells no better than the EFAS 100-year zone used
alone, and at commune level it mostly reproduces "people in the EFAS zone". It also learns the satellite's blind
spots: it ranks the worst-hit Vesdre communes lower than the hand-made score does. The dashboard keeps the hand-made
score. This page documents the test so the team can defend the decision.

Code: `src/build_ml.py` (about 30 s). Outputs: `src/out/meuse/ml_eval.json` (all metrics), `ml_score.parquet`
(cells), `ml_communes.parquet` (communes), and the feature cache `src/out/ml_cells.parquet`.

## 1. Set-up

| | |
|---|---|
| Unit | GHS-POP 2020 cell (30″, ~1 km) holding at least one OBAT building inside an EMS area of interest. All 19 AOIs (BE, NL, DE, including the Rhine-basin ones) are used so the model has more than 115 positive Meuse cells to learn from: 14,823 cells, 466 positive |
| Label | 1 if at least one of the cell's OBAT buildings lies in the observed July 2021 flood (the `build.py` buildings, union of EMS products and monitoring updates) |
| Features (14), challenge data only | EFAS RP10/100/500: share of the cell's ~90 m pixels that are wet; max depth RP100/RP500; share of the cell's buildings on a wet pixel (RP10/100/500); wettest neighbouring cell (RP100/RP500). OBAT: building count, residential share, mean height. GHS-POP: residents |
| Not used | Terrain (height above river, slope), rain, river flow, soil, dikes. None are in the challenge data and the brief asked for no large downloads. They are what a useful model would need (section 5) |
| Model | LightGBM 4.7.0, 4 leaves, 150 trees, learning rate 0.05, ≥ 50 cells per leaf. Score may only go up as EFAS wetness goes up (monotone constraint), so the model cannot learn "inside the flood zone = safer" from the satellite's misses |
| Validation | **Leave one EMS area out**: each area is scored by a model trained on the other 18. No random split, because neighbouring cells share the same flood and would leak |
| Baselines | The EFAS layers used directly as a score, with no training |
| Metrics | ROC AUC (ranking quality, 0.5 = chance); average precision (focuses on the few positive cells; chance = share of positives, ~2 % in the Meuse); share of positive cells caught in the top 10 % of cells |

## 2. Results (cells, scored by a model that never saw their area)

| Held-out area | Cells (hit) | LightGBM AUC | EFAS 100-yr AUC | LightGBM AP | EFAS 100-yr AP | Top 10 %: LightGBM / EFAS |
|---|---|---|---|---|---|---|
| All 19 areas pooled | 14,823 (466) | 0.752 | 0.750 | 0.082 | 0.071 | 29 % / 22 % |
| **5 Meuse areas pooled** | 5,153 (115) | **0.796** | **0.798** | **0.064** | **0.078** | **35 % / 42 %** |
| Liège / Vesdre / Ourthe (BE) | 2,947 (37) | 0.830 | 0.795 | 0.056 | 0.038 | 54 % / 38 % |
| Lesse (BE) | 1,554 (20) | 0.840 | 0.843 | 0.057 | 0.129 | 55 % / 65 % |
| Limburg (NL) | 370 (37) | 0.718 | 0.714 | 0.187 | 0.188 | 22 % / 24 % |
| Inde, Eschweiler (DE) | 207 (13) | 0.560 | 0.476 | 0.081 | 0.067 | 8 % / 8 % |
| Rur, Wassenberg (DE) | 75 (8) | 0.630 | 0.685 | 0.145 | 0.197 | 13 % / 13 % |

- Meuse AUC gain over the EFAS 100-year share: **−0.003, 95 % bootstrap interval −0.027 to +0.021** (500
  resamples of cells). No measurable gain.
- The EFAS 10-year and 500-year shares do as well as the 100-year share (Meuse AUC 0.791 and 0.796).
- Per-area gains (Liège, Inde) rest on 13–37 positive cells and are not consistent across areas.
- Three variants were tried and the best is reported, which flatters the model: 15 leaves / 300 trees (Meuse AUC
  0.737), EFAS features only (0.740), the monotone model above (0.796).

## 3. Communes (70 Meuse communes)

The commune value is the model's expected residents in hit cells (cell probability × residents, summed).

- Rank correlation (Spearman) with people in the EFAS 100-year zone: **0.93**. With the hand-made score: 0.82.
  The hand-made score and EFAS people correlate at 0.88. The model mostly re-weights "people in the EFAS zone".
- **Blind-spot check.** Pepinster, Verviers, Chaudfontaine, Trooz and Liège have 324 cells: **0 hit according to
  the satellite**, 121 inside the EFAS 100-year zone. Every one of these cells is labelled "not flooded". Commune
  ranks (1 = highest):

  | Commune | Hand-made | LightGBM | EFAS people |
  |---|---|---|---|
  | Liège | 1 | 1 | 1 |
  | Pepinster | 7 | 17 | 20 |
  | Verviers | 12 | 12 | 13 |
  | Chaudfontaine | 12 | 16 | 17 |
  | Trooz | 12 | 20 | 27 |

  The hand-made score ranks them higher only because the team added them by hand (the "missed list"). The model
  cannot do that: no training label says the Vesdre flooded.
- Main drivers the model reports: "homes on 10-year flood ground" and "many buildings". The second is a
  warning sign. Dense cells have more buildings that could be caught in the satellite polygon. That is exposure,
  not a higher chance of flooding.

## 4. Why it does not work here

1. **The labels are a floor.** Radar missed narrow, built-up valleys (the Vesdre, central Liège), so "not hit"
   often means "not seen". A model trained on it learns where the satellite looks well: open floodplains.
2. **Too few positives.** 115 Meuse cells, 466 in all, spread over 19 areas with different rivers and image
   timing.
3. **No new information.** Every hazard feature comes from EFAS, so the model can only re-weight EFAS. Without
   terrain or rain it has nothing EFAS does not already have.

## 5. What would make it worth retrying (not done)

- Better labels: official damage or insurance claims per commune (e.g. the Walloon Region's calamity-fund
  files), or the German EMS damage grading used as a separate target.
- New, free features: height above the nearest river and slope from the Copernicus DEM (GLO-30), distance to a
  river from OSM waterways, upstream catchment size.
- Validation on a different event (e.g. the 1993 or 1995 Meuse floods), not on 2021 alone.

## 6. Files (for checking only; not for the dashboard)

`ml_communes.parquet`: `lau_id`, `commune`, `country`, `people` (EFAS 100-yr residents), `score`, `level`
(hand-made), `ml_exp_residents`, `ml_max` (highest cell probability), `ml_driver1`, `ml_driver2` (plain-language
top two drivers, from LightGBM's built-in SHAP values weighted by residents), `ml_score` (0–10 = decile among
the 70 communes, relative only).
`ml_score.parquet`: per cell `r`, `c` (GHS-POP grid row and column), `aoi_id`, `lau_id`, `commune`, cell bounds,
`residents`, `buildings`, `wet100`, `hit_2021_satellite`, `ml` (out-of-area probability, not calibrated), `ml_pct`,
`driver1`, `driver2`.

## 7. For the AI sheet (Annex 7)

- *AI technique tested:* gradient-boosted trees (LightGBM) to rank ~1 km cells by flood likelihood, trained on
  the July 2021 Copernicus EMS flood extent with EFAS, GHS-OBAT and GHS-POP features.
- *Validation:* leave-one-area-out across 19 EMS areas, compared with the EFAS 100-year zone used alone.
- *Result and decision:* no gain (Meuse AUC 0.796 vs 0.798; gain −0.003, 95 % CI −0.027 to +0.021). The model
  also ranked the under-mapped Vesdre communes lower. **We did not put it in the tool.** The dashboard uses a
  transparent rule-based score that a mayor can recompute by hand.
- *Responsible-AI point:* training on a satellite map that is known to undercount would have hidden the communes
  that suffered most. A transparent rule plus a hand-checked "missed" list is safer here than a model.
- *Human checks:* the team should look at `ml_eval.json` and the blind-spot table above, and confirm the
  undercount in the Vesdre with a cited external source (see METHODOLOGY A11).
- Code written with Claude (Claude Code); no Claude API calls; no personal data.

## 8. Retry with terrain (29 Oct, `src/build_ml2.py`)

Section 5 said the model had nothing EFAS does not have. This retry adds what it lacked: terrain. Same cells,
label, leave-one-area-out validation and baselines as above. Six features per cell come from AWS Terrain Tiles
(Terrarium, zoom 12, ~25 m, free, no key): height of the buildings above the lowest ground within ~500 m and
~1 km (10th percentile and median; a rough "height above the valley floor" with no flow routing), median slope,
and the relief and mean slope within ~1.5 km. The model may only score a cell lower as its buildings sit higher
(monotone constraint). Output: `outputs/data/ml2_eval.json`, `ml2_cells.csv`.

| Held-out cells | Cells (hit) | + terrain AUC | Old AUC | EFAS 100-yr AUC | AP: + terrain / old / EFAS | Gain vs EFAS, 95 % CI |
|---|---|---|---|---|---|---|
| All 19 areas pooled | 14,823 (466) | **0.792** | 0.752 | 0.750 | 0.096 / 0.082 / 0.071 | **+0.042 (+0.024 to +0.058)** |
| 5 Meuse areas pooled | 5,153 (115) | 0.789 | 0.796 | **0.798** | 0.057 / 0.064 / 0.078 | −0.010 (−0.039 to +0.020) |
| Ahr (2 areas) | 362 (91) | 0.900 | 0.874 | 0.891 | 0.769 / 0.747 / 0.677 | +0.008 (−0.025 to +0.046) |

Gain of the terrain model over the old model: all areas +0.040 (+0.028 to +0.053); Meuse −0.007 (−0.025 to
+0.010); Ahr +0.025 (−0.006 to +0.059). Intervals: 500 bootstrap resamples of cells.

What this shows, and what it does not:
- **Across all 19 areas, terrain helps and the gain is real**: the interval for the gain over EFAS stays above
  zero. The largest per-area gains are in the Eifel valleys, where EFAS does poorly: Euskirchen / Bad
  Münstereifel on the Erft (0.845 vs EFAS 0.509, 19 hit cells) and Schleiden / Kall on the Urft (0.897 vs 0.661,
  30 hit cells).
- **On the Meuse it does not help.** EFAS alone stays slightly ahead (not significant either way).
- **On the Ahr the model ranks best, but we cannot claim a gain over EFAS.** The interval for +0.008 includes
  zero. The gain over the old model (+0.025) is also not significant. In the small Hönningen area (7 hit
  cells), terrain made it worse (0.61 vs 0.75).
- A simple rule with no training, "lowest buildings first" (height above the valley floor), reaches AUC 0.884 on
  the Ahr and 0.782 on the Meuse. It is almost as good there and anyone can explain it.
- The Vesdre check works better than before. The Vesdre communes have 406 cells, none of them hit according to
  the satellite. The terrain model puts their median cell at the 97th percentile of Meuse cells (old model 92nd,
  EFAS 79th). The terrain rule matches the modelled EFAS 500-year Vesdre flood with AUC 0.955.
- Same limits as sections 2-4: the labels are a floor, there are few positives per area, and the test covers
  one event only.

**Decision.** The town alert levels still do not come from this model. The tool's live part uses the river flow
per town (section 9), and the risk ranking stays rule-based. If a second map layer is added, it should be the
"height above the valley floor" rule, labelled as terrain screening. For the pitch, say that adding terrain
improves the pooled ranking (AUC 0.75 → 0.79, interval above zero). Do **not** say that it beats EFAS on the Ahr
or the Meuse.

## 9. Impact forecast per town (`impact_forecast()` in `src/build_ml2.py`)

Not a trained model: a transparent curve per river gauge that the replay and the live forecast use to set each
town's status.
- Input: the river flow at the town's gauge (GloFAS daily discharge, 19 points in `src/forecast.py`; town → gauge
  in `outputs/data/town_gauge.csv`), one value or a list of ensemble members.
- Curve: share of the July 2021 impact = 0 at the 2-year flow and 1 at the July 2021 peak. In between, the share
  follows a log-flow scale with knots from the EFAS 10/100/500-year zones near the gauge's towns. The return
  period flows come from a Gumbel fit to the GloFAS annual maxima 1991-2020 (`ml2_curves.json`).
- Output per town: expected share and expected impact (people, single-storey homes, care sites), status none /
  watch (< 0.25) / warn (0.25-0.6) / evacuate (≥ 0.6). With ensemble members, it also gives the share of
  members at warn or worse.
- Limits: the July 2021 replay feeds it **hindcast** flows (hindsight), not the forecasts available on the day.
  GloFAS is daily, so the replay holds each day's flow and gives the day, not the hour. A town's status never steps down during the replay. The Urft point is weak
  (peak 44 m³/s). The calibration knots come from EFAS, so they carry the EFAS blind spots described above.

## 10. For the AI sheet (update to section 7)

- *Retried with terrain:* pooled AUC 0.752 → 0.792; the gain over EFAS is +0.042 (95 % CI +0.024 to +0.058). There
  is no gain on the Meuse, and the Ahr gain is not significant. It is still not used for alert levels.
- *Shipped instead:* a flow-to-impact curve per gauge (no training, calibrated on EFAS return-period zones) and
  Claude-drafted briefings (claude-haiku-5-5). Claude writes the words; every number comes from the engine.
