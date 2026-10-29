"""Q1 preview on a test window over the Vesdre valley (BE): flooded buildings and people.
Every number printed here is re-runnable. Method notes are in the prints.
Run: .venv/Scripts/python.exe -I notebooks/q1_preview_vesdre.py
"""
import os, warnings, json
from pathlib import Path
warnings.filterwarnings("ignore")
os.environ["GS_NO_SIGN_REQUEST"] = "YES"
import gcsfs, rasterio, numpy as np, pandas as pd, geopandas as gpd
from rasterio.windows import from_bounds
from shapely.geometry import box
from shapely.validation import make_valid

OUT = Path("outputs/q1_preview"); OUT.mkdir(parents=True, exist_ok=True)
fs = gcsfs.GCSFileSystem(token="anon")
ROOT = "datasets_challenge/working_data"; V = "/vsigs/"
BBOX = (5.70, 50.52, 6.05, 50.66)      # lon/lat test window
METRIC = "EPSG:3035"                   # one metric CRS for all area maths
res = {}

# ---- 1. Flood extent (EMS BE, layer observedEventA) -------------------------------------------
def load_flood(kind):
    frames = []
    for p in fs.find(f"{ROOT}/ems_be"):
        if p.endswith(".shp") and "_observedEventA_" in p and (kind == "all" or f"_{kind}_" in Path(p).parent.name):
            g = gpd.read_file(V + p, bbox=BBOX, engine="pyogrio"); g["src"] = Path(p).parent.name[:30]
            frames.append(g)
    g = pd.concat(frames, ignore_index=True)
    n0 = len(g); bad = int((~g.geometry.is_valid).sum())
    g = g[g.obj_desc == "Riverine flood"].copy()                 # drop mudflow / landslide
    g["geometry"] = g.geometry.apply(make_valid)                 # repair invalid shapes
    g = g.to_crs(METRIC)
    geom = g.geometry.unary_union                                # dissolve overlaps: nothing counted twice
    return geom, dict(polygons=n0, invalid_repaired=bad, riverine=len(g), km2=round(geom.area / 1e6, 2))

flood_p, info_p = load_flood("PRODUCT"); flood_a, info_a = load_flood("all")
print("FLOOD PRODUCT-only :", info_p); print("FLOOD PRODUCT+MONIT:", info_a)
res["flood_product"], res["flood_all"] = info_p, info_a

# ---- 2. Buildings (OBAT BE) --------------------------------------------------------------------
gp = [x for x in fs.find(f"{ROOT}/obat_be") if x.endswith(".gpkg")][0]
b = gpd.read_file(V + gp, bbox=BBOX, engine="pyogrio")
b = b.to_crs(METRIC)
print("\nBUILDINGS in window:", len(b), "| use counts:", b["use"].value_counts().to_dict())

# ---- 3. Population (GHS-POP 2020) -> cells as polygons ----------------------------------------
pp = [x for x in fs.find(f"{ROOT}/ghs_pop") if "E2020" in x and x.endswith(".tif")][0]
with rasterio.open(V + pp) as r:
    win = from_bounds(*BBOX, transform=r.transform).round_offsets().round_lengths()
    arr = r.read(1, window=win); tr = r.window_transform(win)
rows, cols = np.nonzero(arr > 0)
cells = gpd.GeoDataFrame(
    {"pop": arr[rows, cols], "row": rows, "col": cols,
     "geometry": [box(*rasterio.transform.xy(tr, i, j, offset="ul"), *rasterio.transform.xy(tr, i + 1, j + 1, offset="ul"))
                  for i, j in zip(rows, cols)]}, crs="EPSG:4326").to_crs(METRIC)
print("POP cells >0:", len(cells), "| total residents in window:", round(cells["pop"].sum()))

def people_flooded(flood):
    # Method A: area-weighted share of each cell under the flood shape
    share = cells.geometry.intersection(flood).area / cells.geometry.area
    a = float((cells["pop"] * share).sum())
    # Method B: dasymetric. Spread each cell's population over its residential (use==1) buildings, weight = footprint area
    bb = b[b["use"] == 1].copy()
    bb4326 = bb.to_crs("EPSG:4326")
    inv = ~tr
    cj, ri = zip(*[inv * (g.x, g.y) for g in bb4326.geometry])
    bb["col"], bb["row"] = np.floor(cj).astype(int), np.floor(ri).astype(int)
    bb = bb.merge(cells[["row", "col", "pop"]], on=["row", "col"], how="inner")
    bb["w"] = bb["area"] / bb.groupby(["row", "col"])["area"].transform("sum")
    bb["people"] = bb["pop"] * bb["w"]
    inside = bb[bb.geometry.within(flood)]
    unalloc = float(cells["pop"].sum() - bb["people"].sum())
    return a, float(inside["people"].sum()), unalloc, inside

for name, flood in (("PRODUCT-only", flood_p), ("PRODUCT+MONIT", flood_a)):
    inside = b[b.geometry.within(flood)]
    a, d, un, _ = people_flooded(flood)
    print(f"\n=== {name} ===")
    print("buildings flooded:", len(inside), "of", len(b), f"({len(inside)/len(b)*100:.1f}%)", "| by use:", inside["use"].value_counts().to_dict())
    print("flooded footprint area m2 (sum):", round(inside["area"].sum()))
    print("people flooded, A area-weighted :", round(a))
    print("people flooded, B dasymetric    :", round(d), f"(population not placed on any residential building: {round(un)})")
    res[name] = dict(buildings=len(inside), by_use={int(k): int(v) for k, v in inside["use"].value_counts().items()},
                     people_area_weighted=round(a), people_dasymetric=round(d))
    if name == "PRODUCT+MONIT":
        ins, outs = inside, b.drop(inside.index)
        print("height-missing among flooded:", int(ins["height"].isna().sum()))

json.dump(res, open(OUT / "q1_preview_results.json", "w"), indent=2)

# ---- 4. Visual spot check ------------------------------------------------------------------
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(11, 6))
gpd.GeoSeries([flood_a], crs=METRIC).plot(ax=ax, color="#3b82c4", alpha=.45)
ins = b[b.geometry.within(flood_a)]
b.drop(ins.index).sample(min(20000, len(b) - len(ins)), random_state=0).plot(ax=ax, markersize=.3, color="#999")
ins.plot(ax=ax, markersize=2, color="#c8321f")
ax.set_title(f"Vesdre test window: flood (blue), flooded buildings (red, n={len(ins)}), other buildings (grey sample)")
ax.set_axis_off(); fig.savefig(OUT / "spotcheck.png", dpi=130, bbox_inches="tight")
print("\nsaved", OUT / "spotcheck.png")
