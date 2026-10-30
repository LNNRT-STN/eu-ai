---
version: 1
slug: "web-src-app-tsx"
primary_target: "web/src/App.tsx"
related_targets: ["web/src","api/main.py"]
---

## Scope
React + Vite + shadcn/ui frontend (web/) over a FastAPI layer (api/main.py) that reuses src/live.py and src/anna.py. Mode: Operate. Audience: crisis managers (Anna first), projected for a jury. This pass: Region (crisis board), Town plan, Data & limits. Door-knock, Resident and 2021 vs today stay in Streamlit for now.

## Direction contract
THESIS: One verdict per screen, then the list, then the detail. Each level opens only when asked (row → panel, panel → tab, tab → "How this is computed"). Refuses the Streamlit wall of metrics, tabs and captions all visible at once.
OWN-WORLD: shadcn Nova, neutral (Geist, oklch greys, hairline borders, 10px radius). Colour only carries flood status: evacuate red, watch amber, normal grey; First/Next/Then tiers red/orange/grey; dry shelter green; EFAS water blue. Always paired with a word.
STORY: The manager sees whether to act and where (Region), opens one town and reads its first action and who leaves (Town plan), and checks what the numbers cannot say (Data & limits).
FIRST VIEWPORT: Left sidebar (Region, Town plan, Data & limits; its foot holds the planning-tool disclaimer). The scenario switch lives in the header only, one control for the whole desk. Header: page title plus flood scenario segmented control (Normal / 10 / 100 / 500-year). Body: verdict line at the top, map (about 60 %) beside a ranked town list; picking a town flies the camera there.
FORM: user-pinned (fresh shadcn-native look, neutral base, flood-status colours only); no seed roll. Signature move: the camera's fly-to (zoom out, glide, zoom in) on every change of place, jumpTo under reduced motion.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
