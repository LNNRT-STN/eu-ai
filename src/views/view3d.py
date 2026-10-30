"""3D tab of the Town plan: the town's buildings in the 500-year flood zone, raised to their height and coloured by
the most frequent EFAS flood that reaches them (10-, 100- or 500-year), with the dry shelters of the plan. Shows how
the town grows into the water as the flood gets rarer. Numbers: outputs/rp/buildings_3d.parquet (GHS-OBAT, flags
in_rp10 / in_rp100 / in_rp500) and the 10 km bus plan of the scenario.

Imported once by views/evacuate.py, so everything that draws lives in render()."""
import math

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import fmt
from views.shelters import _legend as shelters_legend

B3D = pd.read_parquet(core.DATA / "buildings_3d.parquet")   # every OBAT building in the 500-year zone, with height
ZONE = {"rp10": "10-year zone", "rp100": "100-year zone (not the 10-year)", "rp500": "500-year zone only"}


def render(t, v):
    """Draw town row `t` (app_towns) in 3D; `v` is the scenario's variant (rp10 / rp100 / rp500)."""
    hb = B3D[(B3D.municipality == t.municipality) & (B3D.area == t.area)]
    if hb.empty:
        st.info("No building of this town lies in the modelled flood zones.")
        return
    # the most frequent flood that reaches each building (zones are nested: rp10 inside rp100 inside rp500)
    z = pd.Series("rp500", index=hb.index).mask(hb.in_rp100, "rp100").mask(hb.in_rp10, "rp10")
    n = z.value_counts()
    home = hb.use == 1
    c = st.container(key="kpi_3d").columns(3)
    for col, k in zip(c, core.VARIANT):
        inside = hb[f"in_{k}"]
        col.metric(f"{core.VARIANT[k].capitalize()} zone", f"{fmt(int((home & inside).sum()))} homes", border=True,
                   help=f"{fmt(int(inside.sum()))} buildings in all" + (" · the planned flood" if k == v else ""))

    hv = hb.assign(z=hb.height_m.clip(lower=3), c=[core.rgb(core.RP_COL[k], 230) for k in z],
                   tname=[("Home" if u == 1 else "Building") + f" · {ZONE[k]}" for u, k in zip(hb.use, z)],
                   tinfo=[f"about {h:.0f} m high" if h != 2.5 else "height unknown" for h in hb.height_m])
    hv = hv[["lon", "lat", "z", "c", "tname", "tinfo"]]
    layers = [pdk.Layer("ColumnLayer", hv, get_position=["lon", "lat"], get_elevation="z", elevation_scale=4, radius=6,
                        get_fill_color="c", pickable=True, extruded=True)]
    bus = anna.load_moves()[1]
    sh = (bus[(bus.variant == v) & (bus.municipality == t.municipality) & (bus.people >= .5)]
          .groupby(["shelter", "s_lon", "s_lat"], as_index=False).people.sum())
    if len(sh):
        sh = sh.assign(lon=sh.s_lon, lat=sh.s_lat, tname=sh.shelter,
                       tinfo=[f"dry shelter · about {p:.0f} people from {t['name']}" for p in sh.people])
        layers.append(core.points(sh, core.rgb(core.SHELTER, 230), 7))
    x0, x1 = hb.lon.quantile([.05, .95])
    y0, y1 = hb.lat.quantile([.05, .95])
    span = max(x1 - x0, (y1 - y0) * 1.6, .01)
    zoom = min(15.5, math.log2(1000 * 360 / (512 * span)) + .2)
    st.pydeck_chart(pdk.Deck(
        layers=layers, map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "<b>{tname}</b><br/>{tinfo}"},
        initial_view_state=pdk.ViewState(longitude=(x0 + x1) / 2, latitude=(y0 + y1) / 2, zoom=zoom, pitch=55,
                                         bearing=-20),
        views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=520)
    shelters_legend([(core.RP_COL[k], f"{ZONE[k]}: {fmt(int(n.get(k, 0)))} buildings", False) for k in core.VARIANT]
                    + ([(core.SHELTER, "Dry shelter of the plan", True)] if len(sh) else []))
    st.caption("Darker = flooded more often. Drag to pan, right-drag or Ctrl-drag to tilt and turn.")
    with st.expander("How this is computed", icon=":material/info:"):
        st.caption("Buildings: GHS-OBAT points inside the EFAS 500-year zone, drawn as columns (height × 4), not real "
                   "outlines; 2.5 m is OBAT's fill-in value, so those heights are unknown. Colour: the most frequent "
                   "flood whose zone covers the building. Zones are modelled (EFAS, no dikes or flood walls), so "
                   "towns behind dikes are an upper bound. Map © OpenStreetMap contributors, © CARTO.")
