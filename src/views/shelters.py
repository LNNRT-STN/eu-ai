import streamlit as st

import core
from core import about, fmt

core.style()  # the older analyst pages keep their custom look; the main pages use the theme only

d = core.load()
shelters, towns = d["shelters"], d["towns"]
hit = towns[towns.variant == "worst"].sort_values("people", ascending=False).drop_duplicates("municipality")

core.header("Shelters", "Candidate sites: schools, sports halls and civic buildings with at least 200 m² of floor that "
                        "stayed dry in July 2021 and sit outside the EFAS 100-year zone. Not an official list: confirm "
                        "capacity and access with the commune.")

c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
opts = [None, *hit.municipality]
name = dict(zip(hit.municipality, hit.municipality + " · ≈ " + hit.people.map(about) + " in the water"))
if st.session_state.get("near") not in opts:
    st.session_state.near = None
near = c1.selectbox("Nearest to", opts, format_func=lambda x: "All areas" if x is None else name[x], key="near",
                    help="Municipalities ordered by people in the July 2021 water.")
kinds = c2.pills("Type", list(core.KIND), selection_mode="multi", default=list(core.KIND))

sh = shelters[shelters.type.isin(kinds or [])]
focus = None
if near is not None:
    z = hit[hit.municipality == near].iloc[0]
    focus = (z.lon, z.lat)
    sh = sh.assign(km=core.km(z.lon, z.lat, sh.lon, sh.lat)).sort_values("km").head(25)
else:
    sh = sh.sort_values("capacity_central", ascending=False)

if sh.empty:
    st.info("No candidate sites match. Pick at least one type.", icon=":material/search_off:")
    st.stop()

left, right = st.columns([2, 3], gap="medium")
with right:
    cols = ["name", "type", "muni"] + (["km"] if near is not None else []) + ["capacity_central", "gfa"]
    pick = st.dataframe(sh[cols], hide_index=True, height=520, on_select="rerun", selection_mode="single-row",
                        key=f"site-{near}", column_config={
                            "name": "Site", "type": st.column_config.TextColumn("Type", width="small"),
                            "muni": "Municipality", "km": st.column_config.NumberColumn("km", format="%.1f", width="small"),
                            "capacity_central": st.column_config.NumberColumn(
                                "Places", format="localized", width="small",
                                help="Floor area × 50 % usable ÷ 4 m² per person. Order of magnitude."),
                            "gfa": st.column_config.NumberColumn("Floor m²", format="localized", width="small")})
    c_a, c_b = st.columns([1, 1], vertical_alignment="center")
    c_a.caption(f"{fmt(len(sh))} sites · ≈ {about(sh.capacity_central.sum())} places"
                + (" · nearest 25" if near is not None else ""))
    c_b.download_button("Download list", sh[cols + ["lon", "lat"]].to_csv(index=False), "candidate_shelters.csv",
                        icon=":material/download:", type="tertiary", width="stretch")

sel = sh.iloc[pick.selection.rows[0]] if pick.selection.rows else None
with left:
    layers = core.water("worst") + [core.points(
        sh.assign(tip=[f"{n}\n{t} · {m}\n≈ {c:,.0f} places" for n, t, m, c in
                       zip(sh.name, sh.type, sh.muni, sh.capacity_central)],
                  fill=[core.rgb(core.KIND[k]) for k in sh.type]), "fill", 4, 1)]
    if focus:
        layers.append(core.points(z.to_frame().T[["lon", "lat"]].astype(float).assign(
            tip=f"{z.municipality}\ncentre of the municipality"), core.rgb(core.EVACUATE), 8))
    if sel is not None:
        layers.append(core.points(sel.to_frame().T[["lon", "lat"]].astype(float).assign(tip=f"{sel['name']}"),
                                  core.rgb("#0071e3"), 9, 3))
    v = (sel.lon, sel.lat) if sel is not None else focus
    core.deck(layers, core.view(core.bbox(), v, 13 if sel is not None else 12), 460)
    core.legend("".join(core.swatch(core.KIND[k], k, True) for k in kinds if k in set(sh.type))
                + (core.swatch(core.EVACUATE, "Municipality centre", True) if focus else "")
                + core.swatch(core.WATER, "2021 water") + core.swatch(core.MODEL, "Vesdre, modelled water"))
    if sel is not None:
        core.group([("Type", sel.type), ("Municipality", sel.muni or "–"), ("Floor", f"{fmt(sel.gfa)} m²" + (" (capped)" if sel.capped else "")),
                    ("Places", f"≈ {fmt(sel.capacity_central)}"),
                    ("Map", f"<a href='https://www.openstreetmap.org/#map=18/{sel.lat}/{sel.lon}' target='_blank'>"
                            "Open in OpenStreetMap</a>")], sel["name"])
core.asof("osm")
