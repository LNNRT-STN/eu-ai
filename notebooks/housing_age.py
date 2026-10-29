"""Housing age in the 2021 flood (worst variant), per study area and municipality -> outputs/data/housing_age.csv

Buildings = GHS-OBAT points inside outputs/data/flood_<area>_worst.geojson (only each flood's bounding box is read). Codes from GHS-OBAT_R2024_online_v2.pdf (bucket, sec. 3.1.1):
  use   1 residential, 2 non-residential, 0 outside built-up domain
  epoch 1 <1980, 2 1980-90, 3 1990-2000, 4 2000-10, 5 2010-20, 0 outside built-up domain (= unknown here)
Epoch is the majority "first built-up year" of 100 m grid cells, not a per-building year: a new house in an old
neighbourhood is coded <1980. Use as a neighbourhood-age signal only.
A building in two areas' floods is counted once, in the first area (same order as pipeline.py).
Also writes outputs/data/buildings_3d.parquet: one row per OBAT building in the worst flood (counted once), with
lon, lat (EPSG:4326), use, height_m (NaN if unknown), storeys (= height / 3 m rounded, clipped 1-10, NaN if unknown),
epoch, municipality. Reads the local copy in challenge_data/ if present, else the public bucket (slow).
Run from the repo root: python notebooks/housing_age.py
"""
import os
os.environ.setdefault("GS_NO_SIGN_REQUEST", "YES")
from pathlib import Path
import numpy as np, geopandas as gpd, pandas as pd, pyogrio

OUT = "outputs/data"
LOCAL = "challenge_data/obat_{c}/GHS_OBAT_GPKG_{C}_E2020_R2024A_V1_0/GHS_OBAT_GPKG_{C}_E2020_R2024A_V1_0.gpkg"
SRC = "/vsigs/datasets_challenge/working_data/obat_{c}/GHS_OBAT_GPKG_{C}_E2020_R2024A_V1_0/GHS_OBAT_GPKG_{C}_E2020_R2024A_V1_0.gpkg"
AREAS = [("ahr", "de"), ("liege", "be"), ("rochefort", "be"), ("venlo", "nl"), ("eschweiler", "de"), ("wassenberg", "de"),
         ("schleiden", "de"), ("euskirchen", "de"), ("erftstadt", "de"), ("vesdre", "be")]   # order = pipeline.py
ISO3 = {"be": "BEL", "nl": "NLD", "de": "DEU"}

munis = gpd.read_file(f"{OUT}/municipality_outlines.geojson")[["municipality", "geometry"]].to_crs(4326)
seen, rows, pts = set(), [], []
for area, cc in AREAS:
    flood = gpd.read_file(f"{OUT}/flood_{area}_worst.geojson").to_crs(4326)
    path = LOCAL.format(c=cc, C=ISO3[cc])
    path = path if Path(path).exists() else SRC.format(c=cc, C=ISO3[cc])
    b = pyogrio.read_dataframe(path, bbox=tuple(flood.total_bounds), columns=["id", "use", "epoch", "height"])
    b = b[b.within(flood.union_all())]
    b = b[~b["id"].isin(seen)]; seen |= set(b["id"])
    j = gpd.sjoin(b, munis, predicate="within", how="left")
    b["municipality"] = j[~j.index.duplicated()]["municipality"].reindex(b.index).fillna("(outside mapped municipalities)")
    h = b["height"].where(b["height"] > 0)
    pts.append(pd.DataFrame(dict(area=area, lon=b.geometry.x.round(5), lat=b.geometry.y.round(5), use=b["use"].values,
                                 height_m=h.round(1), storeys=np.clip(np.round(h / 3.0), 1, 10), epoch=b["epoch"].values,
                                 municipality=b["municipality"])))
    print(area, cc, len(b), "buildings in flood", flush=True)
    res = b["use"] == 1
    g = b.assign(res=res, pre=res & (b.epoch == 1), unk=res & ~b.epoch.between(1, 5), nonres=b["use"] == 2)
    g = g.groupby("municipality")[["res", "pre", "unk", "nonres"]].sum()
    g["buildings_all"] = b.groupby("municipality").size()
    for m, r in g.iterrows():
        known = r.res - r.unk
        rows.append(dict(area=area, country=cc.upper(), municipality=m, residential_in_flood=int(r.res),
                         res_pre1980=int(r.pre), res_epoch_unknown=int(r.unk),
                         share_pre1980=round(r.pre / known, 3) if known else None,
                         nonres_in_flood=int(r.nonres), buildings_in_flood=int(r.buildings_all)))

df = pd.DataFrame(rows).sort_values(["area", "res_pre1980"], ascending=[True, False])
df.to_csv(f"{OUT}/housing_age.csv", index=False)
pd.concat(pts, ignore_index=True).to_parquet(f"{OUT}/buildings_3d.parquet", index=False)
print(df.to_string(index=False))
