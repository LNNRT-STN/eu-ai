"""July 2021 impact per commune, for the green→red map layer. Run after build_meuse.py:
python src/build_regions.py → out/meuse/regions.geojson

score = mean percentile rank (among hit communes) of residents in the water, flooded buildings and share of the
commune's population in the water. EMS damage grading exists only for Eschweiler and Wassenberg, so damage is
reported per commune where graded but kept out of the score (it would make every Belgian and Dutch commune look fine)."""
from pathlib import Path

import geopandas as gpd
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "working_data"
OUT = Path(__file__).resolve().parent / "out"
DST = OUT / "meuse"
LOCAL_NAME = {"Luik": "Liège", "Wezet": "Visé", "Limburg": "Limbourg", "Bitsingen": "Bassenge",  # as build_meuse.py
              "Saint-Nicolas (Luik)": "Saint-Nicolas", "Hoei": "Huy", "Namen": "Namur", "Borgworm": "Waremme"}
NOT_MEUSE = ("BE_71",)
# the radar map missed most of the flooding here (same list as the Risk areas note in views/risk_areas.py)
UNDER_DETECTED = {"Pepinster", "Verviers", "Chaudfontaine", "Trooz", "Liège"}
GRADED = ["EMSR517_AOI09", "EMSR517_AOI10"]
CLASSES = ["Not reached by mapped water", "Low", "Moderate", "High", "Severe"]

aoi = gpd.read_file(DST / "aoi.geojson")
x0, y0, x1, y1 = aoi.total_bounds
lau = gpd.read_parquet(OUT / "raw" / "LAU_RG_01M_2021_4326.parquet").rename_geometry("geometry").set_crs(4326, allow_override=True)
lau = lau[lau.CNTR_CODE.isin(["BE", "DE", "NL"])].cx[x0:x1, y0:y1]
lau = lau[~lau.GISCO_ID.str.startswith(NOT_MEUSE)].rename(columns={"GISCO_ID": "lau_id", "LAU_NAME": "commune"})
lau["commune"] = lau.commune.replace(LOCAL_NAME)

# share of each commune inside the satellite-mapped area; drop communes barely touched by it
m = lau.to_crs(3035)
mapped = gpd.overlay(m[["lau_id", "geometry"]], aoi.to_crs(3035)[["geometry"]], how="intersection")
share = mapped.assign(a=mapped.area).groupby("lau_id").a.sum() / m.set_index("lau_id").area
lau = lau.assign(mapped_share=lau.lau_id.map(share).fillna(0))
lau = lau[lau.mapped_share >= 0.1]

obs = pd.read_parquet(DST / "communes.parquet").query("lens == 'obs'")[["lau_id", "buildings", "residential", "residents"]]
r = lau.merge(obs, on="lau_id", how="left").fillna({"buildings": 0, "residential": 0, "residents": 0})
r["pop_share"] = r.residents / r.POP_2021.where(r.POP_2021 > 0)

# EMS damage grading points (Germany only) counted per commune
gra = pd.concat(gpd.read_file(f) for a in GRADED for f in DATA.glob(f"ems_de/{a}_GRA_PRODUCT*/*builtUpP*.shp"))
gra = gpd.sjoin(gra.to_crs(4326)[["damage_gra", "geometry"]], r[["lau_id", "geometry"]], predicate="within")
dmg = gra.groupby(["lau_id", "damage_gra"]).size().unstack(fill_value=0)
r = r.merge(dmg.rename(columns=str.lower).add_prefix("gra_"), left_on="lau_id", right_index=True, how="left")
r["graded"] = r.lau_id.isin(dmg.index) | r.lau_id.str.startswith("DE")  # the German Meuse AOIs are both graded

hit = r.buildings > 0
r["score"] = 0.0
r.loc[hit, "score"] = r[hit][["residents", "buildings", "pop_share"]].rank(pct=True).mean(axis=1)
r["cls"] = 0
r.loc[hit, "cls"] = pd.qcut(r.loc[hit, "score"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
r["class_label"] = r.cls.map(dict(enumerate(CLASSES)))
r["under_detected"] = r.commune.isin(UNDER_DETECTED)

keep = ["lau_id", "commune", "CNTR_CODE", "POP_2021", "mapped_share", "buildings", "residential", "residents",
        "pop_share", "score", "cls", "class_label", "graded", "under_detected"] + [c for c in r if c.startswith("gra_")]
r = r[keep + ["geometry"]].rename(columns={"CNTR_CODE": "country", "POP_2021": "population"})
r["geometry"] = r.geometry.simplify(0.0005)
r.fillna({c: 0 for c in r if c.startswith("gra_")}).to_file(DST / "regions.geojson")
print(r.groupby("class_label").size().to_dict())
print(r.sort_values("score", ascending=False)[["commune", "country", "residents", "buildings", "pop_share", "class_label"]].head(8).to_string())
