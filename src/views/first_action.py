"""Home page for Anna: one decision, three numbers, one map, three next steps. Few words; detail behind 'Why'.
Numbers come from outputs/data/ (notebooks/pipeline.py, q4_ranking.py) and src/out/meuse/replay_2021.json."""
import pandas as pd
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
.bars .cap{font-size:.8rem;font-weight:600;color:#6e6e73;margin:0 0 .3rem}
.one b{display:block;font-size:2.4rem;font-weight:700;letter-spacing:-.03em;line-height:1.05;color:#1d1d1f}
.one span{display:block;margin-top:.3rem;color:#6e6e73;font-size:.95rem}
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

# 3. map + where. Town buttons span the full width so the map and the side panel start on the same line.
MAP_H = 500
top = T.nlargest(5, "no_shelter").reset_index(drop=True)
top["short"] = top.label.str.replace(" (modelled)", " *")
top["why"] = ["full" if f >= n else "far" for f, n in zip(top.full, top.no_reach)]
pick = st.pills("Town", ["All", *top.short], default="All", label_visibility="collapsed")
sel = None if pick in (None, "All") else top[top.short == pick].iloc[0]

focus = None                                   # the site or shelter clicked in a list, shown on the map
if sel is not None:
    # evacuation order: most of the site under water first; on a tie, hospitals before care homes
    sites = (care[(care.town == sel["name"]) & (care.area == sel.area)]
             .assign(_h=lambda d: (d.type != "hospital").astype(int))
             .sort_values(["share_of_site_flooded", "_h", "name"], ascending=[False, True, True])
             .drop(columns="_h").reset_index(drop=True))
    sites.insert(0, "order", range(1, len(sites) + 1))
    near = shel[shel.area == sel.area].assign(km=lambda d: core.km(sel.lon, sel.lat, d.lon, d.lat))
    near = near[near.km <= 6].sort_values("capacity_central", ascending=False).reset_index(drop=True)
    near["label"] = [n if isinstance(n, str) else f"Unnamed {c}" for n, c in zip(near.name, near.cat)]
    # one selection at a time: clicking in one list resets the other (its key gets a new version)
    ver = st.session_state.setdefault("ver", {"evac": 0, "shel": 0})
    kE, kS = f"evac-{pick}-{ver['evac']}", f"shel-{pick}-{ver['shel']}"

    def rows(key):
        try:
            return list(st.session_state[key]["selection"]["rows"])
        except Exception:
            return []

    def clicked(key, kind):
        r = rows(key)
        st.session_state["focus"] = (pick, kind, r[0]) if r else None
        if r:
            other = "shel" if kind == "evac" else "evac"
            st.session_state["ver"][other] += 1

    f = st.session_state.get("focus")
    if f and f[0] == pick:
        src = sites if f[1] == "evac" else near
        if f[2] < len(src):
            focus = src.iloc[f[2]].copy()
            focus["kind"] = f[1]

left, right = st.columns([3, 2], gap="small")
with left:
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
        pts["off"] = [[0, -(r + 12)] if w else [0, r + 12] for r, w in zip(pts.r, west)]
        layers += [pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                             get_fill_color="fill", get_line_color=[255, 255, 255], line_width_min_pixels=2,
                             stroked=True, pickable=True),
                   core.points(care.assign(tname=care.name, tinfo=[f"{t} in the 2021 water" for t in care.type]),
                               core.rgb(core.EVACUATE), 5),
                   pdk.Layer("TextLayer", pts, get_position=["lon", "lat"], get_text="txt", get_size=13,
                             get_color=[29, 29, 31], get_pixel_offset="off", get_alignment_baseline="'center'",
                             background=True, get_background_color=[255, 255, 255, 235], background_padding=[5, 3])]
        view = pdk.ViewState(longitude=6.35, latitude=50.62, zoom=7.7)
    else:
        # one town: dry shelters (green, size = places) and flooded care sites (red); a clicked name gets a ring + label
        shown = near.assign(r=lambda d: (d.capacity_central ** .5) * .5 + 3, tname=near.label,
                            tinfo=[f"{c} · ≈ {about(p)} places" for c, p in zip(near.cat, near.capacity_central)])
        mine = sites.assign(tname=sites.name, tinfo=[f"{t} · {s:.0%} of the site under water"
                                                    for t, s in zip(sites.type, sites.share_of_site_flooded)])
        layers += [pdk.Layer("ScatterplotLayer", shown, get_position=["lon", "lat"], get_radius="r",
                             radius_units="'pixels'", get_fill_color=core.rgb(core.SHELTER, 210),
                             get_line_color=[255, 255, 255], line_width_min_pixels=1, stroked=True, pickable=True),
                   core.points(mine, core.rgb(core.EVACUATE), 7)]
        if focus is not None:
            f1 = pd.DataFrame([{"lon": focus.lon, "lat": focus.lat,
                                "txt": focus["name"] if focus.kind == "evac" else focus.label}])
            layers += [pdk.Layer("ScatterplotLayer", f1, get_position=["lon", "lat"], get_radius=16, radius_units="'pixels'",
                                 filled=False, stroked=True, get_line_color=[29, 29, 31], line_width_min_pixels=3)]
            view = pdk.ViewState(longitude=focus.lon, latitude=focus.lat, zoom=15)
        else:
            c = sites if len(sites) else near.head(5)
            view = pdk.ViewState(longitude=c.lon.mean() if len(c) else sel.lon,
                                 latitude=c.lat.mean() if len(c) else sel.lat, zoom=12.6)
    # scroll wheel must move the page, not zoom the map (the +/- buttons still zoom)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.CARTO_LIGHT,
                             views=[pdk.View(type="MapView", controller={"scrollZoom": False})],
                             tooltip={"html": "<b>{tname}</b><br/>{tinfo}", "style": tipstyle}), height=MAP_H)
    if sel is None:
        core.legend(core.swatch(anna.FULL, "Shelters full", True) + core.swatch(anna.TOO_FAR, "Too far to walk", True)
                    + core.swatch(core.EVACUATE, "Hospital / care home", True) + core.swatch("rgba(0,113,227,.55)", "2021 water"))
    else:
        found = "" if focus is None else (f"<b>◯ {focus['name'] if focus.kind == 'evac' else focus.label}</b> · "
                 + (f"{focus.share_of_site_flooded:.0%} of the site under water" if focus.kind == "evac"
                    else f"≈ {about(focus.capacity_central)} places") + "<br>")
        core.legend(found + core.swatch(core.EVACUATE, "Evacuate first", True) + core.swatch(core.SHELTER, "Dry shelter (size = places)", True)
                    + core.swatch("rgba(0,113,227,.55)", "2021 water"))

with right:
    if sel is None:
        mx = top.no_shelter.max()
        bars = "".join(f"<div class='r'><div class='n'>{r.short}<span class='t'>"
                       f"{'shelters full' if r.why == 'full' else 'too far to walk'}</span></div>"
                       f"<div class='b' style='width:{max(4, 100 * r.no_shelter / mx):.0f}%;background:"
                       f"{anna.FULL if r.why == 'full' else anna.TOO_FAR}'></div><div class='v'>{about(r.no_shelter)}</div></div>"
                       for r in top.itertuples())
        st.html(f"<div class='bars'><div class='cap'>People with no shelter place</div>{bars}</div>"
                "<p class='asof'>* modelled: the satellite missed the Vesdre valley</p>")
    else:
        why = "shelters nearby are full" if sel.why == "full" else "no shelter within 1.5 km on foot"
        st.html(f"<div class='bars'><div class='cap'>{sel.label}</div><div class='one'><b>{about(sel.no_shelter)}</b>"
                f"<span>with no shelter place: {why}</span></div></div>")
        h_e = 36 * min(len(sites), 4) + 38 if len(sites) else 0
        if len(sites):
            st.dataframe(sites.assign(pct=sites.share_of_site_flooded * 100)[["order", "name", "pct"]], key=kE,
                         on_select=lambda: clicked(kE, "evac"), selection_mode="single-row", hide_index=True,
                         height=h_e, column_config={
                             "order": st.column_config.NumberColumn("#", width=40),
                             "name": st.column_config.TextColumn("Evacuate first", width="medium"),
                             "pct": st.column_config.NumberColumn("Under water", format="%d%%", width="small")})
        st.dataframe(near[["label", "capacity_central"]], key=kS, on_select=lambda: clicked(kS, "shel"),
                     selection_mode="single-row", hide_index=True, height=max(150, MAP_H - 130 - h_e),
                     column_config={"label": st.column_config.TextColumn("Dry shelters nearby", width="medium"),
                                    "capacity_central": st.column_config.NumberColumn("Places", format="localized",
                                                                                      width="small")})
        st.html("<p class='asof'>Click a name to find it on the map. Order: most of the site under water first, "
                "hospitals before care homes; confirm residents and mobility with each operator. Places are estimates.</p>")
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
