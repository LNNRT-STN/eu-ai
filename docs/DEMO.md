# 5-minute demo script (jury, Fri 30 Oct)

One message: **pick how rare a flood to plan for, and the tool turns it into an order, a place to go and a door-knock
list for every town in the zone. A rarer flood puts more people in the water and takes shelters away at the same
time.** Numbers on screen come from the data (`outputs/rp/`). Do not quote any other numbers.

## Before the jury (10 min)
1. `streamlit run src/dashboard.py --server.port 8599`, full-screen at 1440 px or wider.
2. Open `/?role=manager`. In the sidebar switch on **100-year**, open every page and tab once (Crisis room: Board,
   Priorities, Rivers; Town plan for Bad Neuenahr-Ahrweiler incl. the 3D tab; Door-knock list; 2021 vs today), then
   **Back to normal**. Switching on queues about 250 briefings; they draft in the background (biggest towns first).
3. **Restart the server** after any code change (Streamlit keeps the old `live.py` in memory). Make sure no other server
   uses the same `data/live.db`.
4. Check that `.env` holds `claude_api`. Without it the briefings use templates (labelled "Template"); the demo still works.

## Script

| Time | Screen and click | Say (short) |
|---|---|---|
| 0:00 | Launch → **Crisis manager**. Crisis room, sidebar says **Normal** | "Today nothing is happening. The question for a crisis room is: what if? Three roles share one scenario: the crisis room, the fire brigade, residents." |
| 0:20 | Sidebar: switch on **10-year** | "A 10-year flood: a 10 % chance every year. 125 towns, about 210,000 people in the zone." Point at the map and the **Return periods compared** table. |
| 0:50 | Also switch on **100-year** (both on) | "Now compare. The 100-year flood has a 1 % chance a year: about 74,000 more people, in the same valleys, the water climbs further up the streets. And look at the last column: we lose shelter sites, because they are in the water too." |
| 1:30 | Add **500-year** | "Even rarer: 326,000 people, 137,000 with no shelter place on foot. Buses to sites up to 10 km away leave about 5,000 with nothing." Read from the table. |
| 2:00 | Scroll to **Alerts and briefings**, pick a fire brigade draft | "Every town in the zone gets a briefing for its mayor and its fire brigade, written by Claude from our numbers: people, homes to check, which shelter, which road is closed. Drafts: nothing is sent until a person checks them." |
| 2:30 | Click Bad Neuenahr-Ahrweiler → **Town plan**, table "as the flood gets rarer" | "One town: the zone at 10, 100 and 500 years, the care homes to move first, the shelters it loses." |
| 3:00 | Town plan → **Orders & message** → Fire brigade: door to door | "This is how the fire brigade informs people: street by street, help requests and single-storey homes first, and for each street the shelter to send them to, with its address." |
| 3:30 | **Switch** → **Resident**. Type `Pützgasse 1, Bad Neuenahr-Ahrweiler` | "A resident types an address: in a 10-year flood this home stays dry, in a 100-year flood it is in the water. Leave now, go here. One tap: I am safe." Then back to the Crisis room: the check-in appears live. |
| 4:10 | **Switch** → **Fire brigade**: Door-knock list | "The crew sees that home as safe, and knocks on the others." |
| 4:30 | Close | Limits (below) and the ask: "Give each mayor this plan for the 100-year flood before the next warning." |

## Limits to say (one sentence each)
- The zones are EFAS model maps: every river at that return period at once, a planning map, not a forecast.
- The model has no dikes or flood walls: Liège and Venlo are an upper bound. Small streams (under 500 km²) are missing.
- The 2021 flood was bigger than these zones in the Ahr: on the 2021 page, the 100-year zone covers 42 % of the
  buildings the satellite saw flooded there.
- Residents are an order of magnitude; shelters are OpenStreetMap candidates, not official shelters.

## If something fails
- Map tiles blank: keep talking over the comparison table and the briefings.
- Claude unavailable: briefings fall back to templates (labelled); say so.
