# Handoff: flood evacuation tool (29 Oct 2026, ~19:00)

Branch `evacuation-loop` (not merged into main). Jury pitch: Fri 30 Oct, 5 minutes. Read this first, then
`docs/LOOP_PLAN.md` (decisions + backlog) and `ai_log.md` (entries 15-29: every AI step and how it was checked).

## Run it
```bash
source .venv/bin/activate && pip install -r requirements.txt
streamlit run src/dashboard.py            # http://localhost:8501 (we used --server.port 8599)
python -m pytest -q tests/test_live.py    # 9 tests, live engine
```
Claude API key: `.env`, variable `claude_api` (gitignored, server-side only). Local state: `data/live.db`,
`data/host_offers.csv` (gitignored). Large OBAT downloads: `challenge_data/` (gitignored, 12 GB, only needed to rebuild
`housing_age.csv` / `buildings_3d.parquet`). OSM extracts: `cache/osm/`.

## What exists (menu by role)
| Page | File | State |
|---|---|---|
| Crisis room (start) | `src/views/crisis.py` | Scenario player in sidebar (replay July 2021 / live forecast, play, reset, speed); 6 live counters; live 3D region map (`src/regionmap/`, updates in place, click a town → flies in, link to its plan); latest events; outbox of Claude-drafted reports. **Last edit (region map swap) rendered OK, committed in this handoff.** |
| Town plan | `src/views/evacuate.py` | First action line, verdict, 3D valley hero (`src/map3d.py`), walk / bus / no place, shelter map + list, call order, tabs: getting out (road sim), evacuate first (single-storey, care sites), who gives the order, warning message (local language + EN), plan & drill + HTML download |
| 3D view | `src/views/view3d.py` | MapLibre terrain + Sentinel-2, layer toggles, July 2021 day slider |
| Long term | `src/views/long_term.py` | Gaps → measures → cited budgets (`docs/BUDGETS.md`, `docs/INFRA_2021.md`) |
| Do I need to leave? | `src/views/resident.py` | Street + number → leave / where / how / minutes, spare beds nearby; not found → offer a bed |
| Offer a bed | `src/views/host.py` | Solidarity register, no personal data |
| Check-ins and door-knock list | `src/views/checkin.py` | Resident check-in + crew list on `live`, refreshes during replay, crews close/reopen roads |
| More / Reference | older analyst pages | keep `core.style()`; not polished |

Engine: `src/live.py` (SQLite: clock, town status, events, check-ins, closures, outbox), `src/reports.py`
(claude-haiku-5-5, template fallback, ~$0.0002/report), `src/build_ml2.py` (`impact_forecast`, `load_town_gauge`),
`src/forecast.py` (19 GloFAS points incl. Ahr, Erft, Urft), `outputs/data/town_gauge.csv`.

## Method (how we worked; keep it)
- `/loop` self-paced, one focused step per iteration; `docs/LOOP_PLAN.md` read first, updated last.
- Background agents for independent work, each owning **separate files** (never two agents on one file); the lead
  integrates. Agents must not stop the shared server on port 8599 (use their own port).
- Verify every step by rendering (Playwright with system Chrome, 1440 and 390 px), check numbers against
  `outputs/data`, then commit with **named files** (not `git add -A`). Log each AI step in `ai_log.md`.
- Product rules: decision first; never invent figures; AI writes words, not numbers; observed and modelled (Vesdre)
  never summed; candidate shelters never called official; label simulated data; `/impeccable` distill + polish,
  native Streamlit, minimal CSS. Owner prefers questions as multiple-choice menus.
- An independent reviewer agent (fresh context) before the pitch caught 4 misleading numbers: repeat this.

## Open work (priority order)
1. **2021 timeline facts** (agent stopped by the spend limit): create `docs/TIMELINE_2021.md` with sourced times:
   EFAS notifications (10-14 Jul), DWD warnings, Kreis Ahrweiler evacuation order (evening 14 Jul), Altenahr gauge
   failure, Vesdre/Eupen dam, Erftstadt-Blessem, Limburg NL. Then show "2021: order at X" next to the replay's
   "tool: evacuate at Y" in the Crisis room. Caveat to state: the replay uses GloFAS hindcast flows (hindsight), not the
   forecasts available at the time, and times are ±12 h.
2. **ML write-up** (agent stopped): append to `docs/ML.md` from `outputs/data/ml2_eval.json`. Results: LightGBM +
   terrain (height above valley floor, slope) pooled AUC 0.792 vs old 0.752 vs EFAS-100 0.750 (AP 0.096 / 0.082 /
   0.071); Ahr 0.900 vs 0.874 vs 0.891; Meuse no gain (0.789 vs EFAS 0.798). Verdict to write: terrain helps in steep
   valleys (Ahr), not on the Meuse; ship as a second layer only where it beats EFAS, or not at all. Check
   `auc_gain_*_95ci` before claiming a gain.
3. Region map polish: MapLibre credit box covers the bottom on wide screens (`src/regionmap/frontend/index.html`,
   `attributionControl` → `{compact: true}` already; also collapse it after load). Pin labels show tiny
   `people_expected` values for big towns (e.g. Maastricht 9): consider showing residents instead.
4. Report recipients read oddly ("Fire brigade, Province of Liège (governor)"): fix naming in `src/live.py` (CALL
   dict copy).
5. Demo script for 5 minutes (storyboard in `docs/VISUAL_IDEAS.md`): Crisis room replay at 3-6 h/s → click the Ahr →
   Town plan / 3D → resident lookup (Ahrstraße 2, Ahrbrück) → crew list fills, close a road → Long term. Practise
   once with Reset. Pre-warm: open each page once (tiles, outlook cache `src/out/outlook_last.pkl`).
6. Final independent review (fresh agent) + `/impeccable` distill on the Crisis room at 390 px.

## Known limits to say out loud
Satellite 2021 counts are a floor; Vesdre is modelled (EFAS 500-year); residents are an order of magnitude; shelters
are OSM candidates; road times are minimums; replay statuses never drop and are ±12 h; simulated check-ins are
labelled; roles/districts and the warning texts are team summaries to verify (native speaker for FR/DE/NL);
Sentinel-2 cloudless is CC BY-NC-SA (non-commercial); Urft (Schleiden/Kall) GloFAS point is weak (peak 44 m³/s).
