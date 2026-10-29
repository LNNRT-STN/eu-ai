"""Home page for Anna. Every section title is the finding itself (Storytelling with Data p.187, horizontal logic);
the page follows diagnosis -> guiding policy -> coherent actions (Good Strategy Bad Strategy p.60).
Numbers come from outputs/data/ (notebooks/pipeline.py, q4_ranking.py) and src/out/meuse/replay_2021.json."""
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import about, fmt

head, towns, crit, shel, flood, summary, qc = anna.load()
V = "worst"                                                    # all satellite passes: closest to official 2021 figures
H, T = head[V], towns[towns.variant == V].copy()
obs, mod = H["observed"], H["modelled_vesdre"]
T["no_shelter"] = T.no_reach + T.full
C = crit[crit.share_of_site_flooded.ge(.05) & crit.in_worst_flood.astype(bool)]
care = C[C.type.isin(["hospital", "care home"])]
DISTRICT = {"ahr": "Ahrweiler", "erftstadt": "Rhein-Erft", "schleiden": "Euskirchen"}
by_d = care.groupby(care.area.map(DISTRICT)).size().sort_values(ascending=False)
top_t = care.town.value_counts()

# 1. the decision
core.banner(core.EVACUATE,
            f"Evacuate the {len(care)} hospitals and care homes that sat in the 2021 water first.",
            "<b>Who:</b> the crisis staffs of the districts of "
            + ", ".join(f"{d} ({n})" for d, n in by_d.items())
            + f". {top_t.iloc[0]} of the sites are in {top_t.index[0]}.<br><b>Why:</b> their residents cannot walk to "
              "a shelter and need the most time to move. Check first whether any site was flood-proofed after 2021.",
            note=False)
st.space("medium")

# 2. the diagnosis, then the towns it applies to
st.html(f"<header class='pg'><h1 style='font-size:1.6rem'>The gap is space, not distance</h1><p>If the July 2021 "
        f"flood came back today, {about(obs['no_shelter'])} people would find no shelter place where the satellite saw "
        "the water (Meuse, Ahr, Eifel, Erft). <b>{about(obs['full'])} of them "
        f"have a shelter within walking distance, but it is full.</b> So: move those who cannot walk first, make room where "
        "people can walk, and bring transport where they cannot.</p></header>")
st.space("small")

top = T.nlargest(5, "no_shelter").reset_index(drop=True)
left, right = st.columns([5, 6], gap="medium")
with left:
    rows = [(f"<b>{i + 1}. {r.label}</b>",
             ("Shelters nearby are full" if r.full >= r.no_reach else "No shelter within 1.5 km on foot")
             + (" · modelled, the satellite missed this valley" if r.area in anna.MODELLED else ""),
             f"<b>{about(r.no_shelter)}</b>") for i, r in top.iterrows()]
    core.group(rows, "People with no shelter place, by town", "Pick a town below the map for its sites and shelters.")
with right:
    pick = st.selectbox("Town", [None, *top.municipality], label_visibility="collapsed",
                        format_func=lambda m: "All five towns" if m is None else top.set_index("municipality").label[m])
    sel = None if pick is None else top[top.municipality == pick].iloc[0]
    layers = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=False,
                        get_fill_color=[0, 113, 227, 40 if a in anna.MODELLED else 90]) for a in anna.AREA]
    layers.append(pdk.Layer("ScatterplotLayer", top.assign(
        r=lambda d: d.no_shelter ** .5 * .32 + 4,
        tip=lambda d: [f"<b>{x.label}</b><br>{fmt(x.no_shelter)} people with no shelter place" for x in d.itertuples()]),
        get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'", get_fill_color=core.rgb(anna.TOO_FAR, 170),
        get_line_color=[255, 255, 255], line_width_min_pixels=1.5, stroked=True, pickable=True))
    layers.append(core.points(care.assign(tip=[f"<b>{n}</b><br>{t} · {w}" for n, t, w in
                                               zip(care.name, care.type, care.town)]), core.rgb(core.EVACUATE), 6))
    vs = (pdk.ViewState(longitude=6.35, latitude=50.62, zoom=7.7) if sel is None else
          pdk.ViewState(longitude=sel.lon, latitude=sel.lat, zoom=11.5))
    core.deck(layers, vs, 400)
    core.legend(core.swatch(anna.TOO_FAR, "People with no shelter place", True)
                + core.swatch(core.EVACUATE, "Hospital or care home in the water", True)
                + core.swatch("rgba(0,113,227,.35)", "2021 water"))

if sel is not None:
    a, b = st.columns(2, gap="medium")
    with a:
        here = C[(C.town == sel["name"]) & (C.area == sel.area)].sort_values("share_of_site_flooded", ascending=False)
        core.group([(f"<b>{r.name}</b>", r.type, f"{r.share_of_site_flooded:.0%} under water") for r in here.itertuples()]
                   or [("None in the water", "", "")], f"{sel.label}: sites in the water")
    with b:
        near = shel[(shel.town == sel["name"]) & (shel.area == sel.area)].nlargest(5, "capacity_central")
        core.group([(f"<b>{r.name if isinstance(r.name, str) else 'Unnamed ' + r.cat}</b>", r.cat,
                     f"≈ {about(r.capacity_central)} places") for r in near.itertuples()]
                   or [("No candidate shelter inside the town", "Look at neighbouring towns", "")],
                   f"{sel.label}: largest dry shelters", "Candidates from OpenStreetMap, not official shelters.")
st.space("medium")

# 3. coherent actions that follow from the diagnosis
full = T[T.full >= T.no_reach].nlargest(3, "full")
far = T[T.no_reach > T.full].nlargest(2, "no_reach")
st.html("<header class='pg'><h1 style='font-size:1.6rem'>Then make room, send buses, and plan who goes where</h1>"
        "</header>")
st.space("small")
core.group([
    (f"<b>Open overflow space in {', '.join(full.label)}</b>",
     "Municipal crisis cells. " + ", ".join(f"{r.label}: {about(r.full)}" for r in full.itertuples())
     + " people have a shelter nearby with no room left.", ""),
    (f"<b>Send buses to {' and '.join(far.label)}</b>",
     f"District crisis staff. {about(far.no_reach.sum())} people have no shelter within 1.5 km on foot.", ""),
    ("<b>Assign streets to shelters</b>",
     f"Municipal crisis cells. A plan shelters {about(obs['coordination_gain'])} more people than everyone heading to the "
     f"nearest hall ({about(mod['coordination_gain'])} more in the Vesdre, modelled).", ""),
])
st.space("medium")

# 4. time: the warning travels downstream (Thinking in Systems: delays are where coordination has leverage)
_, flow = core.load_brief()
peak = flow.idxmax()
first, last = peak.min(), peak.max()
up = sorted({g.split(" · ")[1] for g, d in peak.items() if d == first})
down = sorted({g.split(" · ")[1] for g, d in peak.items() if d == last})
st.html(f"<header class='pg'><h1 style='font-size:1.6rem'>A warning upstream buys downstream about "
        f"{(last - first).days} day</h1><p>In the July 2021 replay the rivers peaked at {', '.join(up)} on "
        f"{first:%d %B}, and at {', '.join(down)} on {last:%d %B}. The Ahr is not in this river model.</p></header>")
core.asof("replay")
st.space("medium")

# 5. then vs now (Big Book of Dashboards ch.6: compare now with then)
st.html("<header class='pg'><h1 style='font-size:1.6rem'>We cannot yet say we are better prepared</h1></header>")
core.group([
    ("<b>People living where the 2021 water reached</b>",
     f"{about(obs['people'])} in 2020, {about(obs['people_2025'])} in 2025. The 2025 figure is a projection, not a "
     "count, and it shows no drop.", "No sign of change"),
    ("<b>New defences, rebuilding, evacuation plans, flood-proofed hospitals, awareness</b>",
     "Not verified yet. The team's desk research on what changed since 2021 is in progress; nothing is shown until it "
     "has a source.", "Pending"),
], foot="Sources and checks: Data & limits.")
