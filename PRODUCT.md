# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Crisis managers and risk managers for the Meuse basin (Liège/Vesdre/Ourthe, Lesse, Dutch Limburg, Rur/Inde): the people in a provincial or municipal crisis cell who decide whom to warn, which sites to evacuate first and where people can go. Used both in quiet weeks (preparedness) and in the days before a flood (response); the home screen leads with the outlook.

## Product Purpose
Turn the July 2021 flood evidence and a live river outlook into actions: is a flood coming, which communes and care sites are exposed, and which dry sites could take people. Success: a crisis manager knows within seconds whether to act and where to look next.

## Positioning
Ties a live GloFAS river outlook, rated against each river's own July 2021 peak, to the people and sites that sat in the 2021 water or sit in the EFAS 100-year zone, per commune.

## Operating Context
European AI Challenge 2026 hackathon deliverable (policy tool), judged on evidence, policy usefulness, clarity and responsible AI. Streamlit app run locally (`streamlit run src/dashboard.py`). Official warnings come from SPW, Rijkswaterstaat and the German state flood centres; this tool is a heads-up.

## Capabilities and Constraints
- Challenge data: Copernicus EMS rapid mapping, EFAS 100-year hazard, GHS-OBAT buildings, GHS-POP. External: GISCO LAU communes, Open-Meteo (GloFAS, rain), OSM facilities.
- Shelter list = candidate sites (OSM schools and town halls, dry in 2021, outside EFAS 10/100-year zones). Not official shelters; no capacity data. OSM has no sites for the Eschweiler area.
- 2021 counts are a floor (radar missed the Vesdre valley and central Liège). Residents are an order of magnitude.
- Works offline without the outlook.

## Evidence on Hand
`src/out/meuse/` (summary, communes, cells, regions, sites), `docs/METHODOLOGY.md`. No shelter capacities, no official shelter lists, no measured gauge data: never fabricate these.

## Product Principles
1. Lead with the decision, then the evidence.
2. Every number names its source and its limit.
3. Disclose depth progressively: verdict, then list, then detail.
4. Candidate is never presented as official.
