# 5-minute demo script (jury, Fri 30 Oct)

One message: **in 2021 the warnings came a day or more before the orders. This tool turns a river warning into an
order, a place to go and a door-knock list for every town in the 2021 water.** Every screen answers one of the four
questions (CHALLENGE_BRIEF.md §2c). Numbers on screen come from the data. Do not quote any other numbers.

## Before the jury (10 min)
1. `streamlit run src/dashboard.py --server.port 8599` and open it full-screen at 1440 px or wider.
2. Open each page once to load the tiles and caches: Crisis room, Town plan (Bad Neuenahr-Ahrweiler), 3D view, Do I need
   to leave?, Check-ins, Long term.
3. **Restart the server** after any code change (Streamlit keeps the old `live.py` in memory), then Crisis room →
   **Reset**, mode **Replay July 2021**, speed **6 h per second**. Reset clears the stale events and drafts. Make sure
   no other server plays the same `data/live.db`.
4. Check that `.env` holds `claude_api`. Without it the outbox uses templates (labelled "Template"), and the demo still works.

## Script

| Time | Screen and click | Say (short) | Question |
|---|---|---|---|
| 0:00 | Crisis room, paused at 12 Jul | "July 2021: more than 200 dead in Germany and Belgium. Anna has a new warning today. Are we better prepared?" | — |
| 0:20 | Scroll to **July 2021: when the orders came** | "EFAS warned on 13 July before noon. The Vesdre order came at 17:57 on the 14th, the Ahr order at 23:09, after its gauge had failed. Erftstadt evacuated on the 15th." | Fix 2021 |
| 0:50 | Scroll up, **Play** | "We replay modelled river flows for July 2021, computed afterwards, day by day. Towns turn amber, then red. At each step the mayor and the fire brigade get a briefing, drafted by Claude from our numbers." | Q4 |
| 1:30 | Pause near 14 Jul. Open one outbox report | "Claude writes the words. Every number comes from the engine. These are drafts: nothing is sent until a person checks them." | AI use |
| 1:50 | Click the Ahr on the map → **Open the plan** | "Bad Neuenahr-Ahrweiler: who leaves, where to, who gives the order." Read the red verdict line. | Q1 + Q3 |
| 2:30 | Town plan tabs: **Evacuate first**, then **Who gives the order** | "People who cannot leave alone go first: care homes and single-storey homes. And here is who gives the order in this country." | Fix 2021 |
| 3:00 | **Do I need to leave?** Type `Ahrstraße 28, Ahrbrück` | "A resident types an address and gets: leave, where to, how many minutes." | Q3 |
| 3:25 | **Check-ins and door-knock list** | "Crews see which homes have not reported safe (simulated in the replay) and can close a road. Every page updates live." | Fix 2021 |
| 3:50 | **Long term** | "Each gap, the measure that closes it, the money that exists for it, and where there is none." | Q2 |
| 4:20 | Back to the Crisis room | Close with the limits (below) and the ask: "Give each mayor this plan before the next warning." | Q4 |

## Limits to say (one sentence each, at 4:20)
- The replay uses river flows known afterwards, not the forecasts of the day, and it gives the day, not the hour.
- The satellite counts are a floor; the Vesdre is modelled (EFAS 500-year).
- The shelters are OpenStreetMap candidates, not official shelters; the check-ins in the replay are simulated.

## If something fails
- Map tiles blank: keep talking over the counters and the event feed; the 3D view loads separately.
- Claude unavailable: the reports fall back to templates (labelled); say so.
- The replay runs too fast or too slow: Pause, set the speed, then Play again. Reset returns to 12 July.

## Do not say
- "The tool would have warned hours earlier": the replay times are hindsight and daily.
- "Real river flows" or "the July 2021 peak was N m³/s": the GloFAS flows are modelled. At Altenahr the model peaks at
  about 250 m³/s, against a reconstructed 750-1,000 m³/s (docs/TIMELINE_2021.md). The model ranks the flood; it does
  not measure it.
- "Terrain ML beats EFAS on the Ahr": the confidence interval includes zero (docs/ML.md §8). Pooled AUC 0.75 → 0.79 is fine.
- Any count of the dead or of the damage that is not in the brief's sources.
