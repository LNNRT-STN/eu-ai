"""Test page for the regionmap component (not in the nav). Run alone:
streamlit run src/views/_regionmap_demo.py --server.port 8601
A fake river level (slider, or auto replay) gives every town a status; the map must update in place every 2 s."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shapely  # noqa: E402
import streamlit as st  # noqa: E402
from shapely.geometry import MultiPoint, mapping, shape  # noqa: E402

import anna  # noqa: E402
from regionmap import ATTRIBUTION, region_map  # noqa: E402


@st.cache_data
def build():
    _, towns, _, _, flood, *_ = anna.load()
    w = towns[towns.variant == "worst"].reset_index(drop=True)
    feats = []
    for area, g in w.groupby("area"):  # demo clip: split each area's water between its towns (Voronoi cells)
        water = shapely.make_valid(shape(flood[(area, "worst")]["features"][0]["geometry"]))
        g = g.drop_duplicates("municipality")
        if len(g) == 1:
            feats.append({"type": "Feature", "geometry": mapping(water), "properties": {"municipality": g.municipality.iloc[0]}})
            continue
        pts = MultiPoint(list(zip(g.lon, g.lat)))
        cells = shapely.voronoi_polygons(pts, extend_to=water.envelope.buffer(1))
        for cell in cells.geoms:
            r = g[[cell.contains(shapely.Point(x, y)) for x, y in zip(g.lon, g.lat)]]
            part = water.intersection(cell).simplify(0.0001)
            if len(r) and not part.is_empty:
                feats.append({"type": "Feature", "geometry": mapping(part), "properties": {"municipality": r.municipality.iloc[0]}})
    rank = w.people.rank(pct=True)
    return w, rank, {"type": "FeatureCollection", "features": feats}


w, rank, flood = build()
CLOSURES = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[5.790, 50.5705], [5.7985, 50.5715], [5.806, 50.5735]]},
     "properties": {"name": "N61 Pepinster"}},
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [7.1150, 50.5435]}, "properties": {"name": "B266 Ahrweiler"}}]}

st.title("Region map test")
auto = st.toggle("Auto replay (level +7 every 2 s)", value=True)
st.slider("Fake river level", 0, 100, 40, key="level")


def status(level, r):
    h = (1 - r) * 60  # bigger towns react to lower levels
    return "evacuate" if level >= h + 40 else "warn" if level >= h + 20 else "watch" if level >= h else "none"


@st.fragment(run_every=2)
def live():
    if auto:
        st.session_state.tick = st.session_state.get("tick", -1) + 1
    level = (st.session_state.level + 7 * st.session_state.get("tick", 0)) % 101 if auto else st.session_state.level
    towns = [dict(municipality=t.municipality, label=t.label, lon=float(t.lon), lat=float(t.lat),
                  status=status(level, r), people=int(t.people), people_expected=None,
                  modelled=t.area in anna.MODELLED) for t, r in zip(w.itertuples(), rank)]
    st.caption(f"Level {level}: " + ", ".join(f"{s} {sum(t['status'] == s for t in towns)}"
                                             for s in ("evacuate", "warn", "watch", "none")))
    sel = region_map(dict(towns=towns, flood=flood, closures=CLOSURES,
                          selected=st.session_state.get("pick")), key="regionmap_demo", height=560)
    st.write("Returned:", sel)


live()
names = [None] + sorted(w.municipality.unique())
st.selectbox("Selected (Python → map)", names, key="pick", format_func=lambda m: "Region overview" if m is None else m)
st.caption(ATTRIBUTION)
