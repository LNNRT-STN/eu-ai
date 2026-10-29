"""Shared data, outlook and UI pieces for dashboard.py and the views/ pages."""
import json, math
from html import escape
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

import forecast

OUT = Path(__file__).resolve().parent / "out"
DST = OUT / "meuse"  # live-outlook files only: river reference flows and the July 2021 river replay
DATA = Path(__file__).resolve().parents[1] / "outputs" / "data"  # cleaned exposure and shelter data (its README.md)
COUNTRY = {"BE": "Belgium", "NL": "Netherlands", "DE": "Germany"}
# two flood maps per area; vesdre has no satellite polygons, so its two are EFAS 100-year (main) and 500-year (worst)
VARIANT = {"worst": "July 2021 · all satellite passes", "main": "July 2021 · first pass only"}
REACH = {"low": "1 km walk · 5 m² · 40 % usable", "central": "1.5 km walk · 4 m² · 50 % usable",
         "high": "2.5 km walk · 3 m² · 60 % usable"}
MISSED = "#8f8c84"  # flooded in reality, missed by the satellite: never draw these as "not reached"
SHELTER, EVACUATE, OFFLINE = "#248a3d", "#d70015", "#aeaeb2"
PEOPLE = "#eb6834"  # residents in the water, one orange everywhere
# shelter sites by building type; hues kept clear of water blue, risk orange, evacuate red and trip green
KIND = {"School": "#0e7c86", "Sports hall": "#c28a00", "Town hall / civic": "#4a4e69"}
CAT = {"school": "School", "sports hall": "Sports hall", "civic": "Town hall / civic"}
# shelter gap per municipality (q4_ranking `why`): label, colour, what the commune does now
GAP = {"No shelter in reach": ("#d70015", "Pre-agree sites further away, or plan buses to a neighbouring commune."),
       "Shelters full": ("#eb6834", "Open more or larger sites in walking reach, or share them with the next commune."),
       "Covered": ("#d9d6cf", "Shelters in walking reach can take everyone in the flood.")}
WHY = {"shelters too far": "No shelter in reach", "shelters full": "Shelters full", "-": "Covered"}
# how fresh each source is, shown under every panel
AS_OF = {"obs": "Copernicus EMS satellite map, 15–20 Jul 2021 · GHS-OBAT · GHS-POP 2020",
         "model": "Vesdre: EFAS 100-/500-year zone (model)", "osm": "OpenStreetMap sites, extracted 29 Oct 2026",
         "replay": "GloFAS river flow, 12–20 Jul 2021 (model)"}
rgb = lambda h, a=255: [int(h[i:i + 2], 16) for i in (1, 3, 5)] + [a]
_lum = lambda h: sum(w * (c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4)
                     for w, c in zip((.2126, .7152, .0722), (v / 255 for v in rgb(h)[:3])))
ink = lambda h: "#fff" if _lum(h) < .18 else "#1d1d1f"  # text on a filled colour: whichever contrasts more
chip = lambda lab, h: f"<span class='pill' style='background:{h};color:{ink(h)}'>{lab}</span>"
WATER = "rgba(0,113,227,.35)"  # observed 2021 water as drawn on the maps
MODEL = "rgba(143,140,132,.4)"  # modelled water (Vesdre, missed by the satellite) in the MISSED grey
fmt = lambda n: f"{n:,.0f}"
MAX_FLOOR = 20_000  # m²: above this OSM merged a whole campus or tagged a race circuit; counted as this much
about = lambda n: fmt(round(n, -2) if n >= 1000 else round(n, -1) if n >= 100 else n)  # residents are an order of magnitude

CSS = """<style>
:root{--label:#1d1d1f;--label2:#6e6e73;--label3:#8e8e93;--sep:#e3e3e8;--group:#fff;--bg:#f2f2f7;--tint:#0071e3}
.block-container{padding:4.25rem 2.5rem 4rem;max-width:1320px}
[data-testid=stSidebar]{border-right:1px solid var(--sep)}
[data-testid=stSidebarNav] a{border-radius:8px;padding:.35rem .6rem}
[data-testid=stSidebarNav] a[aria-current=page]{background:rgba(0,113,227,.1)}
[data-testid=stSidebarNav] a[aria-current=page] span{color:var(--tint)!important;font-weight:600}
[data-testid=stNavSectionHeader]{font-size:.75rem;color:var(--label3);font-weight:600;text-transform:none;letter-spacing:0}
::selection{background:rgba(0,113,227,.2)}
*:focus-visible{outline:2px solid var(--tint)!important;outline-offset:2px}
.pg h1{font-size:2.125rem;font-weight:700;letter-spacing:-.022em;line-height:1.2;margin:0;padding:0;color:var(--label);overflow-wrap:anywhere}
.pg p{color:var(--label2);font-size:1rem;margin:.4rem 0 0;max-width:72ch;line-height:1.45}
.banner{display:flex;gap:.9rem;align-items:flex-start;border-radius:14px;padding:1.1rem 1.25rem;
  background:color-mix(in srgb,var(--c,#fff) 9%,#fff);
  box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c,#fff) 30%,transparent),0 1px 2px rgba(0,0,0,.04),0 4px 16px rgba(0,0,0,.04)}
.banner .dot{flex:none;width:.85rem;height:.85rem;border-radius:50%;margin-top:.42rem;background:var(--c)}
.banner h2{font-size:1.3rem;font-weight:650;letter-spacing:-.012em;margin:0;padding:0;line-height:1.3;color:var(--label)}
.banner p{margin:.3rem 0 0;color:var(--label2);font-size:.95rem;line-height:1.45;max-width:90ch}
.banner small{display:block;margin-top:.5rem;color:var(--label3);font-size:.8rem}
.gh{font-size:.8rem;font-weight:600;color:var(--label2);margin:0 0 -.4rem .9rem}
.gh+.group{margin-top:.85rem}
.group{background:var(--group);border-radius:12px;overflow:hidden}
.group .row{display:flex;align-items:center;gap:.85rem;padding:.7rem 1rem;min-height:2.75rem;position:relative}
.group .row+.row::before{content:"";position:absolute;top:0;left:1rem;right:0;border-top:1px solid var(--sep)}
.group .row .t{flex:1;min-width:0;color:var(--label);font-size:.95rem}
.group .row .t b{font-weight:600}
.group .row .t span{display:block;color:var(--label2);font-size:.85rem;margin-top:.1rem;line-height:1.4}
.group .row .v{color:var(--label2);font-variant-numeric:tabular-nums;font-size:.95rem;text-align:right}
.group .row .v b{color:var(--label);font-weight:600}
.ico{flex:none;width:2rem;height:2rem;border-radius:8px;display:grid;place-items:center;color:#fff}
.ms{font-family:'Material Symbols Rounded';font-size:1.2rem;line-height:1;font-weight:400;font-variation-settings:'FILL' 1}
.chev .ms{font-size:1.4rem}
.chev{flex:none;color:#c7c7cc}
.foot{color:var(--label3);font-size:.8rem;margin:.5rem 0 0 1rem;line-height:1.45}
.legend{display:flex;flex-wrap:wrap;gap:.3rem 1rem;font-size:.8rem;color:var(--label2);margin:.6rem .25rem 0}
.legend span{display:inline-flex;align-items:center;gap:.4rem}
.legend i{width:.75rem;height:.75rem;border-radius:3px;display:inline-block}
.legend b{font-weight:600;color:var(--label)}
/* a whole step row is one link: the page link is stretched over the drawn row */
[class*=st-key-step-]{position:relative;gap:0}
[class*=st-key-step-] [data-testid=stPageLink]{position:absolute;inset:0;margin:0}
[class*=st-key-step-] [data-testid=stPageLink] a{height:100%;border-radius:0;padding:0;background:none!important}
[class*=st-key-step-] [data-testid=stPageLink] a>*{opacity:0}
[class*=st-key-step-]:hover .row{background:#f7f7fa}
[class*=st-key-steps]{background:var(--group);border-radius:12px;overflow:hidden;gap:0;padding-bottom:.15rem}
[class*=st-key-steps] .group{border-radius:0}
[class*=st-key-step-]+[class*=st-key-step-] .row::before{content:"";position:absolute;top:0;left:3.85rem;right:0;border-top:1px solid var(--sep)}
[data-testid=stDataFrame]{border-radius:12px;overflow:hidden}
[data-testid=stExpander] details{background:var(--group);border-radius:12px;border-color:transparent}
[data-testid=stTabs] [data-baseweb=tab-list]{gap:1.25rem}
[data-testid=stDeckGlJsonChart]{border-radius:12px;overflow:hidden}
/* Streamlit escapes tooltip values, so tips are plain text: line breaks via pre-line, first line is the title */
.deck-tooltip::first-line{font-weight:600}
.facts{display:grid;grid-template-columns:repeat(4,1fr);background:var(--group);border-radius:12px}
.facts>div{padding:.95rem 1.1rem;position:relative}
.facts>div+div::before{content:"";position:absolute;left:0;top:1rem;bottom:1rem;border-left:1px solid var(--sep)}
.facts b{display:block;font-size:1.75rem;font-weight:650;letter-spacing:-.02em;line-height:1.1;color:var(--label);
  font-variant-numeric:tabular-nums}
.facts span{display:block;margin-top:.3rem;color:var(--label2);font-size:.88rem;line-height:1.4}
.facts span strong{color:var(--label);font-weight:600}
.facts b i{display:inline-block;width:.7rem;height:.7rem;border-radius:3px;margin-right:.5rem;vertical-align:.2em}
.asof{color:var(--label3);font-size:.75rem;margin:.45rem 0 0 1rem}
.pill{display:inline-block;padding:.1rem .55rem;border-radius:99px;font-size:.8rem;font-weight:600;color:#fff;vertical-align:.1em}
.group .row .t .pill{display:inline-block;margin:0 0 .25rem}
.score{font-size:2.5rem;font-weight:650;letter-spacing:-.02em;line-height:1;font-variant-numeric:tabular-nums;color:var(--label)}
.score small{font-size:1rem;color:var(--label3);font-weight:500}
@media (max-width:900px){.facts{grid-template-columns:repeat(2,1fr)}.facts>div:nth-child(3)::before{display:none}}
@media (max-width:640px){.block-container{padding:3.75rem 1rem 3rem}.pg h1{font-size:1.75rem}.banner{padding:1rem}}
</style>"""

# Material Symbols Rounded, the font Streamlit already loads for the sidebar icons (st.html strips inline SVG)
_I = {"waves": "water", "house": "home_health", "cross": "local_hospital", "users": "groups", "chev": "chevron_right"}
icon = lambda n: f"<span class='ms' aria-hidden='true'>{_I[n]}</span>"


def style():
    st.html(CSS)


def header(title, sub=""):
    st.html(f"<header class='pg'><h1>{title}</h1>" + (f"<p>{sub}</p>" if sub else "") + "</header>")


def group(rows, title="", foot=""):
    """HIG inset grouped list: rows of (label, value) or (label, sub, value)."""
    html = "".join(f"<div class='row'><div class='t'>{r[0]}" + (f"<span>{r[1]}</span>" if len(r) == 3 else "")
                   + f"</div><div class='v'>{r[-1]}</div></div>" for r in rows)
    st.html((f"<div class='gh'>{title}</div>" if title else "") + f"<div class='group'>{html}</div>"
            + (f"<p class='foot'>{foot}</p>" if foot else ""))


def steps(items, title=""):
    """Tappable rows (icon, colour, title, subtitle, page): each row is one link to its page."""
    if title:
        st.html(f"<div class='gh'>{title}</div>")
    with st.container(key="steps"):
        for i, (ic, color, t, sub, page) in enumerate(items):
            with st.container(key=f"step-{i}"):
                st.html(f"<div class='group'><div class='row'><div class='ico' style='background:{color}'>{icon(ic)}</div>"
                        f"<div class='t'><b>{t}</b><span>{sub}</span></div><div class='chev'>"
                        f"{icon('chev')}</div></div></div>")
                st.page_link(page, label=t)


country = lambda m: m.str[-3:-1]  # "Pepinster (BE)" → "BE"
plain = lambda m: m.str.replace(r" \(..\)$", "", regex=True)


@st.cache_data
def load():
    """Cleaned data (outputs/data): areas, towns per flood map, ranking, care sites, shelters, quality checks."""
    csv = lambda n: pd.read_csv(DATA / f"{n}.csv", encoding="utf-8-sig")
    areas, towns, rank, sites = csv("area_summary"), csv("app_towns"), csv("q4_ranking"), csv("critical_sites")
    towns["country"], rank["country"], sites["country"] = country(towns.municipality), country(rank.municipality), \
        country(sites.municipality)
    towns["modelled"] = towns.source == "modelled"
    rank["modelled"] = rank.source.str.startswith("MODELLED")
    rank["gap"] = rank.why.map(WHY)
    sites = sites[sites.share_of_site_flooded >= .05]  # below 5 % the site only touches the water's edge
    sh = gpd.read_file(DATA / "shelters.geojson")
    sh = sh[~sh.geometry.duplicated()]  # a site in two overlapping study areas comes twice
    sh["capped"] = sh.gfa > MAX_FLOOR
    sh["gfa"] = sh.gfa.clip(upper=MAX_FLOOR)
    sh["capacity_central"] = (sh.gfa * .5 / 4).round()  # floor × 50 % usable ÷ 4 m² per person, as in the README
    pt = sh.geometry.to_crs(3035).centroid.to_crs(4326)  # a few campuses are polygons
    sh = pd.DataFrame(sh.drop(columns="geometry")).assign(
        lon=pt.x.round(5), lat=pt.y.round(5), type=sh.cat.map(CAT), name=sh["name"].fillna("(no name in OSM)"),
        country=country(sh.muni.fillna("(??)")))
    js = lambda n: json.loads((DATA / f"{n}.json").read_text())
    return dict(areas=areas, towns=towns, rank=rank, sites=sites, shelters=sh, head=js("q4_headline"),
                qc=js("qc_and_validation"), dq=csv("dq_report"))


@st.cache_data
def flood(variant):
    """Flood extent of every area for one map, observed and modelled told apart by colour."""
    feats = []
    for a in ("ahr", "erftstadt", "eschweiler", "euskirchen", "liege", "rochefort", "schleiden", "venlo", "vesdre",
              "wassenberg"):
        for f in json.loads((DATA / f"flood_{a}_{variant}.geojson").read_text())["features"]:
            m = a == "vesdre"
            feats.append({**f, "properties": {"area": a, "fill": rgb(MISSED, 100) if m else rgb("#0071e3", 85),
                                              "line": rgb(MISSED, 190) if m else rgb("#0071e3", 150)}})
    fc = {"type": "FeatureCollection", "features": feats}
    return fc, list(gpd.GeoDataFrame.from_features(feats).total_bounds)


@st.cache_data
def outlines():
    """GISCO LAU 2021 outline, residents and size of every municipality, by name (build_outlines.py)."""
    return {f["properties"]["municipality"]: f for f in
            json.loads((DATA / "municipality_outlines.geojson").read_text())["features"]}


@st.cache_data
def load_replay():
    """GloFAS daily flows at the river points, 10–20 July 2021 (build_priority.py)."""
    r = pd.DataFrame(json.loads((DST / "replay_2021.json").read_text()))
    return r.set_axis(pd.to_datetime(r.index))


@st.cache_data(ttl=3 * 3600, show_spinner="Fetching river and rain forecasts…")
def _outlook():
    return *forecast.rivers(), forecast.rain(), pd.Timestamp.now(tz="Europe/Brussels")


def outlook():
    """(gauges, series, rain, fetched_at, error); gauges is None when offline or the API is down."""
    try:
        return (*_outlook(), None)
    except Exception as e:
        return None, None, None, None, str(e)


def status(gauges, rain, err):
    """One verdict for the whole basin: (colour, headline, detail, worst gauge row or None)."""
    if gauges is None:
        return OFFLINE, "River outlook unavailable", (f"Open-Meteo could not be reached ({escape(err)}). Exposure, "
                                                      "care sites and shelters below still work."), None
    w = gauges.sort_values(["level", "pct_2021"], ascending=False).iloc[0]
    worst = gauges.sort_values(["level_worst", "worst"], ascending=False).iloc[0]
    head = ("No river flood expected in the next 30 days" if w.level == 0 else
            f"{forecast.LEVELS[w.level][0]} expected on the {w.gauge.split(' · ')[0]} at {w.gauge.split(' · ')[1]}")
    detail = (f"Highest point: {w.gauge}, {fmt(w.peak)} m³/s on {w.peak_day:%a %d %b}, "
              f"{w.pct_2021:.0%} of its July 2021 peak. Rain in the headwaters: up to {rain.max_2day.max():.0f} mm in 2 days.")
    if worst.level_worst > w.level:
        detail += f" The wettest forecast run reaches “{forecast.LEVELS[worst.level_worst][0].lower()}” at {worst.gauge}."
    return forecast.LEVELS[w.level][1] if w.level else SHELTER, head, detail, w


def banner(color, head, detail, note=True):
    st.html(f"<div class='banner' style='--c:{color}'><i class='dot'></i><div>"
            f"<h2>{head}</h2><p>{detail}</p>"
            + ("<small>A heads-up from the GloFAS model, not an official warning. Warnings: SPW (hydrometrie.wallonie.be), "
               "Rijkswaterstaat, German state flood centres.</small>" if note else "") + "</div></div>")


def km(lon0, lat0, lon, lat):
    """Great-circle distance in km from one point to arrays of points."""
    p0, p, dl = np.radians(lat0), np.radians(lat), np.radians(np.asarray(lon) - lon0)
    return 6371 * np.arccos(np.clip(np.sin(p0) * np.sin(p) + np.cos(p0) * np.cos(p) * np.cos(dl), -1, 1))


def view(bbox, focus=None, zoom=11.5):
    if focus is not None:
        return pdk.ViewState(longitude=focus[0], latitude=focus[1], zoom=zoom)
    x0, y0, x1, y1 = bbox
    zoom = min(math.log2(900 * 360 / (512 * (x1 - x0))), math.log2(620 * 360 / (512 * (y1 - y0) * 1.55))) - 0.2
    return pdk.ViewState(longitude=(x0 + x1) / 2, latitude=(y0 + y1) / 2, zoom=zoom)


def water(variant="worst"):
    fc, _ = flood(variant)
    return [pdk.Layer("GeoJsonLayer", fc, filled=True, stroked=True, get_fill_color="properties.fill",
                      get_line_color="properties.line", line_width_min_pixels=1)]


def bbox(variant="worst"):
    return flood(variant)[1]


def points(df, color, radius=6, line=2):
    return pdk.Layer("ScatterplotLayer", df, get_position=["lon", "lat"], get_fill_color=color,
                     get_line_color=[255, 255, 255], line_width_min_pixels=line, stroked=True, get_radius=radius,
                     radius_units="'pixels'", pickable=True)


def towns(df, size, color, scale=14):
    """Municipalities as circles at their centroid, area ∝ `size` (no commune outlines in the cleaned data)."""
    big = max(df[size].max(), 1)
    return pdk.Layer("ScatterplotLayer", df.assign(r=3 + scale * np.sqrt(df[size] / big)), get_position=["lon", "lat"],
                     get_fill_color=color, get_radius="r", radius_units="'pixels'", stroked=True,
                     get_line_color=[255, 255, 255], line_width_min_pixels=1, pickable=True, auto_highlight=True,
                     id=f"towns-{size}")


def regions(df, fill, sel=None):
    """Municipalities as their outline, one feature per row of `df` (every column kept for tooltips and clicks).
    `sel`: the selected municipality, drawn with a heavy outline."""
    shapes = outlines()
    feats = [{"type": "Feature", "geometry": shapes[r["municipality"]]["geometry"],
              "properties": {**r, "line": [29, 29, 31, 255 if r["municipality"] == sel else 110],
                             "w": 3 if r["municipality"] == sel else 1}}
             for r in json.loads(df.to_json(orient="records")) if r["municipality"] in shapes]
    return pdk.Layer("GeoJsonLayer", {"type": "FeatureCollection", "features": feats}, filled=True, stroked=True,
                     get_fill_color=f"properties.{fill}", get_line_color="properties.line", get_line_width="properties.w",
                     line_width_units="'pixels'", pickable=True, auto_highlight=True,
                     highlight_color=[29, 29, 31, 45], id=f"regions-{fill}")


def deck(layers, v, height=600, **kw):
    tip = {"html": "{tip}", "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px",
                                       "padding": "6px 9px", "borderRadius": "8px",
                                       "whiteSpace": "pre-line"}}
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=v, map_style=pdk.map_styles.CARTO_LIGHT, tooltip=tip),
                    height=height, **kw)


def facts(items, asof=""):
    """One white strip of headline numbers, each read as a sentence: (number, sentence[, map colour, round]).
    The colour repeats the number's mark on the map, round for points, square for areas."""
    key = lambda c=None, round_=False: (f"<i style='background:{c}" + (";border-radius:50%" if round_ else "") + "'></i>"
                                        if c else "")
    st.html("<div class='facts'>" + "".join(f"<div><b>{key(*k)}{n}</b><span>{t}</span></div>" for n, t, *k in items)
            + "</div>"
            + (f"<p class='asof'>{asof}</p>" if asof else ""))


def asof(*keys):
    st.html("<p class='asof'>Source · " + " · ".join(AS_OF[k] for k in keys) + "</p>")


def legend(*parts):
    st.html("".join(f"<div class='legend'>{p}</div>" for p in parts))


def paint(df, col, colors):
    """Styler that fills one table column with each value's status colour, label kept as text."""
    return df.style.map(lambda v: f"background-color:{colors[v]};color:{ink(colors[v])}" if v in colors else "",
                        subset=[col])


swatch = lambda h, lab, round_=False: (f"<span><i style='background:{h}" + (";border-radius:50%" if round_ else "")
                                      + f"'></i>{lab}</span>")
