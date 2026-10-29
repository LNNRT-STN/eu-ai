"""Q1 preview from LOCAL data (challenge_data/). Flooded buildings and people per study area,
plus an EFAS (modelled) proxy for the Vesdre valley, where EMS has no flood polygons.
Run from eu-ai/:  .venv/Scripts/python.exe -I notebooks/q1_preview_local.py
Methods:
  flood      = EMS observedEventA, obj_desc == 'Riverine flood', invalid shapes repaired, dissolved
  buildings  = GHS-OBAT points inside the flood shape (point-in-polygon, EPSG:3035)
  people (B) = dasymetric: each GHS-POP 2020 cell's residents spread over its residential (use==1)
               buildings, weighted by OBAT footprint area; summed over flooded buildings. PRIMARY.
  people (A) = cross-check: share of each cell's area under the flood shape x cell residents.
"""
import json, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from rasterio.windows import from_bounds
from shapely.geometry import box
from shapely.validation import make_valid

D = Path("challenge_data"); OUT = Path("outputs/q1_preview"); OUT.mkdir(parents=True, exist_ok=True)
M = "EPSG:3035"
POP = D / "ghs_pop/GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0/GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
OBAT = {"be": D / "obat_be/GHS_OBAT_GPKG_BEL_E2020_R2024A_V1_0/GHS_OBAT_GPKG_BEL_E2020_R2024A_V1_0.gpkg",
        "nl": D / "obat_nl/GHS_OBAT_GPKG_NLD_E2020_R2024A_V1_0/GHS_OBAT_GPKG_NLD_E2020_R2024A_V1_0.gpkg",
        "de": D / "obat_de/GHS_OBAT_GPKG_DEU_E2020_R2024A_V1_0/GHS_OBAT_GPKG_DEU_E2020_R2024A_V1_0.gpkg"}
AREAS = [("BE Liege (EMSR518 AOI01)", "be", "EMSR518_AOI01_"), ("BE Rochefort (EMSR518 AOI02)", "be", "EMSR518_AOI02_"),
         ("NL Venlo (EMSR520 AOI01)", "nl", "EMSR520_AOI01_"), ("DE Ahrweiler (EMSR517 AOI15)", "de", "EMSR517_AOI15_"),
         ("DE Honningen (EMSR517 AOI03)", "de", "EMSR517_AOI03_")]

def flood_geom(cc, key, kinds):
    parts = []
    for prod in (D / f"ems_{cc}").iterdir():
        if prod.is_dir() and key in prod.name and any(k in prod.name for k in kinds):
            for f in prod.glob("*observedEventA*.shp"):
                g = gpd.read_file(f); g = g[g.obj_desc == "Riverine flood"]
                g["geometry"] = g.geometry.apply(make_valid); parts.append(g.to_crs(M))
    g = pd.concat(parts, ignore_index=True)
    return g.unary_union, len(g)

def read_pop(bbox):
    with rasterio.open(POP) as r:
        win = from_bounds(*bbox, transform=r.transform).round_offsets().round_lengths()
        return r.read(1, window=win), r.window_transform(win)

def read_buildings(cc, bbox):
    b = gpd.read_file(OBAT[cc], bbox=bbox, engine="pyogrio")
    b["lon"], b["lat"] = b.geometry.x, b.geometry.y
    b = b.to_crs(M); b["x"], b["y"] = b.geometry.x, b.geometry.y
    return b

def attach_people(b, arr, tr):
    """Dasymetric allocation. Returns b with 'people' and the unallocated residents."""
    col = np.floor((b["lon"].values - tr.c) / tr.a).astype(int); row = np.floor((b["lat"].values - tr.f) / tr.e).astype(int)
    ok = (row >= 0) & (row < arr.shape[0]) & (col >= 0) & (col < arr.shape[1])
    b = b.assign(row=row, col=col)[ok].copy()
    b["cellpop"] = arr[b["row"].values, b["col"].values]
    res = b["use"] == 1
    w = b["area"].where(res, 0.0)
    b["people"] = b["cellpop"] * w / w.groupby([b["row"], b["col"]]).transform("sum").replace(0, np.nan)
    b["people"] = b["people"].fillna(0.0)
    placed = float(b["people"].sum())
    return b, placed

def area_weighted(arr, tr, flood):
    rows, cols = np.nonzero(arr > 0)
    cells = gpd.GeoDataFrame({"pop": arr[rows, cols],
        "geometry": [box(*rasterio.transform.xy(tr, i, j, offset="ul"), *rasterio.transform.xy(tr, i + 1, j + 1, offset="ul")) for i, j in zip(rows, cols)]},
        crs="EPSG:4326").to_crs(M)
    share = cells.geometry.intersection(flood).area / cells.geometry.area
    return float((cells["pop"] * share).sum())

rows_out = []
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
for name, cc, key in AREAS:
    out = {"area": name}
    for label, kinds in (("product", ["PRODUCT"]), ("product+monit", ["PRODUCT", "MONIT"])):
        fl, n = flood_geom(cc, key, kinds)
        x0, y0, x1, y1 = gpd.GeoSeries([fl], crs=M).to_crs(4326).total_bounds
        bbox = (x0 - .03, y0 - .03, x1 + .03, y1 + .03)
        b = read_buildings(cc, bbox); arr, tr = read_pop(bbox)
        b, placed = attach_people(b, arr, tr)
        inside = shapely.contains_xy(fl, b["x"].values, b["y"].values)
        f = b[inside]
        out.update({f"{label}:polygons": n, f"{label}:flood_km2": round(fl.area / 1e6, 2), f"{label}:buildings_window": len(b),
                    f"{label}:buildings_flooded": len(f), f"{label}:flooded_residential": int((f["use"] == 1).sum()),
                    f"{label}:flooded_use0": int((f["use"] == 0).sum()), f"{label}:flooded_use2": int((f["use"] == 2).sum()),
                    f"{label}:people_dasymetric": round(float(f["people"].sum())),
                    f"{label}:people_areaweighted": round(area_weighted(arr, tr, fl)),
                    f"{label}:window_pop": round(float(arr.sum())), f"{label}:pop_unplaced": round(float(arr.sum()) - placed),
                    f"{label}:people_per_building": round(float(arr.sum()) / len(b), 2)})
        if label == "product+monit":
            fig, ax = plt.subplots(figsize=(9, 8)); gpd.GeoSeries([fl], crs=M).plot(ax=ax, color="#3b82c4", alpha=.5)
            b[~inside].sample(min(15000, int((~inside).sum())), random_state=0).plot(ax=ax, markersize=.3, color="#999")
            f.plot(ax=ax, markersize=2, color="#c8321f"); ax.set_axis_off()
            ax.set_title(f"{name}: flood (blue), flooded buildings (red, n={len(f)})")
            fig.savefig(OUT / ("spot_" + key.strip("_") + ".png"), dpi=110, bbox_inches="tight"); plt.close(fig)
    rows_out.append(out); print(json.dumps(out, indent=1), flush=True)

# ---- Vesdre: EMS has no polygons there -> modelled EFAS proxy (NOT the observed 2021 flood) -------------
VB = (5.60, 50.54, 5.95, 50.64)
b = read_buildings("be", VB); arr, tr = read_pop(VB); b, placed = attach_people(b, arr, tr)
ves = {"area": "Vesdre valley (EFAS proxy)", "buildings_window": len(b), "window_pop": round(float(arr.sum()))}
for rp in (10, 100, 500):
    with rasterio.open(D / f"cems-efas/Europe_RP{rp}_filled_depth.tif") as r:
        win = from_bounds(*VB, transform=r.transform).round_offsets().round_lengths()
        d = r.read(1, window=win); t = r.window_transform(win)
    c = np.floor((b["lon"].values - t.c) / t.a).astype(int); rr = np.floor((b["lat"].values - t.f) / t.e).astype(int)
    ok = (rr >= 0) & (rr < d.shape[0]) & (c >= 0) & (c < d.shape[1])
    depth = np.where(ok, d[np.clip(rr, 0, d.shape[0]-1), np.clip(c, 0, d.shape[1]-1)], -9999)
    for thr in (0.1, 0.5):
        wet = depth > thr; f = b[wet]
        ves[f"RP{rp}>{thr}m:buildings"] = len(f); ves[f"RP{rp}>{thr}m:residential"] = int((f["use"] == 1).sum())
        ves[f"RP{rp}>{thr}m:people_dasymetric"] = round(float(f["people"].sum()))
    ves[f"RP{rp}:wet_pixels"] = int((d > 0).sum()); ves[f"RP{rp}:max_depth_m"] = round(float(d[d > 0].max()), 1) if (d > 0).any() else None
rows_out.append(ves); print(json.dumps(ves, indent=1))
json.dump(rows_out, open(OUT / "q1_preview_results.json", "w"), indent=2)
pd.DataFrame(rows_out).T.to_csv(OUT / "q1_preview_results.csv")
print("done")
