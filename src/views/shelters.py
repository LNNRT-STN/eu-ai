import streamlit as st

import core
from core import fmt

s, communes, cells, sites, geo = core.load()
zone = communes[communes.lens == "rp100"].sort_values("residents", ascending=False)

core.header("Shelters", "Candidate sites: schools and town halls that stayed dry in July 2021 and sit outside the "
                        "10- and 100-year zones. Not an official list: confirm capacity and access with the commune.")

c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
opts = [None, *zone.lau_id]
name = dict(zip(zone.lau_id, zone.commune + " · " + zone.residents.round().astype(int).map("{:,}".format) + " at risk"))
if st.session_state.get("near") not in opts:
    st.session_state.near = None
near = c1.selectbox("Nearest to", opts, format_func=lambda x: "Whole basin" if x is None else name[x], key="near",
                    help="Communes ordered by residents in the 100-year zone.")
kinds = c2.pills("Type", ["School", "Town hall"], selection_mode="multi", default=["School", "Town hall"])
strict = c3.toggle("Skip 500-year zone", help="Also leave out sites inside the EFAS 500-year zone.")

sh = sites[(sites.role == "shelter") & sites.type.isin(kinds or [])]
if strict:
    sh = sh[sh.model_zone == "Outside all zones"]
focus = None
if near is not None:
    z = zone[zone.lau_id == near].iloc[0]
    focus = (z.lon, z.lat)
    sh = sh.assign(km=core.km(z.lon, z.lat, sh.lon, sh.lat)).sort_values("km").head(25)

if sh.empty:
    st.info("No candidate sites match. Try both types, or turn off “Skip 500-year zone”. OSM has no schools or town "
            "halls for the Eschweiler area.", icon=":material/search_off:")
    st.stop()

left, right = st.columns([2, 3], gap="medium")
with right:
    cols = ["name", "type", "commune"] + (["km"] if near is not None else []) + ["model_zone"]
    pick = st.dataframe(sh[cols], hide_index=True, height=520, on_select="rerun", selection_mode="single-row",
                        key=f"site-{near}", column_config={
                            "name": "Site", "type": st.column_config.TextColumn("Type", width="small"), "commune": "Commune",
                            "km": st.column_config.NumberColumn("km", format="%.1f", width="small"), "model_zone": "Model"})
    c_a, c_b = st.columns([1, 1], vertical_alignment="center")
    c_a.caption(f"{fmt(len(sh))} sites" + (" · nearest 25" if near is not None else ""))
    c_b.download_button("Download list", sh[cols + ["lon", "lat"]].to_csv(index=False), "candidate_shelters.csv",
                        icon=":material/download:", type="tertiary", width="stretch")

sel = sh.iloc[pick.selection.rows[0]] if pick.selection.rows else None
with left:
    layers = core.water(geo, "rp100") + [core.points(
        sh.assign(tip=[f"<b>{n}</b><br>{t} · {c}<br>model: {z}" for n, t, c, z in zip(sh.name, sh.type, sh.commune, sh.model_zone)],
        fill=[core.rgb(core.KIND[k]) for k in sh.type]), "fill", 5)]
    if focus:
        layers.append(core.points(z.to_frame().T.assign(tip=f"<b>{z.commune}</b><br>centre of homes in the 100-year zone"),
                                  core.rgb(core.EVACUATE), 8))
    if sel is not None:
        layers.append(core.points(sel.to_frame().T.assign(tip=f"<b>{sel['name']}</b>"), core.rgb("#0071e3"), 9, 3))
    v = (sel.lon, sel.lat) if sel is not None else focus
    core.deck(layers, core.view(s, v) if v else core.view(s), 460)
    core.legend("".join(core.swatch(core.KIND[k], k, True) for k in kinds if k in set(sh.type))
                + (core.swatch(core.EVACUATE, "Homes at risk", True) if focus else "")
                + core.swatch("rgba(0,113,227,.4)", "Modelled 100-year zone"))
    if sel is not None:
        core.group([("Type", sel.type), ("Commune", sel.commune), ("July 2021", sel.flood_2021), ("Model", sel.model_zone),
                    ("Map", f"<a href='https://www.openstreetmap.org/{sel.osm_id}' target='_blank'>Open in OpenStreetMap</a>")],
                   sel["name"])
