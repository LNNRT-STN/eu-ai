# 5-minute demo script (jury, Fri 30 Oct)

One message: **in 2021 the warnings came a day or more before the orders. This tool turns a river warning into an
order, a place to go and a door-knock list for every town in the 2021 water.** Every screen answers one of the four
questions (CHALLENGE_BRIEF.md §2c). Numbers on screen come from the data. Do not quote any other numbers.

## Before the jury (10 min)
1. `streamlit run src/dashboard.py --server.port 8599` and open it full-screen at 1440 px or wider.
2. On the launch screen pick **Crisis manager** (or open `/?role=manager`). Open each page and tab once to load the
   tiles and caches: Crisis room (Live board, Priorities, Rivers), Town plan (Bad Neuenahr-Ahrweiler, incl. the 3D tab),
   Door-knock list, 2021, today, next. Then **Switch** → Resident once, and back.
3. **Restart the server** after any code change (Streamlit keeps the old `live.py` in memory), then Crisis room →
   **Reset**, mode **Drill: July 2021**, speed **6 h per second**. Reset clears the stale events and drafts. Make sure
   no other server plays the same `data/live.db`.
4. Check that `.env` holds `claude_api`. Without it the outbox uses templates (labelled "Template"), and the demo still works.

## Script

| Time | Screen and click | Say (short) | Question |
|---|---|---|---|
| 0:00 | Launch screen → **Crisis manager**. Crisis room, paused at **Fri 30 Oct 06:00** (the drill) | "Four roles, each sees only its own pages. Today is Friday. The rivers are normal, but the yellow box says a flood like July 2021 is coming: 60 towns reach evacuate by Monday. In July 2021 more than 200 people died in Germany and Belgium. Are we better prepared?" | — |
| 0:20 | Scroll to **July 2021: when the orders came** | "EFAS warned on 13 July before noon. The Vesdre order came at 17:57 on the 14th, the Ahr order at 23:09, after its gauge had failed. Erftstadt evacuated on the 15th." | Fix 2021 |
| 0:50 | Scroll up, **Play** | "This is a drill: the July 2021 river flows, modelled afterwards, replayed day by day as if they started today. Towns turn amber, then red. At each step the mayor and the fire brigade get a briefing, drafted by Claude from our numbers." | Q4 |
| 1:30 | Pause on Sun 1 Nov (the flows of 14 Jul). Pick a draft under **Briefing drafts** | "Claude writes the words. Every number comes from the engine. These are drafts: nothing is sent until a person checks them." | AI use |
| 1:50 | Click the Ahr on the map → **Open the plan** | "Bad Neuenahr-Ahrweiler: who leaves, where to, who gives the order." Read the red verdict line. | Q1 + Q3 |
| 2:30 | Town plan tabs: **Evacuate first**, then **Orders & message** | "People who cannot leave alone go first: care homes and single-storey homes. And here is who gives the order in this country." | Fix 2021 |
| 3:00 | **Switch** → **Resident**. Type `Ahrstraße 28, Ahrbrück` | "A resident types an address and gets: leave, where to, how many minutes." | Q3 |
| 3:25 | **Switch** → **Fire brigade**: the **Door-knock list** | "Crews see which homes have not reported safe (simulated in the replay) and can close a road. Every page updates live." | Fix 2021 |
| 3:50 | **Switch** → **Policy maker**: **2021, today, next** → **What to fix** | "Each gap, the measure that closes it, the money that exists for it, and where there is none." | Q2 |
| 4:20 | **Crisis room** (in the policy maker's sidebar) | Close with the limits (below) and the ask: "Give each mayor this plan before the next warning." | Q4 |

## Limits to say (one sentence each, at 4:20)
- The drill is the July 2021 replay with its dates moved to start on Fri 30 Oct: the river flows were known afterwards,
  they are not the forecasts of the day, and they give the day, not the hour.
- The satellite counts are a floor; the Vesdre is modelled (EFAS 500-year).
- The shelters are OpenStreetMap candidates, not official shelters; the check-ins in the replay are simulated.

## If something fails
- Map tiles blank: keep talking over the counters and the event feed; the 3D view loads separately.
- Claude unavailable: the reports fall back to templates (labelled); say so.
- The replay runs too fast or too slow: Pause, set the speed, then Play again. Reset returns to Fri 30 Oct 06:00 (the flows of 12 July).

## Do not say
- "The tool would have warned hours earlier": the replay times are hindsight and daily.
- "Real river flows" or "the July 2021 peak was N m³/s": the GloFAS flows are modelled. At Altenahr the model peaks at
  about 250 m³/s, against a reconstructed 750-1,000 m³/s (docs/TIMELINE_2021.md). The model ranks the flood; it does
  not measure it.
- "Terrain ML beats EFAS on the Ahr": the confidence interval includes zero (docs/ML.md §8). Pooled AUC 0.75 → 0.79 is fine.
- Any count of the dead or of the damage that is not in the brief's sources.
