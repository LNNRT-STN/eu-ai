"""MapLibre 3D map of one town: the July 2021 water draped on satellite terrain, with homes (single-storey red),
dry shelters, evacuation roads, rail and care sites. Shared by the Evacuation plan (hero) and the 3D view page.
Open source, no token: MapLibre GL JS (BSD), AWS Terrain Tiles (Terrarium), EOX Sentinel-2 cloudless or Esri imagery."""
import json
import math

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import anna
import core

V = "worst"
ALL = dict(water=True, homes=True, shelters=True, roads=True, rail=True, care=True)
B3D = pd.read_parquet(core.DATA / "buildings_3d.parquet")
EDGES = json.loads((core.DATA / "evac_edges.geojson").read_text())
RAIL = json.loads((core.DATA / "infra_rail.geojson").read_text())
feats = lambda g, m: {"type": "FeatureCollection", "features": [f for f in g["features"]
                                                                 if f["properties"]["municipality"] == m]}


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


def render(t, on=ALL, exag=1.5, imagery="Sentinel-2", opacity=.45, height=640, attribution=True):
    """Draw town row `t` (app_towns, variant worst) in 3D."""
    _, _, crit, _, flood, *_ = anna.load()
    bus = anna.load_moves()[1]
    hb = B3D[(B3D.municipality == t.municipality) & (B3D.area == t.area)]
    homes = hb[hb.use == 1]
    plan = (bus[(bus.municipality == t.municipality) & (bus.area == t.area)]
            .groupby(["shelter", "s_lon", "s_lat"], as_index=False).people.sum().sort_values("people", ascending=False))
    care = crit[(crit.municipality == t.municipality) & (crit.share_of_site_flooded >= .05) & crit.in_worst_flood]
    # camera: frame the flooded homes (5-95 % of them), else the town centre
    if len(hb):
        x0, x1 = hb.lon.quantile([.05, .95])
        y0, y1 = hb.lat.quantile([.05, .95])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        span = max(x1 - x0, (y1 - y0) * 1.6, .01)
        zoom = min(15.5, math.log2(1000 * 360 / (512 * span)) + .4)
    else:
        cx, cy, zoom = t.lon, t.lat, 13
    D = dict(
        water=flood[(t.area, V)] if on["water"] else None, modelled=bool(t.area in anna.MODELLED),
        opacity=round(float(opacity), 3),
        homes=squares(homes) if on["homes"] and len(homes) else None,
        roads=feats(EDGES, t.municipality) if on["roads"] else None,
        rail=feats(RAIL, t.municipality) if on["rail"] else None,
        shelters=[dict(n=r.shelter, x=r.s_lon, y=r.s_lat, p=round(r.people)) for r in plan.itertuples()]
        if on["shelters"] else [],
        care=[dict(n=r.name, k=r.type, x=r.lon, y=r.lat, s=r.share_of_site_flooded)
              for r in care.sort_values("share_of_site_flooded", ascending=False).itertuples()] if on["care"] else [],
        exag=exag, center=[float(cx), float(cy)], zoom=round(float(zoom), 2), key=f"v3d|{t.municipality}",
        imagery=imagery)
    # The component iframe is about:srcdoc, whose location.origin reads "null" while its workers get the app's
    # origin, so MapLibre drops every worker message (no terrain, no GeoJSON). Loading the map from a blob: URL
    # inside it gives page and workers the same origin.
    page = HTML.replace("__DATA__", json.dumps(D, default=float).replace("</", "<\\/"))
    components.html("<style>html,body{margin:0;height:100%}</style><iframe id='f' title='3D map' "
                    "style='border:0;width:100%;height:100%'></iframe><script>document.getElementById('f').src="
                    "URL.createObjectURL(new Blob([" + json.dumps(page).replace("</", "<\\/")
                    + "],{type:'text/html'}));</script>", height=height)
    if attribution:
        st.caption("Elevation: AWS Terrain Tiles (Mapzen, Terrarium; SRTM, EU-DEM and other open sources). Imagery: "
                   + ("Sentinel-2 cloudless 2021 by EOX IT Services GmbH (contains modified Copernicus Sentinel data), "
                      "CC BY-NC-SA 4.0, non-commercial use." if imagery == "Sentinel-2" else
                      "Esri World Imagery (Esri, Maxar, Earthstar Geographics), attribution required, Esri terms of use.")
                   + " Map: MapLibre GL JS (BSD). Homes are OBAT points drawn as 9 m blocks, not real outlines; "
                     "2.5 m tall homes have no reliable height.")


HTML = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.js"></script>
<style>
html,body{margin:0;height:100%;font:13px/1.35 "Source Sans Pro",system-ui,sans-serif}
#m{position:absolute;inset:0;border-radius:12px;overflow:hidden}
.pin{display:flex;align-items:center;gap:6px;cursor:default;transform:translateY(-2px)}
.pin i{width:12px;height:12px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.5);flex:none}
.pin b{background:rgba(255,255,255,.92);color:#1d1d1f;padding:2px 7px;border-radius:6px;font-weight:600;
  white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.25);max-width:190px;overflow:hidden;text-overflow:ellipsis}
.key{position:absolute;left:10px;top:10px;font-size:12px;background:rgba(255,255,255,.92);border-radius:10px;padding:8px 10px;
  box-shadow:0 1px 4px rgba(0,0,0,.25);color:#1d1d1f}
.key #k div{display:flex;align-items:center;gap:7px;margin:2px 0}
.key s{display:inline-block;width:14px;height:10px;border-radius:2px;text-decoration:none}
.maplibregl-popup-content{font:13px/1.35 system-ui,sans-serif;padding:8px 10px}
.key summary{cursor:pointer;font-weight:600;list-style:none}
.key summary::-webkit-details-marker{display:none}
.key[open] summary{margin-bottom:4px}
</style></head><body><div id="m"></div><details class="key" id="kd"><summary>Legend</summary><div id="k"></div></details>
<script>document.getElementById("kd").open = innerWidth > 600;  // on phones the legend starts folded</script>
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
  if (D.rail && D.rail.features.length) {
    map.addSource("rail", {type: "geojson", data: D.rail});
    map.addLayer({id: "rail", type: "line", source: "rail", paint: {"line-color": "#1d1d1f", "line-width": 4}});
    map.addLayer({id: "rail2", type: "line", source: "rail", paint: {"line-color": "#fff", "line-width": 2, "line-dasharray": [2, 2]}});
    key.push(["#1d1d1f", "Rail in the water"]);
  }
  if (D.roads && D.roads.features.length) {
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
  D.care.forEach((c, i) => pin(c.x, c.y, "#7a2c10", c.n, c.n + " (" + c.k + "), " + Math.round(c.s * 100) + "% of the site in the 2021 water", i < 3));
  if (D.care.length) key.push(["#7a2c10", "Care site in the water (top 3 named)"]);
  document.getElementById("k").innerHTML = key.map(([c, l]) => '<div><s style="background:' + c + '"></s>' + l + "</div>").join("")
    || "<div>No layers on</div>";
});
</script></body></html>"""
