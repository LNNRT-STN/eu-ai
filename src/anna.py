"""Loads the notebooks/ pipeline outputs (outputs/data/) for the First action page: every mapped area, Ahr included,
with shelter capacity per town. Run notebooks/pipeline.py, dq_report.py and q4_ranking.py to rebuild them."""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "outputs" / "data"
VARIANT = {"worst": "All satellite passes", "main": "First pass only"}
AREA = {"ahr": "Ahr", "vesdre": "Vesdre", "liege": "Liège area", "rochefort": "Rochefort area", "venlo": "Venlo area",
        "eschweiler": "Eschweiler", "wassenberg": "Wassenberg", "schleiden": "Schleiden area",
        "euskirchen": "Euskirchen area", "erftstadt": "Erftstadt"}
MODELLED = {"vesdre"}
LOCAL = {"Luik": "Liège", "Limburg": "Limbourg"}  # GISCO lists some Walloon communes under their Dutch name
# chart colours from core's palette, validated together (dataviz validator: CVD 12.4, normal-vision 18.0, contrast >= 3:1)
SHELTERED, FULL, TOO_FAR = "#8e8e93", "#eb6834", "#7a2c10"
# official 2021 figures, verified at source (ai_log.md entries 8 and 11)
OFFICIAL = {"ahr": ("over 9,000 buildings destroyed or heavily damaged", "bpb, 10 Jul 2023"),
            "wallonia": ("about 48,000 buildings hit, 45,000 of them homes", "Wallonia government, Jul 2022"),
            "venlo": ("10,700 residents evacuated as a precaution", "Venlo municipality, 16 Jul 2021, via Hart van Nederland")}


def town(name):
    """'Bad Neuenahr-Ahrweiler, Stadt (DE)' -> 'Bad Neuenahr-Ahrweiler'."""
    n = name.rsplit(" (", 1)[0].replace(", Stadt", "")
    return LOCAL.get(n, n)


def load():
    """Cached, but keyed on the newest file time, so rebuilding outputs/data/ refreshes a running app."""
    return _load(max(f.stat().st_mtime for f in DATA.glob("*.*")))


@st.cache_data
def _load(_stamp):
    head = json.loads((DATA / "q4_headline.json").read_text())
    towns = pd.read_csv(DATA / "app_towns.csv")
    towns["name"] = towns.municipality.map(town)
    towns["label"] = towns.name + towns.area.map(lambda a: " (modelled)" if a in MODELLED else "")
    crit = pd.read_csv(DATA / "critical_sites.csv")
    crit["town"] = crit.municipality.map(town)
    shel = gpd.read_file(DATA / "shelters.geojson")
    pt = shel.geometry.representative_point()
    shel = pd.DataFrame(shel.drop(columns="geometry").assign(lon=pt.x, lat=pt.y))
    shel["town"] = shel.muni.map(town)
    flood = {(a, v): json.loads((DATA / f"flood_{a}_{v}.geojson").read_text()) for a in AREA for v in VARIANT}
    summary = pd.read_csv(DATA / "area_summary.csv")
    qc = json.loads((DATA / "qc_and_validation.json").read_text())
    return head, towns, crit, shel, flood, summary, qc


def load_moves():
    """Where people go: receiving hospitals / care homes per flooded site, and the 10 km bus plan per town."""
    return _load_moves(max(f.stat().st_mtime for f in DATA.glob("*.*")))


@st.cache_data
def _load_moves(_stamp):
    recv = pd.read_csv(DATA / "receiving_sites.csv")
    bus = pd.read_csv(DATA / "bus_plan.csv")
    bus["town"] = bus.municipality.map(town)
    return recv, bus


ROAD = 1.3  # road distance / straight line, measured 1.2-1.4 in notebooks/evac_sim.py


def shelter_address(r):
    """'Ahrstraße 5, 53506 Ahrbrück' from a row of shelter_addresses.csv; '' when OSM has no address within 100 m."""
    if not isinstance(r.get("street"), str):
        return ""
    place = " ".join(x for x in (r.get("postcode"), r.get("city")) if isinstance(x, str))
    return f"{r['street']} {r['housenumber']}" + (f", {place}" if place else "")


@st.cache_data
def plan_shelters():
    """Per town, the shelters its people go to in the 10 km plan, each with its street address
    (notebooks/shelter_addresses.py)."""
    bus = load_moves()[1]
    p = bus.groupby(["municipality", "shelter", "cat", "s_lon", "s_lat"], as_index=False).people.sum()
    p = p[p.people >= .5]
    ad = pd.read_csv(DATA / "shelter_addresses.csv", dtype=str)
    ad[["s_lon", "s_lat"]] = ad[["s_lon", "s_lat"]].astype(float)
    p = p.merge(ad, on=["shelter", "s_lon", "s_lat"], how="left")
    p["address"] = [shelter_address(r) for r in p.to_dict("records")]
    # OSM sites with no name are listed as "Unnamed school": call them by what they are
    p["label"] = p.shelter.where(~p.shelter.str.startswith("Unnamed "),
                                 p.shelter.str.removeprefix("Unnamed ").str.capitalize())
    return p


def destinations(muni, homes):
    """For each home (lon, lat) of one town: its nearest plan shelter, that shelter's address and the road km."""
    import numpy as np
    p = plan_shelters().query("municipality == @muni").reset_index(drop=True)
    if p.empty:
        return homes.assign(go="", go_address="", go_km=np.nan)
    lat0 = np.radians(homes.lat.values)[:, None]
    dx = (homes.lon.values[:, None] - p.s_lon.values[None]) * np.cos(lat0) * 111.32
    dy = (homes.lat.values[:, None] - p.s_lat.values[None]) * 110.57
    d = np.hypot(dx, dy) * ROAD
    i = d.argmin(1)
    return homes.assign(go=p.label.values[i], go_address=p.address.values[i], go_km=d[np.arange(len(i)), i].round(1),
                        go_lon=p.s_lon.values[i], go_lat=p.s_lat.values[i], go_cat=p["cat"].values[i])
