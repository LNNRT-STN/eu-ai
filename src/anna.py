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
