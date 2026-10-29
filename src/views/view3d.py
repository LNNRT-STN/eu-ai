"""Valley in 3D: one town's July 2021 water draped on satellite terrain, with the homes, dry shelters, evacuation roads,
rail and care sites in it, and a day-by-day river replay. MapLibre GL JS (open source, no token) in a component;
elevation: AWS Terrain Tiles (Terrarium); imagery: EOX Sentinel-2 cloudless or Esri World Imagery.
Numbers: outputs/data/ (app_towns, buildings_3d, bus_plan, critical_sites, evac_edges, infra_rail) and the GloFAS
replay (core.load_replay). The water opacity on the timeline is a visual cue, not a flood simulation."""
import json
import math

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import anna
import core
import forecast
from core import about, fmt

V = "worst"
head, towns, crit, shel, flood, *_ = anna.load()
recv, bus = anna.load_moves()
B3D = pd.read_parquet(core.DATA / "buildings_3d.parquet")
EDGES = json.loads((core.DATA / "evac_edges.geojson").read_text())
RAIL = json.loads((core.DATA / "infra_rail.geojson").read_text())
feats = lambda g, m: {"type": "FeatureCollection", "features": [f for f in g["features"]
                                                                 if f["properties"]["municipality"] == m]}

# ---- town: shared sidebar picker (session_state["town"]), else the town with the most people in the water
T = towns[towns.variant == V].sort_values("people", ascending=False)
pick = st.session_state.get("town")
rows = T[T.municipality == pick]
t = (rows if len(rows) else T).iloc[0]
modelled = t.area in anna.MODELLED

# ---- controls
with st.sidebar:
    st.caption("3D view layers")
    on = dict(water=st.toggle("2021 water", True), homes=st.toggle("Homes", True),
              shelters=st.toggle("Dry shelters", True), roads=st.toggle("Evacuation roads", True),
              rail=st.toggle("Rail in the water", True), care=st.toggle("Care sites", True))
    exag = st.slider("Terrain exaggeration", 1.0, 3.0, 1.5, 0.25, help="Heights ×; 1 = true relief")
    imagery = st.segmented_control("Imagery", ["Sentinel-2", "Esri"], default="Sentinel-2",
                                   help="Sentinel-2 cloudless (10 m, EOX) or Esri World Imagery (sharper)") or "Sentinel-2"

# ---- data for this town
hb = B3D[(B3D.municipality == t.municipality) & (B3D.area == t.area)]
homes = hb[hb.use == 1]
single = (homes.storeys == 1) & (homes.height_m != 2.5)  # 2.5 m is OBAT's fill-in value: height unknown
n_single, n_unknown = int(single.sum()), int((homes.height_m == 2.5).sum())
plan = (bus[(bus.municipality == t.municipality) & (bus.area == t.area)]
        .groupby(["shelter", "s_lon", "s_lat"], as_index=False).people.sum().sort_values("people", ascending=False))
care = crit[(crit.municipality == t.municipality) & (crit.share_of_site_flooded >= .05) & crit.in_worst_flood]


def squares(d, half=4.5):
    """Each OBAT point as a ~9 m footprint so MapLibre can extrude it (OBAT gives points, not outlines)."""
    dy = half / 111_320
    out = []
    for r in d.itertuples():
        dx = half / (111_320 * math.cos(math.radians(r.lat)))
        x, y = r.lon, r.lat
        unknown = r.height_m == 2.5
        one = r.storeys == 1 and not unknown
        out.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[
            [x - dx, y - dy], [x + dx, y - dy], [x + dx, y + dy], [x - dx, y + dy], [x - dx, y - dy]]]},
            "properties": {"h": float(max(r.height_m, 3)), "one": bool(one),
                           "t": "Single-storey home" if one else "Home, height unknown" if unknown
                           else "Home with an upper floor",
                           "i": "height unknown" if unknown else f"about {r.height_m:.0f} m high"}})
    return {"type": "FeatureCollection", "features": out}


# ---- river replay: nearest GloFAS point within 15 km of the town centre
rep = core.load_replay().loc["2021-07-12":"2021-07-20"]
g_lat, g_lon = np.array(list(forecast.GAUGES.values())).T
d_km = core.km(t.lon, t.lat, g_lon, g_lat)
gauge = list(forecast.GAUGES)[int(d_km.argmin())] if d_km.min() <= 15 else None

# ---- layout
st.title(f"{t['name']} in 3D")
st.caption(f"The July 2021 water on the valley floor{' (modelled: EFAS 500-year zone, no satellite map here)' if modelled else ''}. "
           "Drag to pan, right-drag or Ctrl-drag to tilt and turn, scroll to zoom.")

opacity, day = .55, None
if gauge:
    days = list(rep.index)
    q = rep[gauge]
    day = st.select_slider("Day, July 2021", days, value=q.idxmax(), format_func=lambda d: f"{d:%a %d %b}")
    lo, hi = q.min(), q.max()
    opacity = .12 + .6 * (q[day] - lo) / (hi - lo) if hi > lo else .55

map_col, facts = st.columns([3, 1], gap="medium")

with facts:
    with st.container(border=True):
        st.metric("Residents in the 2021 water", about(t.people),
                  help="GHS-POP 2020 spread over flooded homes: an order of magnitude")
        st.metric("Single-storey homes", fmt(n_single),
                  help=f"No upper floor to escape to. {fmt(n_unknown)} more homes have no reliable height (OBAT 2.5 m).")
        st.metric("Dry shelters", fmt(len(plan)), help="Candidate sites in the 10 km bus plan, dry in 2021 and "
                                                        "in the EFAS 100-year model; not official")
        st.metric("Care sites to evacuate", fmt(len(care)), help="Hospitals, care homes, schools with at least 5 % "
                                                                  "of the site in the 2021 water")
    if gauge:
        with st.container(border=True):
            ch = pd.DataFrame({"day": rep.index, "flow": rep[gauge].values})
            base = alt.Chart(ch).encode(x=alt.X("day:T", title=None, axis=alt.Axis(format="%d", tickCount=9)))
            line = base.mark_line(color="#0071e3", strokeWidth=2).encode(
                y=alt.Y("flow:Q", title="m³/s", axis=alt.Axis(tickCount=3)))
            rule = alt.Chart(pd.DataFrame({"day": [day]})).mark_rule(color="#1d1d1f", strokeDash=[3, 3]).encode(x="day:T")
            dot = base.transform_filter(alt.datum.day == alt.expr.toDate(day.isoformat())).mark_point(
                filled=True, size=50, color="#1d1d1f").encode(y="flow:Q")
            st.caption(f"River flow, {gauge} ({d_km.min():.0f} km away)")
            st.altair_chart((line + rule + dot).properties(height=120), width="stretch")
            st.caption(f"{day:%d %b}: {fmt(rep.loc[day, gauge])} m³/s. GloFAS model. Water opacity on the map follows "
                       "this flow as a visual cue only: the map shows the final 2021 extent, not the water on that day.")
    else:
        st.caption("No river point of the replay lies within 15 km of this town, so there is no timeline here.")

# camera: frame the flooded homes (5-95 % of them), else the town centre
if len(hb):
    x0, x1 = hb.lon.quantile([.05, .95])
    y0, y1 = hb.lat.quantile([.05, .95])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    span = max(x1 - x0, (y1 - y0) * 1.6, .01)
    zoom = min(15.5, math.log2(1000 * 360 / (512 * span)) - .2)
else:
    cx, cy, zoom = t.lon, t.lat, 13

water = flood[(t.area, V)]
D = dict(
    water=water if on["water"] else None, modelled=bool(modelled), opacity=round(float(opacity), 3),
    homes=squares(homes) if on["homes"] and len(homes) else None,
    roads=feats(EDGES, t.municipality) if on["roads"] else None,
    rail=feats(RAIL, t.municipality) if on["rail"] else None,
    shelters=[dict(n=r.shelter, x=r.s_lon, y=r.s_lat, p=round(r.people)) for r in plan.itertuples()] if on["shelters"] else [],
    care=[dict(n=r.name, k=r.type, x=r.lon, y=r.lat, s=r.share_of_site_flooded) for r in care.itertuples()] if on["care"] else [],
    exag=exag, center=[float(cx), float(cy)], zoom=round(float(zoom), 2), key=f"v3d|{t.municipality}",
    imagery=imagery,
)

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
html,body{margin:0;height:100%;font:13px/1.35 "Source Sans Pro",system-ui,sans-serif}
#m{position:absolute;inset:0;border-radius:12px;overflow:hidden}
.pin{display:flex;align-items:center;gap:6px;cursor:default;transform:translateY(-2px)}
.pin i{width:12px;height:12px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.5);flex:none}
.pin b{background:rgba(255,255,255,.92);color:#1d1d1f;padding:2px 7px;border-radius:6px;font-weight:600;
  white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.25);max-width:190px;overflow:hidden;text-overflow:ellipsis}
.key{position:absolute;left:10px;bottom:28px;background:rgba(255,255,255,.92);border-radius:10px;padding:8px 10px;
  box-shadow:0 1px 4px rgba(0,0,0,.25);color:#1d1d1f}
.key div{display:flex;align-items:center;gap:7px;margin:2px 0}
.key s{display:inline-block;width:14px;height:10px;border-radius:2px;text-decoration:none}
.maplibregl-popup-content{font:13px/1.35 system-ui,sans-serif;padding:8px 10px}
</style></head><body><div id="m"></div><div class="key" id="k"></div>
<script>
const D = __DATA__;
const IMG = {
  "Sentinel-2": {tiles:["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/g/{z}/{y}/{x}.jpg"],
    maxzoom:15, attribution:'<a href="https://s2maps.eu" target="_blank">Sentinel-2 cloudless 2021</a> by EOX IT Services GmbH (modified Copernicus Sentinel data 2021), CC BY-NC-SA 4.0'},
  "Esri": {tiles:["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    maxzoom:19, attribution:'Imagery: Esri, Maxar, Earthstar Geographics, and the GIS User Community'}
}[D.imagery];
let cam = null;
try { cam = JSON.parse(sessionStorage.getItem(D.key)); } catch (e) {}
const map = new maplibregl.Map({
  container: "m", hash: false, maxPitch: 80,
  center: cam ? cam.c : D.center, zoom: cam ? cam.z : D.zoom, pitch: cam ? cam.p : 60, bearing: cam ? cam.b : -20,
  style: {version: 8, sources: {
      img: {type: "raster", tiles: IMG.tiles, tileSize: 256, maxzoom: IMG.maxzoom, attribution: IMG.attribution},
      dem: {type: "raster-dem", tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
        encoding: "terrarium", tileSize: 256, maxzoom: 15,
        attribution: 'Terrain: <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank">AWS Terrain Tiles</a> (Mapzen; SRTM, EU-DEM and others)'},
      hs: {type: "raster-dem", tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
        encoding: "terrarium", tileSize: 256, maxzoom: 15}},
    layers: [{id: "img", type: "raster", source: "img"},
      {id: "hs", type: "hillshade", source: "hs", paint: {"hillshade-exaggeration": 0.25, "hillshade-shadow-color": "#1d1d1f"}}]},
  attributionControl: {compact: true}
});
map.addControl(new maplibregl.NavigationControl({visualizePitch: true}), "top-right");
map.addControl(new maplibregl.ScaleControl({unit: "metric"}), "bottom-right");
map.on("moveend", () => { try { sessionStorage.setItem(D.key, JSON.stringify(
  {c: map.getCenter().toArray(), z: map.getZoom(), p: map.getPitch(), b: map.getBearing()})); } catch (e) {} });

const key = [];
map.once("style.load", () => {
  map.setTerrain({source: "dem", exaggeration: D.exag});
  if (map.setSky) map.setSky({"sky-color": "#a9c8ee", "horizon-color": "#e8eef5", "fog-color": "#e8eef5",
    "sky-horizon-blend": 0.6, "horizon-fog-blend": 0.6, "fog-ground-blend": 0.2});
  if (D.water) {
    map.addSource("water", {type: "geojson", data: D.water});
    map.addLayer({id: "water", type: "fill", source: "water", paint: {"fill-color": "#1e7bff", "fill-opacity": D.opacity}});
    map.addLayer({id: "water-edge", type: "line", source: "water", paint: {"line-color": "#7fb6ff", "line-width": 1.2,
      "line-dasharray": D.modelled ? [3, 2] : [1, 0]}});
    key.push(["#1e7bff", D.modelled ? "2021 water, modelled (EFAS 500-year)" : "2021 water (satellite, all passes)"]);
  }
  if (D.rail) {
    map.addSource("rail", {type: "geojson", data: D.rail});
    map.addLayer({id: "rail", type: "line", source: "rail", paint: {"line-color": "#1d1d1f", "line-width": 4}});
    map.addLayer({id: "rail2", type: "line", source: "rail", paint: {"line-color": "#fff", "line-width": 2, "line-dasharray": [2, 2]}});
    key.push(["#1d1d1f", "Rail in the water"]);
  }
  if (D.roads) {
    map.addSource("roads", {type: "geojson", data: D.roads});
    map.addLayer({id: "roads", type: "line", source: "roads", layout: {"line-cap": "round"},
      paint: {"line-color": "#eb6834", "line-width": ["interpolate", ["linear"], ["get", "people"], 0, 2, 3000, 7]}});
    key.push(["#eb6834", "Busiest evacuation roads"]);
  }
  if (D.homes) {
    map.addSource("homes", {type: "geojson", data: D.homes});
    map.addLayer({id: "homes", type: "fill-extrusion", source: "homes", paint: {
      "fill-extrusion-color": ["case", ["get", "one"], "#d70015", "#c7c7cc"],
      "fill-extrusion-height": ["get", "h"], "fill-extrusion-opacity": 0.92}});
    key.push(["#d70015", "Single-storey home"], ["#c7c7cc", "Other home (height from OBAT)"]);
    const pop = new maplibregl.Popup({closeButton: false, offset: 6});
    map.on("click", "homes", e => pop.setLngLat(e.lngLat).setHTML(
      "<b>" + e.features[0].properties.t + "</b><br>" + e.features[0].properties.i).addTo(map));
    map.on("mouseenter", "homes", () => map.getCanvas().style.cursor = "pointer");
    map.on("mouseleave", "homes", () => map.getCanvas().style.cursor = "");
  }
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const pin = (x, y, col, label, tip, showLabel) => {
    const el = document.createElement("div"); el.className = "pin"; el.title = tip;
    el.innerHTML = '<i style="background:' + col + '"></i>' + (showLabel ? "<b>" + esc(label) + "</b>" : "");
    new maplibregl.Marker({element: el, anchor: "left"}).setLngLat([x, y]).addTo(map);
  };
  D.shelters.forEach((s, i) => pin(s.x, s.y, "#248a3d", s.n, s.n + ": about " + s.p + " people in the bus plan", i < 4));
  if (D.shelters.length) key.push(["#248a3d", "Dry shelter (top 4 named)"]);
  D.care.forEach(c => pin(c.x, c.y, "#7a2c10", c.n, c.k + ", " + Math.round(c.s * 100) + "% of the site in the 2021 water", true));
  if (D.care.length) key.push(["#7a2c10", "Care site in the water"]);
  document.getElementById("k").innerHTML = key.map(([c, l]) => '<div><s style="background:' + c + '"></s>' + l + "</div>").join("")
    || "<div>No layers on</div>";
});
</script></body></html>"""

with map_col:
    components.html(HTML.replace("__DATA__", json.dumps(D, default=float).replace("</", "<\\/")), height=640)
    st.caption("Elevation: AWS Terrain Tiles (Mapzen, Terrarium; SRTM, EU-DEM and other open sources). Imagery: "
               + ("Sentinel-2 cloudless 2021 by EOX IT Services GmbH (contains modified Copernicus Sentinel data), "
                  "CC BY-NC-SA 4.0, non-commercial use." if imagery == "Sentinel-2" else
                  "Esri World Imagery (Esri, Maxar, Earthstar Geographics), attribution required, Esri terms of use.")
               + " Map: MapLibre GL JS (BSD). Homes are OBAT points drawn as 9 m blocks, not real outlines; "
                 "2.5 m tall homes have no reliable height.")
