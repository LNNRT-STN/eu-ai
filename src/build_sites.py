"""Sites for the action dashboard (dashboard.py), from the OSM extract enrich.py made. Run after build_meuse.py:
python src/build_sites.py → out/meuse/sites.parquet

role = shelter: candidate shelter site, a school or town hall that stayed dry in July 2021 (not inside or within
          100 m of the mapped water) and sits outside the EFAS 10- and 100-year zones. Not an official shelter list.
role = evacuate: hospital or care home inside or within 100 m of the 2021 water, or inside the EFAS 100-year zone.
Each site gets its commune (GISCO LAU 2021) so the dashboard can pair a risk area with dry sites nearby."""
from pathlib import Path

import geopandas as gpd
import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
DST = OUT / "meuse"
LOCAL_NAME = {"Luik": "Liège", "Wezet": "Visé", "Limburg": "Limbourg", "Bitsingen": "Bassenge",  # as build_meuse.py
              "Saint-Nicolas (Luik)": "Saint-Nicolas", "Hoei": "Huy", "Namen": "Namur", "Borgworm": "Waremme"}
NOT_MEUSE = ("BE_71",)
SHELTER = {"school", "town_hall"}
VULNERABLE = {"hospital", "care_home"}
LABEL = {"school": "School", "town_hall": "Town hall", "hospital": "Hospital", "care_home": "Care home"}

aoi = gpd.read_file(DST / "aoi.geojson")
fac = pd.read_parquet(OUT / "osm_facilities.parquet")
fac = fac[fac.aoi_id.isin(aoi.aoi_id) & fac.category.isin(SHELTER | VULNERABLE)]
fac = gpd.GeoDataFrame(fac, geometry=gpd.points_from_xy(fac.lon, fac.lat), crs=4326)

wet2021 = fac.in_flood | fac.near_flood
zone = fac.efas.isin(["RP10", "RP100"])
fac["role"] = None
fac.loc[fac.category.isin(SHELTER) & ~wet2021 & ~zone, "role"] = "shelter"
fac.loc[fac.category.isin(VULNERABLE) & (wet2021 | zone), "role"] = "evacuate"
fac = fac[fac.role.notna()]

x0, y0, x1, y1 = aoi.total_bounds
lau = gpd.read_parquet(OUT / "raw" / "LAU_RG_01M_2021_4326.parquet").rename_geometry("geometry").set_crs(4326, allow_override=True)
lau = lau[lau.CNTR_CODE.isin(["BE", "DE", "NL"])].cx[x0:x1, y0:y1]
lau = lau.rename(columns={"GISCO_ID": "lau_id", "LAU_NAME": "commune"})
lau["commune"] = lau.commune.replace(LOCAL_NAME)
fac = gpd.sjoin(fac, lau[["lau_id", "commune", "geometry"]], predicate="within").drop(columns="index_right")
fac = fac[~fac.lau_id.str.startswith(NOT_MEUSE)].drop_duplicates("osm_id")

fac["type"] = fac.category.map(LABEL)
fac["name"] = fac.name.where(fac.name.str.strip() != "", "Unnamed " + fac.type.str.lower())
fac["country"] = fac.lau_id.str[:2]
fac["flood_2021"] = fac.in_flood.map({True: "In the water"}).fillna(fac.near_flood.map({True: "Within 100 m", False: "Dry"}))
fac["model_zone"] = fac.efas.map({"RP10": "10-year zone", "RP100": "100-year zone", "RP500": "500-year zone only",
                                  "none": "Outside all zones"})
cols = ["osm_id", "role", "type", "name", "commune", "lau_id", "country", "lon", "lat", "flood_2021", "model_zone"]
fac[cols].sort_values(["role", "commune", "type", "name"]).to_parquet(DST / "sites.parquet", index=False)
print(fac.groupby(["role", "country", "type"]).size().to_string())
