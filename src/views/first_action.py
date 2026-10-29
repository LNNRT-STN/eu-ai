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
FONT = "Arial"                                   # map labels: one plain sans every machine has
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
.lst .r{grid-template-columns:1fr auto}
.lst .n{white-space:normal}
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
top["short"] = top.label.str.replace(" (modelled)", " *")
top["why"] = ["full" if f >= n else "far" for f, n in zip(top.full, top.no_reach)]
left, right = st.columns([3, 2], gap="small")
with left:
    pick = st.pills("Town", ["All", *top.short], default="All", label_visibility="collapsed")
    sel = None if pick in (None, "All") else top[top.short == pick].iloc[0]
    color = lambda w, a=200: core.rgb(anna.FULL if w == "full" else anna.TOO_FAR, a)
    tipstyle = {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}
    layers = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=True, line_width_min_pixels=1,
                        get_fill_color=[0, 113, 227, 70 if a in anna.MODELLED else 140], get_line_color=[0, 90, 200, 200])
              for a in anna.AREA]
    if sel is None:
        # overview: one labelled circle per town, coloured by the reason (same colours as the bars)
        pts = top.assign(r=lambda d: d.no_shelter ** .5 * .32 + 6, fill=[color(w) for w in top.why],
                         txt=[f"{s}  {about(n)}" for s, n in zip(top.short, top.no_shelter)],
                         tname=top.label, tinfo=[f"{fmt(n)} people with no shelter place" for n in top.no_shelter])
        # label under its circle; when a neighbour within 15 km sits to the east, this one goes above, so they never touch
        west = [((core.km(x.lon, x.lat, top.lon, top.lat) < 15) & (top.lon > x.lon)).any() for x in pts.itertuples()]
        pts["anchor"] = "middle"
        pts["off"] = [[0, -(r + 12)] if w else [0, r + 12] for r, w in zip(pts.r, west)]
        layers += [pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                             get_fill_color="fill", get_line_color=[255, 255, 255], line_width_min_pixels=2,
                             stroked=True, pickable=True),
                   core.points(care.assign(tname=care.name, tinfo=[f"{t} in the 2021 water" for t in
                                                care.type]), core.rgb(core.EVACUATE), 5),
                   pdk.Layer("TextLayer", pts, get_position=["lon", "lat"], get_text="txt", get_size=13,
                             get_color=[29, 29, 31], get_pixel_offset="off", get_text_anchor="anchor",
                             get_alignment_baseline="'center'", background=True,
                             get_background_color=[255, 255, 255, 235], background_padding=[5, 3])]
        view = pdk.ViewState(longitude=6.35, latitude=50.62, zoom=7.7)
    else:
        # one town: its flooded area, the dry shelters around it (size = places) and its flooded care sites, named
        near = shel[shel.area == sel.area].assign(km=lambda d: core.km(sel.lon, sel.lat, d.lon, d.lat))
        near = near[near.km <= 6].assign(r=lambda d: (d.capacity_central ** .5) * .5 + 3,
                                         tname=lambda d: [n if isinstance(n, str) else c for n, c in zip(d.name, d.cat)],
                                         tinfo=lambda d: [f"≈ {about(p)} places" for p in d.capacity_central])
        here = care[(care.area == sel.area)].assign(tname=lambda d: d.name, tinfo=lambda d: [f"{t}, {s:.0%} of the site under water"
                                                                  for t, s in zip(d.type, d.share_of_site_flooded)])
        layers += [pdk.Layer("ScatterplotLayer", near, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                             get_fill_color=core.rgb(core.SHELTER, 210), get_line_color=[255, 255, 255],
                             line_width_min_pixels=1, stroked=True, pickable=True),
                   core.points(here, core.rgb(core.EVACUATE), 7)]
        # centre on the flooded sites when the town has some (the municipality's middle can sit outside the valley)
        mine = here[here.town == sel["name"]]
        view = pdk.ViewState(longitude=mine.lon.mean() if len(mine) else sel.lon,
                             latitude=mine.lat.mean() if len(mine) else sel.lat, zoom=12.6)
    # scroll wheel must move the page, not zoom the map (the +/- buttons still zoom)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.CARTO_LIGHT,
                             views=[pdk.View(type="MapView", controller={"scrollZoom": False})],
                             tooltip={"html": "<b>{tname}</b><br/>{tinfo}", "style": tipstyle}), height=440)
    if sel is None:
        core.legend(core.swatch(anna.FULL, "Shelters full", True) + core.swatch(anna.TOO_FAR, "Too far to walk", True)
                    + core.swatch(core.EVACUATE, "Hospital / care home", True) + core.swatch("rgba(0,113,227,.55)", "2021 water"))
    else:
        core.legend(f"<b>{sel.label}</b> · {fmt(sel.no_shelter)} with no shelter place"
                    + core.swatch(core.SHELTER, "Dry shelter (size = places)", True)
                    + core.swatch(core.EVACUATE, "Hospital / care home in the water", True)
                    + core.swatch("rgba(0,113,227,.55)", "2021 water"))
with right:
  if sel is not None:
    # one town: number, reason, its flooded care sites, its biggest dry shelters. Short lines only.
    why = "shelters nearby are full" if sel.why == "full" else "no shelter within 1.5 km on foot"
    sites = care[(care.town == sel["name"]) & (care.area == sel.area)]
    big = shel[(shel.area == sel.area) & (core.km(sel.lon, sel.lat, shel.lon, shel.lat) <= 6)].nlargest(3, "capacity_central")
    li = lambda rows: "".join(f"<div class='r'><div class='n'>{a}<span class='t'>{b}</span></div>"
                              f"<div class='v'>{c}</div></div>" for a, b, c in rows)
    st.html(f"<div class='h2'>{sel.label}</div><div class='big' style='grid-template-columns:1fr'><div>"
            f"<b>{about(sel.no_shelter)}</b><span>with no shelter place: {why}</span></div></div>"
            + (f"<div class='h2' style='margin-top:.8rem'>Evacuate first · % of site under water</div><div class='bars lst'>"
               + li((n, t, f"{s:.0%}") for n, t, s in zip(sites.name, sites.type, sites.share_of_site_flooded))
               + "</div>" if len(sites) else "")
            + "<div class='h2' style='margin-top:.8rem'>Biggest dry shelters · places</div><div class='bars lst'>"
            + li((n if isinstance(n, str) else c, c, f"{about(p)}") for n, c, p in
                 zip(big.name, big.cat, big.capacity_central)) + "</div><p class='asof'>Places are estimates; confirm with the commune.</p>")
  else:
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
