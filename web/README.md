# Flood desk · React frontend

React + Vite + [shadcn/ui](https://github.com/shadcn-ui/ui) (Nova preset, neutral) over a FastAPI layer
(`api/main.py`) that reuses `src/live.py` and `src/anna.py`, so every number matches the Streamlit dashboard.
The Claude key and the shared scenario stay in the Python process.

This pass covers the Region board, the Town plan and Data & limits. The door-knock list, the resident page and
2021 vs today are still in Streamlit (`streamlit run src/dashboard.py`).

## Run it

```bash
# from the repo root, once
.venv/bin/pip install -r requirements.txt
cd web && npm install

# two terminals
.venv/bin/uvicorn api.main:app --reload    # http://127.0.0.1:8000
cd web && npm run dev                      # http://localhost:5173 (proxies /api to :8000)
```

`LIVE_DB=/path/to/scratch.db` points the API at a scratch copy of the shared scenario database (tests, demos).

## How it reads

Each screen opens with one verdict sentence, then a list, then the detail on demand:

- **Region**: verdict for the flood switched on; map beside the towns to act in. Picking a town flies the camera
  there and swaps the list for that town's panel; briefings, residents' reports and the method sit in folds below.
- **Town plan**: the first action and where residents go (walk / bus / no place); map beside three tabs (who
  leaves in order, shelters, care sites). Picking an address frames it with its shelter and the route between them.
  Getting out, the warning message, who gives the order and the method sit in folds below.
- **Data & limits**: every source and limit is one row; open it for the detail.

The flood scenario (Normal / 10 / 100 / 500-year) in the header is shared by everyone on the desk, as in Streamlit.
Every change of place moves the map with MapLibre's `flyTo` (zoom out, glide, zoom in); with reduced motion it jumps.
