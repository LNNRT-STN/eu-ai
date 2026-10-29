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
Launch screen (`src/dashboard.py`): pick a role; `?role=manager|brigade|resident|policy` skips it. Each role sees only
its pages (sidebar rows with coloured icons; hover shows a ? and what the page is for). 6 pages, 14 before.

| Page | Host file (absorbed modules, `render()`) | Roles | Content |
|---|---|---|---|
| Crisis room | `crisis.py` (`first_action`, `briefing`, `rivers`) | manager, brigade, policy | Tabs: Live board (drill clock, coming box, counters, region map, events, briefing drafts, 2021 orders) · Priorities (care sites by district, shelter gap per town and per municipality, CSV) · Rivers (live 30-day outlook; drill heatmap) |
| Town plan | `evacuate.py` (`shelters`, `view3d`) | manager, brigade, policy | First action, verdict, 3 numbers, plan map; tabs Getting out · Evacuate first · Shelters · Orders & message · 3D; region call order folded |
| Door-knock list | `checkin.py` (crew only) | manager, brigade | Needs help / no news first, map, roads closed |
| Am I at risk? | `resident.py` (`host`, resident form from `checkin`) | resident | Tabs Do I need to leave? · I have left / I need help · Offer a bed |
| 2021, today, next | `then_now.py` (`risk_areas`, `long_term`) | policy, manager | Verdict over three layers; tabs What the water covered · What changed since · What to fix |
| Data & limits | `limits.py` | all but resident | Sources, limits, checks, model match; detail behind ? |

Explanations sit behind `?` (help=) or one "How this is computed" expander per tab; visible lines are only the caveats
that change a number's meaning (modelled, simulated, candidate, drill).

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
Drill framing (29 Oct, late, ai_log 35): the replay is shown as if it starts on **Fri 30 Oct 2026** (`live.DRILL_DAY0`,
`live.drill()`); the data stays July 2021. Change `DRILL_DAY0` to move the drill. The Crisis room shows a "flood is
coming" box from the replay's first-evacuate times.
Done in the session of 29 Oct, evening (commits e467c0e..bb57e32, ai_log entries 30-33):
- 2021 timeline: `docs/TIMELINE_2021.md` (sourced; Ahr and Vesdre times re-checked in the primary documents); a
  "July 2021: when the orders came" table under the Crisis room map (replay mode), with the tool column taken **by day of
  the daily flow**. The hourly replay's earlier times come from interpolation and are not claimed.
- ML write-up: `docs/ML.md` §8-10. The pooled gain is real (+0.042 over EFAS, CI above zero); on the Ahr the gain over
  EFAS is not significant, and on the Meuse there is none.
- Districts per town (`live.district`): fixed Maastricht, Weilerswist, Inden, Blankenheim, and the Belgian Limburg and
  Luxembourg towns. The fire brigade in reports is named by town.
- Region map: pins show people in the 2021 water; the credits are collapsed. Crisis counters wrap on phones.
- Resident lookup: full addresses work. "Ahrstraße 28" used to give a false all-clear.
- `CHALLENGE_BRIEF.md` §2a-2c: the present-state task, the 2021 failures the tool fixes, and each question → page → evidence.
- `docs/DEMO.md`: the 5-minute script, the pre-warm list and the "do not say" list.

Still open:
1. Review acted on (ai_log 34). Not done: P1-9 source for "people who could not leave alone died" (CHALLENGE_BRIEF §2b
   [VERIFY]); Town plan "Who gives the order" is a national table, not cross-border.
2. Practise `docs/DEMO.md` once with Reset; time it.
3. Timeline gaps: no clock time for the Steinbachtalsperre order or the Blessem breach. EFAS issue times may be UTC
   (the JRC captions disagree with its tables).
4. Mobile: region-map labels run past the map edge at 390 px.

## Known limits to say out loud
Replay times are hindsight and shown by day; satellite 2021 counts are a floor; Vesdre is modelled (EFAS 500-year); residents are an order of magnitude; shelters
are OSM candidates; road times are minimums; replay statuses never drop and are given by day; simulated check-ins are
labelled; roles/districts and the warning texts are team summaries to verify (native speaker for FR/DE/NL);
Sentinel-2 cloudless is CC BY-NC-SA (non-commercial); Urft (Schleiden/Kall) GloFAS point is weak (peak 44 m³/s).
