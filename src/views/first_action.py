"""Home page for Anna: one decision, three numbers, one map, three next steps. Few words; detail behind 'Why'.
Numbers come from outputs/data/ (notebooks/pipeline.py, q4_ranking.py) and src/out/meuse/replay_2021.json."""
import pydeck as pdk
import streamlit as st

import anna
import core
from core import about, fmt

head, towns, crit, shel, flood, summary, qc = anna.load()
V = "worst"                                               # all satellite passes: closest to official 2021 figures
obs, mod = head[V]["observed"], head[V]["modelled_vesdre"]
T = towns[towns.variant == V].assign(no_shelter=lambda d: d.no_reach + d.full)
C = crit[crit.share_of_site_flooded.ge(.05) & crit.in_worst_flood.astype(bool)]
care = C[C.type.isin(["hospital", "care home"])]
DISTRICT = {"ahr": "Ahrweiler", "erftstadt": "Rhein-Erft", "schleiden": "Euskirchen"}
by_d = care.groupby(care.area.map(DISTRICT)).size().sort_values(ascending=False)
_, flow = core.load_brief()
lead = (flow.idxmax().max() - flow.idxmax().min()).days

st.html("""<style>
.act{background:#fff;border-radius:16px;padding:1.4rem 1.6rem;display:flex;gap:1rem;align-items:center}
.act i{flex:none;width:.9rem;height:.9rem;border-radius:50%;background:#d70015;box-shadow:0 0 0 5px #d7001522}
.act h1{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;line-height:1.15;margin:0;padding:0;color:#1d1d1f}
.act p{margin:.35rem 0 0;color:#6e6e73;font-size:1rem}
.big{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem}
.big div{background:#fff;border-radius:16px;padding:1.1rem 1.3rem}
.big b{display:block;font-size:2.6rem;font-weight:700;letter-spacing:-.03em;line-height:1;color:#1d1d1f;font-variant-numeric:tabular-nums}
.big span{display:block;margin-top:.4rem;color:#6e6e73;font-size:1rem}
.bars{background:#fff;border-radius:16px;padding:1rem 1.2rem}
.bars .r{display:grid;grid-template-columns:9.5rem 1fr 3.6rem;gap:.6rem;align-items:center;padding:.45rem 0}
.bars .n{font-weight:600;color:#1d1d1f;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bars .t{display:block;font-weight:400;color:#8e8e93;font-size:.78rem}
.bars .b{height:.7rem;border-radius:4px}
.bars .v{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;color:#1d1d1f}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem}
.steps div{background:#fff;border-radius:16px;padding:1rem 1.2rem}
.steps b{display:block;font-size:1.05rem;color:#1d1d1f}
.steps span{display:block;margin-top:.25rem;color:#6e6e73;font-size:.9rem}
.h2{font-size:1.15rem;font-weight:650;color:#1d1d1f;margin:0 0 .5rem .2rem}
@media (max-width:900px){.big,.steps{grid-template-columns:1fr}.act h1{font-size:1.5rem}}
</style>""")

# 1. the decision
st.html(f"<div class='act'><i></i><div><h1>Evacuate the {len(care)} hospitals and care homes in the flood zone first</h1>"
        f"<p>District crisis staffs: {' · '.join(f'{d} {n}' for d, n in by_d.items())}</p></div></div>")
st.space("small")

# 2. three numbers
st.html(f"<div class='big'><div><b>{about(obs['no_shelter'])}</b><span>people with no shelter place</span></div>"
        f"<div><b>{about(obs['full'])}</b><span>of them: shelter nearby, but full</span></div>"
        f"<div><b>{lead} day</b><span>warning from upstream to Venlo</span></div></div>")
st.space("small")

# 3. map + where
top = T.nlargest(5, "no_shelter").reset_index(drop=True)
left, right = st.columns([3, 2], gap="small")
with left:
    layers = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=False,
                        get_fill_color=[0, 113, 227, 40 if a in anna.MODELLED else 90]) for a in anna.AREA]
    layers.append(pdk.Layer("ScatterplotLayer", top.assign(
        r=lambda d: d.no_shelter ** .5 * .32 + 5,
        tip=lambda d: [f"<b>{x.label}</b><br>{fmt(x.no_shelter)} with no shelter place" for x in d.itertuples()]),
        get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'", get_fill_color=core.rgb(anna.TOO_FAR, 170),
        get_line_color=[255, 255, 255], line_width_min_pixels=1.5, stroked=True, pickable=True))
    layers.append(core.points(care.assign(tip=[f"<b>{n}</b><br>{t}" for n, t in zip(care.name, care.type)]),
                              core.rgb(core.EVACUATE), 6))
    # scroll wheel must move the page, not zoom the map (the +/- buttons still zoom)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(longitude=6.35, latitude=50.62, zoom=7.7),
                             views=[pdk.View(type="MapView", controller={"scrollZoom": False})],
                             map_style=pdk.map_styles.CARTO_LIGHT,
                             tooltip={"html": "{tip}", "style": {"backgroundColor": "#1d1d1f", "color": "#fff",
                                                                 "fontSize": "13px", "borderRadius": "8px"}}), height=420)
    core.legend(core.swatch(anna.TOO_FAR, "No shelter place", True) + core.swatch(core.EVACUATE, "Hospital / care home", True)
                + core.swatch("rgba(0,113,227,.35)", "2021 water"))
with right:
    mx = top.no_shelter.max()
    rows = "".join(f"<div class='r'><div class='n'>{r.label.replace(' (modelled)', ' *')}"
                   f"<span class='t'>{'shelters full' if r.full >= r.no_reach else 'too far to walk'}</span></div>"
                   f"<div class='b' style='width:{max(4, 100 * r.no_shelter / mx):.0f}%;background:"
                   f"{anna.FULL if r.full >= r.no_reach else anna.TOO_FAR}'></div><div class='v'>{about(r.no_shelter)}</div></div>"
                   for r in top.itertuples())
    st.html(f"<div class='h2'>Where</div><div class='bars'>{rows}</div>"
            "<p class='asof'>* modelled: the satellite missed the Vesdre valley</p>")
st.space("small")

# 4. next steps
full = T[T.full >= T.no_reach].nlargest(3, "full")
far = T[T.no_reach > T.full].nlargest(2, "no_reach")
short = lambda d: ", ".join(d.label.str.replace(" (modelled)", " *"))
st.html("<div class='h2'>Then</div><div class='steps'>"
        f"<div><b>Overflow space</b><span>{short(full)}</span></div>"
        f"<div><b>Buses</b><span>{short(far)}</span></div>"
        f"<div><b>Plan who goes where</b><span>+{about(obs['coordination_gain'])} people sheltered</span></div></div>")
st.space("small")

# 5. the honest answer to "better prepared?", then the detail on demand
core.group([("<b>Better prepared than 2021?</b>", "", "Not verified yet")])
with st.expander("Why these numbers"):
    st.markdown(
        f"- **Space, not distance:** {about(obs['full'])} of {about(obs['no_shelter'])} people have a shelter within "
        "1.5 km, but it is full (4 m² per person, half the floor usable).\n"
        f"- **Range:** {about(obs['no_shelter_range'][0])} to {about(obs['no_shelter_range'][1])} with stricter or "
        "looser assumptions.\n"
        f"- **Vesdre (modelled):** {about(mod['no_shelter'])} more; the satellite map has no flood there.\n"
        f"- **Hospitals and care homes:** at least 5 % of the site was under water in July 2021.\n"
        f"- **People in the flood zone:** {about(obs['people'])} in 2020, {about(obs['people_2025'])} in 2025 "
        "(projection): no drop.\n"
        "- **Sources and checks:** Data & limits.")
