"""Region map: a bidirectional Streamlit component (plain HTML + MapLibre GL JS 5.6.0, no build step).

A new call with new data updates the live map in place (setData / setPaintProperty / marker updates), so a page
that reruns every 1-2 s during a replay does not flicker or lose the camera. Keep `key` constant.

data = {
  "towns":   [{municipality, label, lon, lat, status: none|watch|warn|evacuate, people, people_expected, modelled}],
  "flood":   GeoJSON FeatureCollection, each feature with properties.municipality,
  "areas":   optional GeoJSON of municipality outlines (properties.municipality), filled by the town's status,
  "homes":   optional GeoJSON points (properties.s: needs help|no news|safe), drawn from zoom 11 (the selected town),
  "closures": GeoJSON FeatureCollection of Point / LineString closed roads (optional),
  "selected": municipality or None (change it to fly there; None = region overview),
  "camera":  optional {center: [lon, lat], zoom, pitch, bearing}; applied whenever it changes,
  "overview": optional [west, south, east, north] for the region view (default: every town and all the water),
}
Returns None until the user clicks a town label or its area, then {"selected": municipality, "clicks": n}
(n grows with every click, so a repeated click on the same town is detectable).
"""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component("regionmap", path=str(Path(__file__).parent / "frontend"))

ATTRIBUTION = ("Map: © OpenStreetMap contributors © CARTO. Imagery: Sentinel-2 cloudless 2021 by EOX IT Services GmbH (contains modified Copernicus Sentinel "
               "data), CC BY-NC-SA 4.0. Elevation: AWS Terrain Tiles (Mapzen, Terrarium). Renderer: MapLibre GL JS (BSD).")


def region_map(data: dict, key: str, height: int = 560) -> dict | None:
    """Draw (first call) or update (later calls) the region map; return the last town the user clicked."""
    return _component(data=data, height=int(height), key=key, default=None)
