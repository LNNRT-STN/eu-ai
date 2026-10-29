"""Home page: the brief's three questions, answered in order, each with its evidence; maps open on demand.
  Hero        the answer in one sentence
  Prepared?   what changed since 2021 (Q2 desk research, src/measures.py)
  Exposed?    residents in the 2021 water and who has a candidate shelter within walking distance (Q1, Q3)
  First?      evacuate the hospitals and care homes in the 2021 water, per district, in order (Q4)
Numbers come from outputs/data/ (notebooks/pipeline.py, q4_ranking.py, receiving.py) and src/out/meuse/replay_2021.json."""
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import about, fmt
from measures import DONE, GAPS, MEASURES, STATUS, UNVERIFIED

head, towns, crit, shel, flood, summary, qc = anna.load()
recv, bus = anna.load_moves()
V = "worst"                                               # all satellite passes: closest to official 2021 figures
obs, mod = head[V]["observed"], head[V]["modelled_vesdre"]
T = towns[towns.variant == V].assign(no_shelter=lambda d: d.no_reach + d.full)
C = crit[crit.share_of_site_flooded.ge(.05) & crit.in_worst_flood.astype(bool)]
care = C[C.type.isin(["hospital", "care home"])]
schools = C[C.type == "school"]
DISTRICT = {"ahr": "Ahrweiler", "erftstadt": "Rhein-Erft", "schleiden": "Euskirchen"}
by_d = care.groupby(care.area.map(DISTRICT)).size().sort_values(ascending=False)
flow = core.load_replay()
lead = (flow.idxmax().max() - flow.idxmax().min()).days
far_more = obs["bus_covered"] - obs["sheltered"]
MAP_H = 480
TIP = {"html": "<b>{tname}</b><br/>{tinfo}",
       "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}}
WATER = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=True, line_width_min_pixels=1,
                   get_fill_color=[0, 113, 227, 70 if a in anna.MODELLED else 140], get_line_color=[0, 90, 200, 200])
         for a in anna.AREA]
GREEN = core.rgb(core.SHELTER)

st.html("""<style>
html{scroll-behavior:smooth}
.hero{padding:1.5rem 0 .5rem;max-width:60rem}
.hero h1{font-size:clamp(2.1rem,4.4vw,3.4rem);font-weight:700;letter-spacing:-.035em;line-height:1.06;margin:0;padding:0;
  color:#1d1d1f;text-wrap:balance}
.hero h1 span{color:#86868b}
.hero p{margin:1.1rem 0 0;color:#6e6e73;font-size:1.1rem;line-height:1.5;max-width:44rem}
.idx{background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,.04),0 6px 24px rgba(0,0,0,.05)}
.idx a{display:grid;grid-template-columns:11rem 1fr auto 1.4rem;gap:1rem;align-items:center;padding:1rem 1.3rem;
  text-decoration:none;color:inherit;position:relative;transition:background .15s}
.idx a+a::before{content:"";position:absolute;top:0;left:1.3rem;right:0;border-top:1px solid #e3e3e8}
.idx a:hover{background:#f7f7fa}
.idx .q{color:#6e6e73;font-size:.92rem}
.idx .a{color:#1d1d1f;font-size:1.02rem;font-weight:600;line-height:1.35}
.idx .a small{display:block;font-weight:400;color:#6e6e73;font-size:.88rem;margin-top:.15rem}
.idx .n{font-size:1.6rem;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;text-align:right;color:#1d1d1f}
.idx .chev{color:#c7c7cc;font-family:'Material Symbols Rounded';font-size:1.4rem}
.find{scroll-margin-top:4.5rem;margin:3.2rem 0 0;max-width:58rem}
.find h2{font-size:clamp(1.45rem,2.6vw,1.95rem);font-weight:700;letter-spacing:-.025em;line-height:1.18;margin:0;padding:0;
  color:#1d1d1f;text-wrap:balance}
.find h2 span{color:#86868b}
.find p{margin:.6rem 0 0;color:#6e6e73;font-size:1rem;line-height:1.5;max-width:46rem}
.stat{background:#fff;border-radius:16px;padding:1.1rem 1.3rem}
.stat .bar{display:flex;gap:2px;height:.85rem;border-radius:5px;overflow:hidden}
.stat .lab{display:flex;flex-wrap:wrap;gap:.3rem 1.4rem;margin-top:.7rem;font-size:.88rem;color:#6e6e73}
.stat .lab b{color:#1d1d1f;font-variant-numeric:tabular-nums;margin-right:.3rem}
.stat .lab i{display:inline-block;width:.7rem;height:.7rem;border-radius:3px;margin-right:.4rem;vertical-align:-.05em}
.bars{background:#fff;border-radius:16px;padding:1rem 1.2rem}
.bars .r{display:grid;grid-template-columns:9.5rem 1fr 3.6rem;gap:.6rem;align-items:center;padding:.45rem 0}
.bars .n{font-weight:600;color:#1d1d1f;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bars .t{display:block;font-weight:400;color:#8e8e93;font-size:.78rem}
.bars .v{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;color:#1d1d1f}
.bars.wide .r{grid-template-columns:13rem 1fr 3.6rem}
.group a{color:#0071e3;text-decoration:none}
.group a:hover{text-decoration:underline;text-underline-offset:2px}
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
@media (max-width:900px){.idx a{grid-template-columns:1fr auto;gap:.2rem .8rem}.idx .q{grid-column:1/-1}.idx .chev{display:none}
  .trio{grid-template-columns:1fr}}
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


def flip(key):
    st.session_state[key] = not st.session_state.get(key, False)


def finding(anchor, question, answer, sub=""):
    """Section heading that states the finding (the question in grey first), like Our World in Data's key insights."""
    st.html(f"<section class='find' id='{anchor}'><h2><span>{question}</span> {answer}</h2>"
            + (f"<p>{sub}</p>" if sub else "") + "</section>")


# ============================================================================================ the answer, in one line
status_n = pd.Series([m[4] for m in MEASURES]).value_counts().reindex(list(STATUS), fill_value=0)
st.html(f"<div class='hero'><h1>Partly better prepared. <span>Start with the {len(care)} hospitals and care homes "
        f"that sat in the 2021 water.</span></h1><p>Are we better prepared than in 2021, where are we still exposed, "
        "and what is the first action? The three answers, each with its evidence below.</p></div>")
st.space("small")
st.html("<nav class='idx'>"
        f"<a href='#prepared'><span class='q'>Better prepared?</span><span class='a'>Partly<small>Repairs are done; "
        f"most new protection is still being built</small></span><span class='n'>{status_n[DONE]} of {len(MEASURES)}"
        "</span><span class='chev' aria-hidden='true'>chevron_right</span></a>"
        f"<a href='#exposed'><span class='q'>Still exposed?</span><span class='a'>{about(obs['people'])} residents in "
        f"the 2021 water<small>{about(obs['no_shelter'])} of them with no shelter place within walking distance"
        f"</small></span><span class='n'>{about(obs['no_shelter'])}</span>"
        "<span class='chev' aria-hidden='true'>chevron_right</span></a>"
        f"<a href='#first'><span class='q'>First action?</span><span class='a'>Evacuate the hospitals and care homes "
        f"in the 2021 water<small>{len(by_d)} districts: {', '.join(by_d.index)}</small></span>"
        f"<span class='n'>{len(care)}</span><span class='chev' aria-hidden='true'>chevron_right</span></a>"
        "</nav>")
st.html("<p class='asof'>Numbers: measures done of measures found · people with no shelter place within 1.5 km · "
        "sites to evacuate</p>")

# ============================================================================================ 1 · better prepared?
finding("prepared", "Better prepared?", "Partly. The 2021 damage is repaired; most new protection is still being built.",
        f"Desk research, October 2026: {len(MEASURES)} measures found in official, water-authority and press "
        "sources. Status is what the source reports, not checked on the ground.")
st.space("small")
st.html("<div class='stat'><div class='bar'>"
        + "".join(f"<i style='flex:{n};background:{STATUS[s]}' title='{s}: {n}'></i>" for s, n in status_n.items() if n)
        + "</div><div class='lab'>"
        + "".join(f"<span><i style='background:{STATUS[s]}'></i><b>{n}</b>{s.lower()}</span>" for s, n in status_n.items())
        + "</div></div>")
st.space("small")
pill = lambda s: f"<span class='pill' style='background:{STATUS[s]};color:{core.ink(STATUS[s])}'>{s}</span>"
# the biggest structural work per river, then the gaps that matter for the first action
key_works = [next(m for m in MEASURES if m[0].startswith(r) and m[1] == "Defences" and m[4] != DONE)
             for r in ("Vesdre", "Limburg", "Inde")]
core.group([(f"<b>{area}</b>", f"{what} <a href='{url}' target='_blank'>{src}</a>", pill(s))
            for area, _, what, _, s, src, url in key_works]
           + [(f"<b>{t}</b>", d, pill(UNVERIFIED)) for t, d in (GAPS[0], GAPS[5])],
           "The big works, and what we could not find")
st.page_link("views/then_now.py", label=f"All {len(MEASURES)} measures and their sources", icon=":material/arrow_forward:")

# ============================================================================================ 2 · still exposed?
finding("exposed", "Still exposed?", f"{about(obs['people'])} residents lived in the 2021 water. "
        f"{about(obs['no_shelter'])} of them would have no shelter place within walking distance.",
        f"Candidate shelters are schools, sports halls and civic buildings that stayed dry. {about(obs['full'])} of the "
        f"{about(obs['no_shelter'])} have one within 1.5 km, but it is full. Candidates 2–10 km away have empty places "
        f"for {about(far_more)} more. {len(schools)} schools sat in the water themselves.")
st.space("small")
top = T.nlargest(5, "no_shelter").reset_index(drop=True)
top["short"] = top.label.str.replace(" (modelled)", " *")
mx = top.people.max()
bars = "".join(f"<div class='r'><div class='n'>{r.short}<span class='t'>{about(r.covered)} of {about(r.people)} "
               f"have one</span></div><div style='display:flex;height:.7rem;border-radius:4px;overflow:hidden;"
               f"background:#f2f2f7'><i style='width:{100 * r.covered / mx:.0f}%;background:{core.SHELTER}'></i>"
               f"<i style='width:{100 * r.no_shelter / mx:.0f}%;background:{core.EVACUATE}'></i></div>"
               f"<div class='v'>{about(r.no_shelter)}</div></div>" for r in top.itertuples())
bars_cap = "Five towns with the most residents without a shelter place within 1.5 km"
bars_key = (core.swatch(core.SHELTER, "Has a place") + core.swatch(core.EVACUATE, "No place (number)")
            + "<span>* modelled: the satellite missed the Vesdre valley</span>")
if not st.session_state.get("map2"):
    st.html(f"<div class='bars wide'><div class='cap'>{bars_cap}</div>{bars}</div>")
    core.legend(bars_key)
    st.button("Open the map: shelters and flooded schools per town", icon=":material/map:", on_click=flip,
              args=("map2",), key="open2")
else:
    st.button("Close the map", icon=":material/close:", on_click=flip, args=("map2",), key="close2", type="tertiary")
    st.session_state.setdefault("town", "All")
    pick = st.pills("Town", ["All", *top.short], label_visibility="collapsed", key="town")
    sel = None if pick in (None, "All") else top[top.short == pick].iloc[0]
    cands = (shel[(shel.town == sel["name"]) & (shel.area == sel.area)].sort_values("capacity_central", ascending=False)
             .reset_index(drop=True) if sel is not None else shel.iloc[0:0])
    cands["label"] = [n if isinstance(n, str) else f"Unnamed {c}" for n, c in zip(cands.name, cands.cat)]
    town_schools = schools[(schools.town == sel["name"]) & (schools.area == sel.area)] if sel is not None else schools
    all2 = st.session_state.get(f"all2-{pick}", False)
    k2 = f"cand-{pick}-{all2}"
    i2 = picked_row(k2)
    stop = cands.iloc[i2] if i2 is not None and i2 < len(cands) else None

    left, right = st.columns([3, 2], gap="small")
    with left:
        sch = town_schools.assign(tname=town_schools.name, tinfo=[f"school in the 2021 water · {s:.0%} of the site"
                                                                 for s in town_schools.share_of_site_flooded])
        school_layer = pdk.Layer("ScatterplotLayer", sch, get_position=["lon", "lat"], get_radius=6,
                                 radius_units="'pixels'", filled=False, stroked=True,
                                 get_line_color=core.rgb(core.EVACUATE), line_width_min_pixels=2, pickable=True)
        layers = list(WATER)
        if sel is None:
            circ = top.assign(r=lambda d: d.no_shelter ** .5 * .32 + 6, tname=top.label,
                              tinfo=[f"{fmt(n)} of {fmt(p)} residents with no shelter place within 1.5 km"
                                     for n, p in zip(top.no_shelter, top.people)],
                              txt=[f"{s}  {about(n)}" for s, n in zip(top.short, top.no_shelter)])
            west = [((core.km(x.lon, x.lat, top.lon, top.lat) < 15) & (top.lon > x.lon)).any() for x in circ.itertuples()]
            circ["off"] = [[0, -(r + 12)] if w else [0, r + 12] for r, w in zip(circ.r, west)]
            layers += [pdk.Layer("ScatterplotLayer", circ, get_position=["lon", "lat"], get_radius="r",
                                 radius_units="'pixels'", get_fill_color=core.rgb(core.EVACUATE, 190),
                                 get_line_color=[255, 255, 255], line_width_min_pixels=2, stroked=True, pickable=True),
                       school_layer,
                       pdk.Layer("TextLayer", circ, get_position=["lon", "lat"], get_text="txt", get_size=13,
                                 get_color=[29, 29, 31], get_pixel_offset="off", get_alignment_baseline="'center'",
                                 background=True, get_background_color=[255, 255, 255, 235], background_padding=[5, 3])]
            view = pdk.ViewState(longitude=6.35, latitude=50.62, zoom=7.7)
        else:
            cs = cands.assign(tname=cands.label, tinfo=[f"candidate {c} · rough capacity ≈ {about(p)} places"
                                                        for c, p in zip(cands.cat, cands.capacity_central)],
                              r=lambda d: d.capacity_central ** .5 * .45 + 3)
            layers += [pdk.Layer("ScatterplotLayer", cs, get_position=["lon", "lat"], get_radius="r",
                                 radius_units="'pixels'", get_fill_color=GREEN, get_line_color=[255, 255, 255],
                                 line_width_min_pixels=1.5, stroked=True, pickable=True),
                       school_layer]
            if stop is not None:
                layers.append(ring(stop.lon, stop.lat))
                view = pdk.ViewState(longitude=stop.lon, latitude=stop.lat, zoom=15)
            else:
                pts2 = pd.concat([cands[["lon", "lat"]], town_schools[["lon", "lat"]]])
                view = fit(pts2) if len(pts2) else pdk.ViewState(longitude=sel.lon, latitude=sel.lat, zoom=12.5)
        deck(layers, view)
        ring_key = "<span><i style='border:2px solid #d70015;border-radius:50%;background:none'></i>School in the 2021 water</span>"
        if sel is None:
            core.legend(core.swatch(core.EVACUATE, "People with no shelter place within 1.5 km (circle size)", True)
                        + ring_key + core.swatch("rgba(0,113,227,.55)", "2021 water"))
        else:
            core.legend(("" if stop is None else f"<b>◯ {stop.label}</b> · candidate {stop['cat']} · rough capacity "
                         f"≈ {about(stop.capacity_central)} places<br>")
                        + core.swatch(core.SHELTER, "Candidate shelter, dry (size = rough capacity)", True)
                        + ring_key + core.swatch("rgba(0,113,227,.55)", "2021 water"))
    with right:
        if sel is None:
            st.html(f"<div class='bars'><div class='cap'>{bars_cap}</div>{bars}</div>")
            core.legend(bars_key)
            st.html("<p class='asof'>Pick a town above to see its candidate shelters and its schools in the water.</p>")
        else:
            st.html(f"<div class='bars'><div class='cap'>{sel.label} · residents in the 2021 water</div><div class='trio'>"
                    f"<div><b style='color:{core.SHELTER}'>{about(sel.covered)}</b><span>have a shelter place within "
                    f"1.5 km</span></div><div><b style='color:{core.EVACUATE}'>{about(sel.no_shelter)}</b><span>have none"
                    f"</span></div><div><b>{len(town_schools)}</b><span>schools in the water</span></div></div></div>")
            shown2 = cands if all2 else cands.head(3)
            st.dataframe(shown2[["label", "cat", "capacity_central"]], key=k2, on_select="rerun",
                         selection_mode="single-row", hide_index=True, height=min(36 * len(shown2) + 40, MAP_H - 230),
                         column_config={"label": st.column_config.TextColumn("Candidate shelter in the town",
                                                                             width="medium"),
                                        "cat": st.column_config.TextColumn("Type", width="small"),
                                        "capacity_central": st.column_config.NumberColumn("Rough capacity",
                                                                                          format="localized",
                                                                                          width="small")})
            if len(cands) > 3:
                st.toggle(f"Show all {len(cands)} candidates", key=f"all2-{pick}")
            st.html("<p class='asof'>Candidates, not official shelters: OpenStreetMap, dry in 2021 and in the 100-year "
                    "model, at least 200 m². Rough capacity: floor area × 50 % usable ÷ 4 m² per person. Click one to "
                    "find it.</p>")

# ============================================================================================ 3 · first action
finding("first", "First action?", f"Evacuate the {len(care)} hospitals and care homes that sat in the 2021 water.",
        "Desk research has not yet covered the Ahr and the Erft, so we do not know if any was flood-proofed since. "
        "Each district's crisis staff has its own list: pick "
        "one to see its sites in evacuation order and the nearest dry hospitals and care homes.")
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
if dist is None and not st.session_state.get("map1"):
    st.button(f"Open the map: all {len(care)} sites in evacuation order", icon=":material/map:", on_click=flip,
              args=("map1",), key="open1")
else:
    if dist is None:
        st.button("Close the map", icon=":material/close:", on_click=flip, args=("map1",), key="close1", type="tertiary")
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
            layers += [pdk.Layer("LineLayer", legs, get_source_position=["flon", "flat"],
                                 get_target_position=["lon", "lat"], get_color=[36, 138, 61, 200], get_width=3,
                                 width_units="'pixels'"),
                       pdk.Layer("ScatterplotLayer", legs, get_position=["lon", "lat"], get_radius=9,
                                 radius_units="'pixels'", get_fill_color=GREEN, get_line_color=[255, 255, 255],
                                 line_width_min_pixels=2, stroked=True, pickable=True),
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
        # never taller than the space left beside the map: longer lists scroll inside the table
        h_list = min(36 * len(shown1) + 38, MAP_H - 190 - (150 if site is not None else 0))
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
            rows = "".join(f"<div class='r' style='grid-template-columns:1fr auto'><div class='n' "
                           f"style='white-space:normal'>{r.to_name}<span class='t'>dry {r.type}</span></div>"
                           f"<div class='v'>{r.km:.1f} km</div></div>" for r in dest.itertuples())
            st.html(f"<div class='bars'><div class='cap'>Nearest dry sites of the same kind</div>"
                    f"{rows or 'No dry site of the same kind within 30 km'}</div>")
        st.html("<p class='asof'>Order: most of the site under water first, hospitals before care homes. Free beds and "
                "residents are not in any dataset: confirm with each operator.</p>")

# ============================================================================================ how we know
st.space("large")
core.group([
    ("<b>Warning time</b>", f"In the July 2021 replay, Maastricht to Venlo peaked {lead} day after the Vesdre and Liège.",
     f"{lead} day"),
], "Also worth knowing")
with st.expander("Why these numbers"):
    st.markdown(
        f"- **No place on foot:** {about(obs['no_shelter'])} people where the satellite saw the 2021 water; "
        f"{about(obs['full'])} of them have a shelter within 1.5 km, but it is full (4 m² per person, half the floor "
        f"usable). Range {about(obs['no_shelter_range'][0])} to {about(obs['no_shelter_range'][1])} with stricter or "
        "looser assumptions.\n"
        f"- **Within 10 km:** the same candidate shelters, up to 10 km away in a straight line, have empty places for "
        f"{about(far_more)} of them.\n"
        f"- **Vesdre (modelled):** {about(mod['no_shelter'])} more people with no place on foot; the satellite map has "
        "no flood there.\n"
        "- **Hospitals and care homes:** at least 5 % of the site under water in July 2021. Receiving sites: the nearest "
        "OpenStreetMap hospitals or care homes that were dry in 2021 and in the 100-year model; free beds unknown.\n"
        f"- **People in the flood zone:** {about(obs['people'])} in 2020, {about(obs['people_2025'])} in 2025 "
        "(projection).\n"
        f"- **Better prepared:** {len(MEASURES)} measures from desk research; status as each source reports it.")
st.page_link("views/limits.py", label="Sources, limits and how we checked the numbers", icon=":material/info:")
