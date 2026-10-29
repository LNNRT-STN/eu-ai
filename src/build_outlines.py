"""Municipality outlines for the dashboard maps: the GISCO LAU 2021 polygon of every municipality in the cleaned data.
Run after build_meuse.py (it downloads the LAU file): python src/build_outlines.py → outputs/data/municipality_outlines.geojson

Matched on name and country; where a name occurs twice (Blankenheim, DE) the polygon holding the town centre wins."""
from pathlib import Path

import geopandas as gpd
import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
DATA = Path(__file__).resolve().parents[1] / "outputs" / "data"

towns = pd.read_csv(DATA / "app_towns.csv", encoding="utf-8-sig").drop_duplicates("municipality")
towns["cn"], towns["nm"] = towns.municipality.str[-3:-1], towns.municipality.str.replace(r" \(..\)$", "", regex=True)
lau = gpd.read_parquet(OUT / "raw" / "LAU_RG_01M_2021_4326.parquet").rename_geometry("geometry").set_crs(4326, allow_override=True)
lau = lau[lau.CNTR_CODE.isin(["BE", "DE", "NL"])]

m = gpd.GeoDataFrame(towns.merge(lau, left_on=["cn", "nm"], right_on=["CNTR_CODE", "LAU_NAME"]), crs=4326)
m = m[[g.contains(p) or n == 1 for g, p, n in zip(m.geometry, gpd.points_from_xy(m.lon, m.lat),
                                                     m.groupby("municipality").municipality.transform("size"))]]
missing = set(towns.municipality) - set(m.municipality)
assert not missing, f"no LAU polygon for {missing}"

m = m[["municipality", "GISCO_ID", "POP_2021", "AREA_KM2", "geometry"]].rename(
    columns={"GISCO_ID": "lau_id", "POP_2021": "population_2021", "AREA_KM2": "area_km2"})
m["geometry"] = m.geometry.simplify(0.0005)  # ≈ 50 m: plenty at commune zoom, keeps the file small
m.to_file(DATA / "municipality_outlines.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
print(f"{len(m)} outlines → {DATA / 'municipality_outlines.geojson'}")
