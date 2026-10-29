"""Priority score per commune for the home page (views/briefing.py), and the July 2021 river replay. Run after
build_meuse.py, build_regions.py and build_sites.py: python src/build_priority.py → out/meuse/priority.geojson,
out/meuse/replay_2021.json, outputs/data/town_gauge.csv (--replay: only the last two)

Score, 0–10, built so a mayor can redo it by hand (thresholds are the team's choice, not an official standard):
  people in the EFAS 100-year zone   ≥ 50: 1 · ≥ 500: 2 · ≥ 2,000: 3 · ≥ 10,000: 4
  share of the commune's population  ≥ 5 %: 1 · ≥ 20 %: 2
  flooded in July 2021               satellite saw homes in the water, or it is on the missed list: 2
  care sites at risk                 1–2: 1 · 3 or more: 2
Level: 7–10 act first · 4–6 prepare · 1–3 watch. Shelter pressure (people per dry candidate site within 5 km) is
shown next to the score but kept out of it: OSM has no sites for the German side, which would inflate its score."""
import json, sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

import forecast

OUT = Path(__file__).resolve().parent / "out"
DST = OUT / "meuse"
LOCAL_NAME = {"Luik": "Liège", "Wezet": "Visé", "Limburg": "Limbourg", "Bitsingen": "Bassenge",  # as build_meuse.py
              "Saint-Nicolas (Luik)": "Saint-Nicolas", "Hoei": "Huy", "Namen": "Namur", "Borgworm": "Waremme"}
UNDER_DETECTED = {"Pepinster", "Verviers", "Chaudfontaine", "Trooz", "Liège"}  # as build_regions.py
LEVELS = [(7, "Act first"), (4, "Prepare"), (1, "Watch"), (0, "Low")]
pts = lambda v, steps: sum(v >= s for s in steps)
# river that floods each town in outputs/data/app_towns.csv (worst variant); its gauge is that river's nearest point.
# Close calls: Liège lies at the Vesdre/Ourthe/Meuse confluence, so Meuse · Liège (just downstream) carries all three;
# Bitsingen (Geer) has no Geer point and the Geer meets the Meuse at Maastricht; Stolberg (Vicht) drains to the Inde;
# Kelmis' Geul point is ~15 km downstream.
TOWN_RIVER = {m: river for river, ms in {
    "Ahr": ["Bad Neuenahr-Ahrweiler, Stadt (DE)", "Sinzig, Stadt (DE)", "Dernau (DE)", "Altenahr (DE)", "Rech (DE)",
            "Schuld (DE)", "Ahrbrück (DE)", "Mayschoß (DE)", "Insul (DE)", "Hönningen (DE)", "Müsch (DE)",
            "Fuchshofen (DE)", "Blankenheim (DE)", "Antweiler (DE)", "Dümpelfeld (DE)", "Wershofen (DE)"],
    "Vesdre": ["Verviers (BE)", "Pepinster (BE)", "Chaudfontaine (BE)", "Trooz (BE)", "Limburg (BE)", "Dison (BE)",
               "Olne (BE)"],
    "Hoëgne": ["Theux (BE)"],
    "Ourthe": ["Esneux (BE)", "Neupré (BE)", "Hamoir (BE)", "Hotton (BE)", "La Roche-en-Ardenne (BE)", "Durbuy (BE)",
               "Rendeux (BE)"],
    "Lesse": ["Rochefort (BE)"],
    "Meuse": ["Luik (BE)", "Wezet (BE)", "Oupeye (BE)", "Maastricht (NL)", "Bitsingen (BE)", "Kinrooi (BE)", "Riemst (BE)",
              "Maasgouw (NL)", "Maasmechelen (BE)", "Venlo (NL)", "Roermond (NL)", "Peel en Maas (NL)",
              "Horst aan de Maas (NL)", "Leudal (NL)"],
    "Rur": ["Wassenberg, Stadt (DE)", "Heinsberg, Stadt (DE)", "Roerdalen (NL)"],
    "Inde": ["Eschweiler, Stadt (DE)", "Inden (DE)", "Stolberg (Rhld.), Kupferstadt (DE)"],
    "Erft": ["Erftstadt, Stadt (DE)", "Euskirchen, Stadt (DE)", "Bad Münstereifel, Stadt (DE)", "Weilerswist (DE)",
             "Kerpen, Kolpingstadt (DE)"],
    "Urft": ["Schleiden, Stadt (DE)", "Kall (DE)"],
    "Geul": ["Kelmis (BE)"]}.items() for m in ms}


def km(lon0, lat0, lon, lat):
    p0, p, dl = np.radians(lat0), np.radians(lat), np.radians(np.asarray(lon) - lon0)
    return 6371 * np.arccos(np.clip(np.sin(p0) * np.sin(p) + np.cos(p0) * np.cos(p) * np.cos(dl), -1, 1))


def replay():
    """GloFAS river flow 10–20 July 2021 at every forecast point (the "forecast" the home page replays), and each
    town's river point."""
    r = forecast._get(forecast.FLOOD, forecast.GAUGES, retries=5, daily="river_discharge", start_date="2021-07-10",
                      end_date="2021-07-20")
    (DST / "replay_2021.json").write_text(json.dumps({k: dict(zip(v["daily"]["time"], v["daily"]["river_discharge"]))
                                                      for k, v in r.items()}, indent=1))
    t = pd.read_csv(OUT.parent.parent / "outputs" / "data" / "app_towns.csv").query("variant == 'worst'")
    rows = []
    for m, area, lon, lat in t[["municipality", "area", "lon", "lat"]].itertuples(index=False):
        river = TOWN_RIVER.get(m)
        g = {k: v for k, v in forecast.GAUGES.items() if k.split(" · ")[0] == river}
        d = {k: km(lon, lat, v[1], v[0]) for k, v in g.items()}
        best = min(d, key=d.get) if d else None
        rows.append({"municipality": m, "area": area, "gauge": best, "km": round(d[best], 1) if best else None,
                     "river": river})
    out = pd.DataFrame(rows)
    out.to_csv(OUT.parent.parent / "outputs" / "data" / "town_gauge.csv", index=False)
    if out.gauge.isna().any():
        print("no river point:", out[out.gauge.isna()].municipality.tolist())


if "--replay" in sys.argv[1:]:
    replay()
    sys.exit()

com = pd.read_parquet(DST / "communes.parquet")
zone, obs = com[com.lens == "rp100"].set_index("lau_id"), com[com.lens == "obs"].set_index("lau_id")
sites = pd.read_parquet(DST / "sites.parquet")
care, dry = sites[sites.role == "evacuate"], sites[sites.role == "shelter"]

lau = gpd.read_parquet(OUT / "raw" / "LAU_RG_01M_2021_4326.parquet").rename_geometry("geometry").set_crs(4326, allow_override=True)
lau = lau[lau.GISCO_ID.isin(zone.index.union(obs.index))].rename(
    columns={"GISCO_ID": "lau_id", "LAU_NAME": "commune", "CNTR_CODE": "country", "POP_2021": "population"})
p = lau[["lau_id", "commune", "country", "population", "geometry"]].reset_index(drop=True)
p["commune"] = p.commune.replace(LOCAL_NAME)
p["people"] = p.lau_id.map(zone.residents).fillna(0).round()
p["people_2021"] = p.lau_id.map(obs.residents).fillna(0).round()
p["share"] = (p.people / p.population.where(p.population > 0)).fillna(0).clip(upper=1)
p["missed"] = p.commune.isin(UNDER_DETECTED)
p["hit_2021"] = (p.people_2021 > 0) | p.missed
p["care"] = p.lau_id.map(care.groupby("lau_id").size()).fillna(0).astype(int)

# centre of the homes at risk (100-year zone, else 2021 water) for distances to dry sites and rivers
ctr = zone[["lon", "lat"]].combine_first(obs[["lon", "lat"]])
p["lon"], p["lat"] = p.lau_id.map(ctr.lon), p.lau_id.map(ctr.lat)
p["dry_5km"] = [int((km(x, y, dry.lon, dry.lat) <= 5).sum()) for x, y in zip(p.lon, p.lat)]
p["per_site"] = (p.people / p.dry_5km.where(p.dry_5km > 0)).round()
p.loc[p.country == "DE", ["dry_5km", "per_site"]] = np.nan  # no OSM sites on the German side: unknown, not zero

p["pts_people"] = p.people.map(lambda v: pts(v, (50, 500, 2000, 10000)))
p["pts_share"] = p.share.map(lambda v: pts(v, (.05, .2)))
p["pts_2021"] = p.hit_2021 * 2
p["pts_care"] = p.care.map(lambda v: pts(v, (1, 3)))
p["score"] = p[["pts_people", "pts_share", "pts_2021", "pts_care"]].sum(axis=1)
p["level"] = p.score.map(lambda s: next(lab for lo, lab in LEVELS if s >= lo))

p["geometry"] = p.geometry.simplify(0.0005)
p.sort_values(["score", "people"], ascending=False).to_file(DST / "priority.geojson")
print(p.groupby("level").size().to_dict())
print(p.sort_values(["score", "people"], ascending=False)[["commune", "country", "people", "share", "hit_2021", "care",
                                                            "score", "level", "dry_5km"]].head(15).to_string())

replay()
