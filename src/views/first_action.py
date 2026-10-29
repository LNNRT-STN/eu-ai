"""Home page for Anna, in order of importance:
  1 Do now   evacuate the hospitals and care homes in the 2021 water: per district, in order, and where to take them
  2 Next     people with no shelter place within walking distance, and the empty places 2-10 km away
  3 Context  warning time, 'better prepared?', how the numbers were made
Numbers come from outputs/data/ (notebooks/pipeline.py, q4_ranking.py, receiving.py) and src/out/meuse/replay_2021.json."""
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import about, fmt

head, towns, crit, shel, flood, summary, qc = anna.load()
recv, bus = anna.load_moves()
V = "worst"                                               # all satellite passes: closest to official 2021 figures
obs, mod = head[V]["observed"], head[V]["modelled_vesdre"]
T = towns[towns.variant == V].assign(no_shelter=lambda d: d.no_reach + d.full)
C = crit[crit.share_of_site_flooded.ge(.05) & crit.in_worst_flood.astype(bool)]
care = C[C.type.isin(["hospital", "care home"])]
DISTRICT = {"ahr": "Ahrweiler", "erftstadt": "Rhein-Erft", "schleiden": "Euskirchen"}
by_d = care.groupby(care.area.map(DISTRICT)).size().sort_values(ascending=False)
_, flow = core.load_brief()
lead = (flow.idxmax().max() - flow.idxmax().min()).days
MAP_H = 480
TIP = {"html": "<b>{tname}</b><br/>{tinfo}",
       "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}}
WATER = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=True, line_width_min_pixels=1,
                   get_fill_color=[0, 113, 227, 70 if a in anna.MODELLED else 140], get_line_color=[0, 90, 200, 200])
         for a in anna.AREA]
GREEN = core.rgb(core.SHELTER)

st.html("""<style>
.act{background:#fff;border-radius:16px;padding:1.1rem 1.4rem;display:flex;gap:1rem;align-items:center}
.act i{flex:none;width:.9rem;height:.9rem;border-radius:50%;background:#d70015;box-shadow:0 0 0 5px #d7001522}
.act.next i{background:#8e8e93;box-shadow:0 0 0 5px #8e8e9322}
.act h1{font-size:1.35rem;font-weight:700;letter-spacing:-.02em;line-height:1.2;margin:0;padding:0;color:#1d1d1f}
.act p{margin:.3rem 0 0;color:#6e6e73;font-size:.98rem}
.act p b{color:#1d1d1f}
.bars{background:#fff;border-radius:16px;padding:1rem 1.2rem}
.bars .r{display:grid;grid-template-columns:9.5rem 1fr 3.6rem;gap:.6rem;align-items:center;padding:.45rem 0}
.bars .n{font-weight:600;color:#1d1d1f;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bars .t{display:block;font-weight:400;color:#8e8e93;font-size:.78rem}
.bars .v{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;color:#1d1d1f}
.bars .cap{font-size:.8rem;font-weight:600;color:#6e6e73;margin:0 0 .3rem}
.one b{display:block;font-size:2.2rem;font-weight:700;letter-spacing:-.03em;line-height:1.05;color:#1d1d1f}
.one span{display:block;margin-top:.3rem;color:#6e6e73;font-size:.95rem}
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-top:.6rem}
.trio div{background:#f2f2f7;border-radius:10px;padding:.5rem .7rem}
.trio b{display:block;font-size:1.25rem;font-weight:700;color:#1d1d1f;font-variant-numeric:tabular-nums}
.trio span{display:block;font-size:.75rem;color:#6e6e73}
.dc{background:#fff;border-radius:16px;padding:1rem 1.2rem;border:2px solid transparent;transition:border-color .15s}
.dc b{display:block;font-size:2.2rem;font-weight:700;letter-spacing:-.03em;line-height:1;color:#d70015}
.dc h3{font-size:1.05rem;font-weight:650;margin:.35rem 0 0;padding:0;color:#1d1d1f}
.dc span{display:block;margin-top:.2rem;color:#6e6e73;font-size:.88rem}
.dc.on{border-color:#d70015}
[class*=st-key-dcard-]{position:relative;gap:0}
[class*=st-key-dcard-] [data-testid=stElementContainer]:has(button){position:absolute;inset:0;margin:0;width:100%!important;height:100%}
[class*=st-key-dcard-] [data-testid=stButton],[class*=st-key-dcard-] [data-testid=stButton]>*{width:100%;height:100%}
[class*=st-key-dcard-] [data-testid=stButton] button{width:100%;height:100%;opacity:0;cursor:pointer}
[class*=st-key-dcard-]:hover .dc{border-color:#d7001555}
@media (max-width:900px){.act h1{font-size:1.2rem}.trio{grid-template-columns:1fr}}
</style>""")


def evac_order(d):
    """Most of the site under water first; on a tie, hospitals before care homes."""
    d = (d.assign(_h=lambda x: (x.type != "hospital").astype(int))
         .sort_values(["share_of_site_flooded", "_h", "name"], ascending=[False, True, True])
         .drop(columns="_h").reset_index(drop=True))
    d.insert(0, "order", range(1, len(d) + 1))
    return d


def picked_row(key):
    """Row index the user ticked in a dataframe on the previous run, or None."""
    try:
        r = list(st.session_state[key]["selection"]["rows"])
        return r[0] if r else None
    except Exception:
        return None


def deck(layers, view):
    # scroll wheel must move the page, not zoom the map (the +/- buttons still zoom)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.CARTO_LIGHT,
                             views=[pdk.View(type="MapView", controller={"scrollZoom": False})], tooltip=TIP),
                    height=MAP_H)


def ring(lon, lat):
    return pdk.Layer("ScatterplotLayer", pd.DataFrame([{"lon": lon, "lat": lat}]), get_position=["lon", "lat"],
                     get_radius=17, radius_units="'pixels'", filled=False, stroked=True,
                     get_line_color=[29, 29, 31], line_width_min_pixels=3)


def fit(df):
    """Centre and zoom so every point in df is in view."""
    spread = core.km(df.lon.mean(), df.lat.mean(), df.lon, df.lat).max()
    z = 14 if spread < .7 else 13 if spread < 1.5 else 12 if spread < 4 else 11 if spread < 8 else 10 if spread < 16 else 9
    return pdk.ViewState(longitude=df.lon.mean(), latitude=df.lat.mean(), zoom=z)


# =============================================================================== 1 · DO NOW
st.html(f"<div class='act'><i></i><div><h1>Do now: evacuate the {len(care)} hospitals and care homes in the flood zone"
        "</h1><p>Pick a district: its sites in evacuation order, and the nearest dry hospitals and care homes."
        "</p></div></div>")
st.space("small")
st.session_state.setdefault("district", None)


def pick_district(d):
    st.session_state.district = None if st.session_state.district == d else d
    st.session_state.v1 = st.session_state.get("v1", 0) + 1          # reset the site list selection


cards = st.columns(len(by_d), gap="small")
for col, (d, n) in zip(cards, by_d.items()):
    in_d = care[care.area.map(DISTRICT) == d].town.value_counts()
    with col, st.container(key=f"dcard-{d}"):
        st.html(f"<div class='dc{' on' if st.session_state.district == d else ''}'><b>{n}</b>"
                f"<h3>{d} district crisis staff</h3><span>{' · '.join(f'{t} {k}' for t, k in in_d.items())}</span></div>")
        st.button(f"Show {d}", key=f"dbtn-{d}", on_click=pick_district, args=(d,))
st.space("small")

dist = st.session_state.district
sites = evac_order(care[care.area.map(DISTRICT) == dist] if dist else care)
sites["district"] = sites.area.map(DISTRICT)
all1 = st.session_state.get(f"all1-{dist}", False)
k1 = f"sites-{dist}-{st.session_state.get('v1', 0)}-{all1}"
i1 = picked_row(k1)
site = sites.iloc[i1] if i1 is not None and i1 < len(sites) else None
dest = recv[recv.from_name == site["name"]] if site is not None else recv.iloc[0:0]

left, right = st.columns([3, 2], gap="small")
with left:
    pts = sites.assign(tname=[f"{o}. {n}" for o, n in zip(sites.order, sites.name)],
                       tinfo=[f"{t} · {w} · {s:.0%} of the site under water"
                              for t, w, s in zip(sites.type, sites.town, sites.share_of_site_flooded)])
    layers = WATER + [core.points(pts, core.rgb(core.EVACUATE), 7)]
    if site is not None:
        legs = dest.assign(flon=site.lon, flat=site.lat, tname=dest.to_name,
                           tinfo=[f"dry {t} · {k} km" for t, k in zip(dest.type, dest.km)])
        layers += [pdk.Layer("LineLayer", legs, get_source_position=["flon", "flat"], get_target_position=["lon", "lat"],
                             get_color=[36, 138, 61, 200], get_width=3, width_units="'pixels'"),
                   pdk.Layer("ScatterplotLayer", legs, get_position=["lon", "lat"], get_radius=9, radius_units="'pixels'",
                             get_fill_color=GREEN, get_line_color=[255, 255, 255], line_width_min_pixels=2,
                             stroked=True, pickable=True),
                   ring(site.lon, site.lat)]
        view = fit(pd.concat([dest[["lon", "lat"]], pd.DataFrame([{"lon": site.lon, "lat": site.lat}])]))
    else:
        view = fit(sites) if dist else pdk.ViewState(longitude=6.75, latitude=50.62, zoom=8.6)
    deck(layers, view)
    core.legend(("" if site is None else f"<b>◯ {site.order}. {site['name']}</b> · {site.town} · "
                 f"{site.share_of_site_flooded:.0%} of the site under water<br>")
                + core.swatch(core.EVACUATE, "Hospital / care home to evacuate", True)
                + (core.swatch(core.SHELTER, "Nearest dry site of the same kind", True) if site is not None else "")
                + core.swatch("rgba(0,113,227,.55)", "2021 water"))
with right:
    head_txt = f"{dist} district crisis staff" if dist else "All three districts"
    st.html(f"<div class='bars'><div class='cap'>{head_txt}</div><div class='one'><b>{len(sites)} sites</b>"
            "<span>to evacuate, in this order · click one to see the nearest dry sites</span></div></div>")
    cols = ["order", "name", "town", "pct"] if dist else ["order", "name", "district", "pct"]
    shown1 = sites if all1 else sites.head(3)
    h_list = 36 * len(shown1) + 38
    st.dataframe(shown1.assign(pct=shown1.share_of_site_flooded * 100)[cols], key=k1, on_select="rerun",
                 selection_mode="single-row", hide_index=True, height=h_list, column_config={
                     "order": st.column_config.NumberColumn("#", width=40),
                     "name": st.column_config.TextColumn("Site", width="medium"),
                     "town": st.column_config.TextColumn("Town", width="small"),
                     "district": st.column_config.TextColumn("District", width="small"),
                     "pct": st.column_config.NumberColumn("Under water", format="%d%%", width="small")})
    if len(sites) > 3:
        st.toggle(f"Show all {len(sites)} sites", key=f"all1-{dist}")
    if site is not None:
        rows = "".join(f"<div class='r' style='grid-template-columns:1fr auto'><div class='n' style='white-space:normal'>"
                       f"{r.to_name}<span class='t'>dry {r.type}</span></div><div class='v'>{r.km:.1f} km</div></div>"
                       for r in dest.itertuples())
        st.html(f"<div class='bars'><div class='cap'>Nearest dry sites of the same kind</div>"
                f"{rows or 'No dry site of the same kind within 30 km'}</div>")
    st.html("<p class='asof'>Order: most of the site under water first, hospitals before care homes. Free beds and "
            "residents are not in any dataset: confirm with each operator.</p>")
st.space("medium")

# =============================================================================== 2 · NEXT
bus_more = obs["bus_covered"] - obs["sheltered"]
st.html(f"<div class='act next'><i></i><div><h1>Next: shelters within walking distance are full, but there are "
        "empty places 2–10 km away</h1>"
        f"<p>{about(obs['no_shelter'])} people would have no shelter place within 1.5 km on foot. "
        f"<b>Shelters 2–10 km away have empty places for {about(bus_more)} of them</b>; "
        f"{about(obs['bus_no_shelter'])} would have no place within 10 km. Pick a town to see where the empty places "
        "are.</p></div></div>")
st.space("small")

top = T.nlargest(5, "no_shelter").reset_index(drop=True)
top["short"] = top.label.str.replace(" (modelled)", " *")
top["by_bus"] = (top.bus_covered.fillna(top.covered) - top.covered).clip(lower=0)
top["left"] = (top.people - top.bus_covered.fillna(top.covered)).clip(lower=0)
st.session_state.setdefault("town", "All")
pick = st.pills("Town", ["All", *top.short], label_visibility="collapsed", key="town")
sel = None if pick in (None, "All") else top[top.short == pick].iloc[0]
plan = (bus[(bus.town == sel["name"]) & (bus.area == sel.area)].sort_values("people", ascending=False)
        .reset_index(drop=True) if sel is not None else bus.iloc[0:0])
all2 = st.session_state.get(f"all2-{pick}", False)
k2 = f"bus-{pick}-{all2}"
i2 = picked_row(k2)
stop = plan.iloc[i2] if i2 is not None and i2 < len(plan) else None

left, right = st.columns([3, 2], gap="small")
with left:
    layers = list(WATER)
    if sel is None:
        circ = top.assign(r=lambda d: d.no_shelter ** .5 * .32 + 6, tname=top.label,
                          tinfo=[f"{fmt(n)} with no shelter place on foot · {fmt(b)} could find one 2–10 km away"
                                 for n, b in zip(top.no_shelter, top.by_bus)],
                          txt=[f"{s}  {about(n)}" for s, n in zip(top.short, top.no_shelter)])
        west = [((core.km(x.lon, x.lat, top.lon, top.lat) < 15) & (top.lon > x.lon)).any() for x in circ.itertuples()]
        circ["off"] = [[0, -(r + 12)] if w else [0, r + 12] for r, w in zip(circ.r, west)]
        layers += [pdk.Layer("ScatterplotLayer", circ, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                             get_fill_color=core.rgb(core.EVACUATE, 190), get_line_color=[255, 255, 255],
                             line_width_min_pixels=2, stroked=True, pickable=True),
                   pdk.Layer("TextLayer", circ, get_position=["lon", "lat"], get_text="txt", get_size=13,
                             get_color=[29, 29, 31], get_pixel_offset="off", get_alignment_baseline="'center'",
                             background=True, get_background_color=[255, 255, 255, 235], background_padding=[5, 3])]
        view = pdk.ViewState(longitude=6.35, latitude=50.62, zoom=7.7)
    else:
        legs = plan.rename(columns={"s_lon": "lon", "s_lat": "lat"}).assign(
            tlon=sel.lon, tlat=sel.lat, tname=plan.shelter,
            tinfo=[f"{c} · room for {about(p)} people from {sel['name']} · ≈ {about(pl)} places in all"
                   for c, p, pl in zip(plan.cat, plan.people, plan.places)],
            r=lambda d: d.people ** .5 * .6 + 4)
        town_pt = pd.DataFrame([{"lon": sel.lon, "lat": sel.lat, "tname": sel.label,
                                 "tinfo": f"{fmt(sel.no_shelter)} with no shelter place on foot"}])
        # faint grey lines to the 10 biggest destinations; the picked one is drawn bold green below (one at a time)
        layers += [pdk.Layer("LineLayer", legs.head(10), get_source_position=["tlon", "tlat"],
                             get_target_position=["lon", "lat"], get_color=[142, 142, 147, 90], get_width=1.5,
                             width_units="'pixels'"),
                   pdk.Layer("ScatterplotLayer", legs, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                             get_fill_color=GREEN, get_line_color=[255, 255, 255], line_width_min_pixels=1.5,
                             stroked=True, pickable=True),
                   pdk.Layer("ScatterplotLayer", town_pt, get_position=["lon", "lat"], get_radius=11,
                             radius_units="'pixels'", get_fill_color=core.rgb(core.EVACUATE), get_line_color=[255, 255, 255],
                             line_width_min_pixels=2, stroked=True, pickable=True)]
        if stop is not None:
            one = pd.DataFrame([{"tlon": sel.lon, "tlat": sel.lat, "lon": stop.s_lon, "lat": stop.s_lat}])
            layers += [pdk.Layer("LineLayer", one, get_source_position=["tlon", "tlat"], get_target_position=["lon", "lat"],
                                 get_color=[36, 138, 61, 230], get_width=4, width_units="'pixels'"),
                       ring(stop.s_lon, stop.s_lat)]
            view = fit(pd.DataFrame([{"lon": sel.lon, "lat": sel.lat}, {"lon": stop.s_lon, "lat": stop.s_lat}]))  # town and shelter both in view
        else:
            view = fit(pd.concat([legs[["lon", "lat"]], town_pt[["lon", "lat"]]]))
    deck(layers, view)
    if sel is None:
        core.legend(core.swatch(core.EVACUATE, "People with no shelter place on foot (circle size)", True)
                    + core.swatch("rgba(0,113,227,.55)", "2021 water"))
    else:
        core.legend(("" if stop is None else f"<b>◯ {stop.shelter}</b> · {stop['cat']} · {about(stop.people)} people "
                     f"from {sel['name']} · ≈ {about(stop.places)} places<br>")
                    + core.swatch(core.EVACUATE, sel.label, True)
                    + core.swatch(core.SHELTER, "Shelter with empty places within 10 km (size = people)", True)
                    + core.swatch("rgba(0,113,227,.55)", "2021 water"))
with right:
    if sel is None:
        mx = top.people.max()
        bars = "".join(f"<div class='r'><div class='n'>{r.short}<span class='t'>{about(r.left)} no place within 10 km"
                       f"</span></div><div style='display:flex;height:.7rem;border-radius:4px;overflow:hidden;"
                       f"background:#f2f2f7'><i style='width:{100 * r.covered / mx:.0f}%;background:#c7c7cc'></i>"
                       f"<i style='width:{100 * r.by_bus / mx:.0f}%;background:{core.SHELTER}'></i>"
                       f"<i style='width:{100 * r.left / mx:.0f}%;background:{core.EVACUATE}'></i></div>"
                       f"<div class='v'>{about(r.no_shelter)}</div></div>" for r in top.itertuples())
        st.html(f"<div class='bars'><div class='cap'>People with no shelter place on foot</div>{bars}</div>")
        core.legend(core.swatch("#c7c7cc", "Place within 1.5 km") + core.swatch(core.SHELTER, "Empty place 2–10 km away")
                    + core.swatch(core.EVACUATE, "No place within 10 km"))
        st.html("<p class='asof'>* modelled: the satellite missed the Vesdre valley</p>")
    else:
        st.html(f"<div class='bars'><div class='cap'>{sel.label}</div><div class='one'><b>{about(sel.no_shelter)}</b>"
                "<span>with no shelter place on foot</span></div><div class='trio'>"
                f"<div><b>{about(sel.covered)}</b><span>place within 1.5 km</span></div>"
                f"<div><b style='color:{core.SHELTER}'>{about(sel.by_bus)}</b><span>empty place 2–10 km away</span></div>"
                f"<div><b style='color:{core.EVACUATE}'>{about(sel.left)}</b><span>no place within 10 km</span></div>"
                "</div></div>")
        shown2 = plan if all2 else plan.head(3)
        st.dataframe(shown2.assign(p=shown2.people.round())[["shelter", "p"]], key=k2, on_select="rerun",
                     selection_mode="single-row", hide_index=True, height=36 * len(shown2) + 40,
                     column_config={"shelter": st.column_config.TextColumn("Shelter with empty places", width="medium"),
                                    "p": st.column_config.NumberColumn("People", format="localized", width="small")})
        if len(plan) > 3:
            st.toggle(f"Show all {len(plan)} shelters", key=f"all2-{pick}")
        st.html("<p class='asof'>Click a shelter to find it. Up to 10 km in a straight line, 4 m² per person, half the "
                "floor usable. Places are estimates.</p>")
st.space("medium")

# =============================================================================== 3 · CONTEXT
core.group([
    ("<b>Warning time</b>", f"In the July 2021 replay, Maastricht to Venlo peaked {lead} day after the Vesdre and Liège.",
     f"{lead} day"),
    ("<b>Better prepared than 2021?</b>", "What changed since 2021 is still being verified.", "Not verified yet"),
], "Context")
with st.expander("Why these numbers"):
    st.markdown(
        f"- **No place on foot:** {about(obs['no_shelter'])} people where the satellite saw the 2021 water; "
        f"{about(obs['full'])} of them have a shelter within 1.5 km, but it is full (4 m² per person, half the floor "
        f"usable). Range {about(obs['no_shelter_range'][0])} to {about(obs['no_shelter_range'][1])} with stricter or "
        "looser assumptions.\n"
        f"- **Within 10 km:** the same shelters, up to 10 km away in a straight line, have empty places for "
        f"{about(bus_more)} of them.\n"
        f"- **Vesdre (modelled):** {about(mod['no_shelter'])} more people with no place on foot; the satellite map has "
        "no flood there.\n"
        "- **Hospitals and care homes:** at least 5 % of the site under water in July 2021. Receiving sites: the nearest "
        "OpenStreetMap hospitals or care homes that were dry in 2021 and in the 100-year model; free beds unknown.\n"
        f"- **People in the flood zone:** {about(obs['people'])} in 2020, {about(obs['people_2025'])} in 2025 "
        "(projection).\n"
        "- **Sources and checks:** Data & limits.")
