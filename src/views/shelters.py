"""Candidate shelters, a section of the Town plan's Shelters tab: schools, sports halls and civic buildings with at
least 200 m² of floor that stayed dry in July 2021 and sit outside the EFAS 100-year zone. Not an official list.

Imported once by views/evacuate.py, so everything that draws lives in render()."""
from html import escape

import streamlit as st

import core
from core import about, fmt


def _legend(parts):
    """Inline-styled legend row (the page does not load core.style's CSS)."""
    st.html("<div style='display:flex;flex-wrap:wrap;gap:.3rem 1rem;font-size:.8rem;color:#4f6580;margin:.4rem .25rem 0'>"
            + "".join(f"<span style='display:inline-flex;align-items:center;gap:.4rem'><i style='width:.75rem;"
                      f"height:.75rem;display:inline-block;background:{h};border-radius:{'50%' if r else '3px'}'></i>"
                      f"{escape(lab)}</span>" for h, lab, r in parts) + "</div>")


def render(t):
    """Candidate sites nearest to town row `t` (or in all areas), with a type filter, map and download."""
    shelters = core.load()["shelters"]
    name = t["name"]
    c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
    scope = c1.segmented_control("Show", [f"Nearest to {name}", "All areas"], default=f"Nearest to {name}",
                                 key=f"sh_scope_{t.municipality}", label_visibility="collapsed") or f"Nearest to {name}"
    kinds = c2.pills("Type", list(core.KIND), selection_mode="multi", default=list(core.KIND), key="sh_kinds",
                     label_visibility="collapsed")
    near = scope != "All areas"

    sh = shelters[shelters.type.isin(kinds or [])]
    if near:
        sh = sh.assign(km=core.km(t.lon, t.lat, sh.lon, sh.lat)).sort_values("km").head(25)
    else:
        sh = sh.sort_values("capacity_central", ascending=False)
    if sh.empty:
        st.info("No candidate sites match. Pick at least one type.", icon=":material/search_off:")
        return

    left, right = st.columns([2, 3], gap="medium")
    with right:
        cols = ["name", "type", "muni"] + (["km"] if near else []) + ["capacity_central", "gfa"]
        pick = st.dataframe(sh[cols], hide_index=True, height=460, on_select="rerun", selection_mode="single-row",
                            key=f"sh_site_{t.municipality if near else 'all'}", column_config={
                                "name": "Site", "type": st.column_config.TextColumn("Type", width="small"),
                                "muni": "Municipality",
                                "km": st.column_config.NumberColumn("km", format="%.1f", width="small",
                                                                    help="Straight line from the town centre"),
                                "capacity_central": st.column_config.NumberColumn(
                                    "Places", format="localized", width="small",
                                    help="Floor area × 50 % usable ÷ 4 m² per person. Order of magnitude."),
                                "gfa": st.column_config.NumberColumn("Floor m²", format="localized", width="small")})
        c_a, c_b = st.columns([1, 1], vertical_alignment="center")
        c_a.caption(f"{fmt(len(sh))} sites · ≈ {about(sh.capacity_central.sum())} places"
                    + (" · nearest 25" if near else ""))
        c_b.download_button("Download list", sh[cols + ["lon", "lat"]].to_csv(index=False), "candidate_shelters.csv",
                            icon=":material/download:", type="tertiary", width="stretch", key="sh_dl")

    sel = sh.iloc[pick.selection.rows[0]] if pick.selection.rows else None
    with left:
        layers = core.water("worst") + [core.points(
            sh.assign(tip=[f"{n}\n{k} · {m}\n≈ {c:,.0f} places" for n, k, m, c in
                           zip(sh.name, sh.type, sh.muni, sh.capacity_central)],
                      fill=[core.rgb(core.KIND[k]) for k in sh.type]), "fill", 4, 1)]
        focus = (t.lon, t.lat) if near else None
        if near:
            layers.append(core.points(t.to_frame().T[["lon", "lat"]].astype(float).assign(
                tip=f"{name}\ncentre of the municipality"), core.rgb(core.EVACUATE), 8))
        if sel is not None:
            layers.append(core.points(sel.to_frame().T[["lon", "lat"]].astype(float).assign(tip=f"{sel['name']}"),
                                      core.rgb("#0071e3"), 9, 3))
        v = (sel.lon, sel.lat) if sel is not None else focus
        core.deck(layers, core.view(core.bbox(), v, 13 if sel is not None else 12), 400)
        _legend([(core.KIND[k], k, True) for k in kinds if k in set(sh.type)]
                + ([(core.EVACUATE, "Town centre", True)] if near else [])
                + [(core.WATER, "2021 water", False), (core.MODEL, "Vesdre, modelled water", False)])
        if sel is not None:
            st.markdown(f"**{sel['name']}** · {sel.type} · {sel.muni or '–'}  \n"
                        f"Floor {fmt(sel.gfa)} m²{' (capped)' if sel.capped else ''} · ≈ {fmt(sel.capacity_central)} "
                        f"places · [Open in OpenStreetMap](https://www.openstreetmap.org/#map=18/{sel.lat}/{sel.lon})")
        else:
            st.caption("Select a row to see the site on the map.")
