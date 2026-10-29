"""Home: one working screen. Panel on the left (the brief's answers as three numbers, then three tabs), map on the
right, always visible. Click a row or a point on the map: the other follows.
  Evacuate     the hospitals and care homes in the 2021 water, in evacuation order, and the nearest dry sites (Q4)
  Shelters     residents in the 2021 water with / without a candidate shelter within 1.5 km; flooded schools (Q1, Q3)
  Since 2021   what changed since July 2021, from desk research (Q2, src/measures.py)
Numbers come from outputs/data/ (notebooks/pipeline.py, q4_ranking.py, receiving.py)."""
from functools import partial

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
from core import about, fmt
from measures import DONE, GAPS, MEASURES, STATUS

head, towns, crit, shel, flood, summary, qc = anna.load()
recv, _ = anna.load_moves()
V = "worst"                                               # all satellite passes: closest to official 2021 figures
obs = head[V]["observed"]
T = towns[towns.variant == V].assign(no_shelter=lambda d: d.no_reach + d.full)
C = crit[crit.share_of_site_flooded.ge(.05) & crit.in_worst_flood.astype(bool)]
schools = C[C.type == "school"]
DISTRICT = {"ahr": "Ahrweiler", "erftstadt": "Rhein-Erft", "schleiden": "Euskirchen"}
care = C[C.type.isin(["hospital", "care home"])].assign(district=lambda d: d.area.map(DISTRICT))
by_d = care.district.value_counts()
MAP_H = 600
PANEL_H = MAP_H - 198        # map height minus the first-action card, context line and tabs: both columns end level
TABS = ["Evacuate", "Shelters", "Since 2021"]
TIP = {"html": "<b>{tname}</b><br/>{tinfo}",
       "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}}
WATER = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=True, line_width_min_pixels=1,
                   get_fill_color=[0, 113, 227, 70 if a in anna.MODELLED else 140], get_line_color=[0, 90, 200, 200])
         for a in anna.AREA]
GREEN, RED = core.rgb(core.SHELTER), core.rgb(core.EVACUATE)
S = st.session_state
for k, v in {"tab": TABS[0], "site": None, "dfilt": "All", "town": None, "shelter": None, "meas": None, "commune": None,
             "v": 0}.items():
    S.setdefault(k, v)

st.html("""<style>
.block-container{padding-top:3.75rem;padding-bottom:0}   /* clear the 56 px top bar shown when the sidebar is closed */
.kpi{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border-radius:12px}
.kpi div{padding:.6rem .8rem;position:relative}
.kpi div+div::before{content:"";position:absolute;left:0;top:.7rem;bottom:.7rem;border-left:1px solid #e3e3e8}
.kpi b{display:block;font-size:1.35rem;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:#1d1d1f;
  font-variant-numeric:tabular-nums}
.kpi span{display:block;font-size:.75rem;color:#6e6e73;line-height:1.3;margin-top:.15rem}
.act{display:flex;gap:.7rem;align-items:flex-start}
.act i{flex:none;width:.75rem;height:.75rem;border-radius:50%;background:#d70015;box-shadow:0 0 0 4px #d7001522;margin-top:.42rem}
.act h2{font-size:1.18rem;font-weight:700;letter-spacing:-.015em;line-height:1.3;margin:0;padding:0;color:#1d1d1f}
[class*=st-key-act]{background:#fff;border-radius:12px;padding:.8rem .95rem .7rem;gap:.55rem}
[class*=st-key-act] [data-testid=stButtonGroup]{margin-left:1.45rem}
.ctx{color:#6e6e73;font-size:.8rem;margin:0 .2rem;line-height:1.35}
.ctx b{color:#1d1d1f;font-variant-numeric:tabular-nums}
.cap{font-size:.8rem;font-weight:600;color:#1d1d1f;margin:0 .2rem}
.card{background:#fff;border-radius:12px;padding:.85rem 1rem}
/* list rows: a whole row is one click target (an invisible button stretched over it) */
.st-key-list{background:#fff;border-radius:12px;padding:.3rem;gap:0!important}
[class*=st-key-r-]{position:relative;gap:0}
[class*=st-key-r-] [data-testid=stElementContainer]:has(button){position:absolute;inset:0;margin:0;width:100%!important;height:100%}
[class*=st-key-r-] [data-testid=stButton],[class*=st-key-r-] [data-testid=stButton]>*{width:100%;height:100%}
[class*=st-key-r-] [data-testid=stButton] button{width:100%;height:100%;opacity:0;cursor:pointer}
.lr{display:grid;grid-template-columns:1.5rem 1fr auto;gap:.65rem;align-items:center;padding:.55rem .6rem;border-radius:9px;
  transition:background .12s}
[class*=st-key-r-]:hover .lr{background:#f5f5f7}
.lr.on{background:rgba(0,113,227,.09)!important}
.lr .no{width:1.5rem;height:1.5rem;border-radius:50%;display:grid;place-items:center;font-size:.75rem;font-weight:700;
  color:#fff;background:#d70015;font-variant-numeric:tabular-nums}
.lr .dot{width:.6rem;height:.6rem;border-radius:50%;justify-self:center}
.lr .tx{min-width:0}
.lr .tx b{display:block;font-size:.9rem;font-weight:600;color:#1d1d1f;line-height:1.3}
.lr .tx span{display:block;font-size:.78rem;color:#6e6e73;line-height:1.35;margin-top:.05rem}
.lr .tx span.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.lr .m{display:flex;align-items:center;gap:.45rem;font-size:.8rem;color:#1d1d1f;font-variant-numeric:tabular-nums;font-weight:600}
.lr .m i{display:flex;width:3.2rem;height:.38rem;border-radius:3px;background:#ececf0;overflow:hidden}
.lr .m u{display:block;height:100%}
.lr.sub{grid-template-columns:1fr auto;padding:.4rem .6rem .4rem 2.75rem}
.lr.sub .tx b{font-weight:500;font-size:.85rem}
.det{margin:.1rem .6rem .5rem 2.75rem;padding:.5rem 0 .2rem;border-top:1px solid #e3e3e8;font-size:.82rem;color:#1d1d1f}
.det .h{font-size:.72rem;font-weight:600;color:#6e6e73;text-transform:uppercase;letter-spacing:.03em;margin:.15rem 0 .25rem}
.det .r{display:flex;justify-content:space-between;gap:.8rem;padding:.22rem 0}
.det .r span{color:#6e6e73}
.det .r b{font-variant-numeric:tabular-nums;font-weight:600;text-align:right}
.det p{margin:.2rem 0;line-height:1.45;font-size:.82rem}
.det a{color:#0071e3;text-decoration:none}
/* tabs as text with an underline */
.st-key-tabs [data-testid=stButtonGroup]>div{gap:0;border-bottom:1px solid #e3e3e8}
.st-key-tabs button{background:transparent!important;border:none!important;border-radius:0!important;box-shadow:none!important;
  border-bottom:2px solid transparent!important;color:#6e6e73!important;font-weight:500;padding:.35rem .2rem .5rem!important}
.st-key-tabs button[aria-checked=true]{border-bottom-color:#1d1d1f!important;color:#1d1d1f!important;font-weight:650}
.card h3{font-size:1.05rem;font-weight:650;margin:0;padding:0;color:#1d1d1f;line-height:1.3}
.card .sub{color:#6e6e73;font-size:.85rem;margin-top:.15rem}
.card .r{display:flex;justify-content:space-between;gap:.8rem;padding:.45rem 0;border-top:1px solid #e3e3e8;font-size:.9rem}
.card .r:first-of-type{margin-top:.6rem}
.card .r span{color:#6e6e73;font-size:.8rem;display:block}
.card .r b{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.card p{color:#1d1d1f;font-size:.9rem;margin:.5rem 0 0;line-height:1.45}
.card a{color:#0071e3;text-decoration:none}
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin-top:.6rem}
.trio div{background:#f2f2f7;border-radius:8px;padding:.45rem .6rem}
.trio b{display:block;font-size:1.15rem;font-weight:700;font-variant-numeric:tabular-nums}
.trio span{display:block;font-size:.72rem;color:#6e6e73}
.sbar{display:flex;gap:2px;height:.6rem;border-radius:4px;overflow:hidden;margin:.15rem 0 .45rem}
.slab{display:flex;flex-wrap:wrap;gap:.2rem .9rem;font-size:.78rem;color:#6e6e73}
.slab i{display:inline-block;width:.6rem;height:.6rem;border-radius:2px;margin-right:.3rem}
.slab b{color:#1d1d1f;margin-right:.2rem}
.mapkey{position:relative;z-index:5;margin:-3.2rem 0 0 .6rem;width:fit-content;max-width:calc(100% - 1.2rem);background:rgba(255,255,255,.94);border-radius:8px;padding:.1rem .7rem .4rem;box-shadow:0 1px 4px rgba(0,0,0,.12)}
.mapkey .legend{margin:.3rem 0 0}
.note{color:#8e8e93;font-size:.74rem;line-height:1.4;margin:.35rem .1rem 0}
[class*=st-key-panel]{background:transparent;overflow:hidden!important}  /* only the lists scroll, never the panel */
</style>""")


# ------------------------------------------------------------------------------------------------ helpers
def evac_order(d):
    """Most of the site under water first; on a tie, hospitals before care homes."""
    d = (d.assign(_h=lambda x: (x.type != "hospital").astype(int))
         .sort_values(["share_of_site_flooded", "_h", "name"], ascending=[False, True, True])
         .drop(columns="_h").reset_index(drop=True))
    d.insert(0, "order", range(1, len(d) + 1))
    return d


def fit(df, pad=1.0):
    """Centre and zoom so every point in df is in view."""
    spread = core.km(df.lon.mean(), df.lat.mean(), df.lon, df.lat).max() * pad
    z = 14 if spread < .7 else 13 if spread < 1.5 else 12 if spread < 4 else 11 if spread < 8 else 10 if spread < 16 \
        else 9 if spread < 32 else 8.2
    return pdk.ViewState(longitude=df.lon.mean(), latitude=df.lat.mean(), zoom=z)


def ring(lon, lat):
    return pdk.Layer("ScatterplotLayer", pd.DataFrame([{"lon": lon, "lat": lat}]), get_position=["lon", "lat"],
                     get_radius=17, radius_units="'pixels'", filled=False, stroked=True,
                     get_line_color=[29, 29, 31], line_width_min_pixels=3)


def dots(df, lid, color, r=7, **kw):
    # the id changes after every pick: the stable map keeps its last selection, and Streamlit greys out every
    # object outside it; a selection on an id that no longer exists does nothing
    return pdk.Layer("ScatterplotLayer", df, id=f"{lid}-{S.v}", get_position=["lon", "lat"], get_radius=kw.pop("get_radius", r),
                     radius_units="'pixels'", get_fill_color=color, get_line_color=[255, 255, 255],
                     line_width_min_pixels=2, stroked=True, pickable=True, auto_highlight=True, **kw)


def bump():
    S.v += 1                                           # new widget keys: clears stale table and map selections


def toggle(state, value, *clear):
    S[state] = None if S[state] == value else value
    for c in clear:
        S[c] = None
    bump()


def row(key, html, on, state, value, *clear, sub=False):
    """One list row; clicking it opens it (or closes it if it is open). Details are drawn right after it."""
    with st.container(key=f"r-{key}"):
        st.html(f"<div class='lr{' sub' if sub else ''}{' on' if on else ''}'>{html}</div>")
        st.button("Open", key=f"b-{key}", on_click=toggle, args=(state, value, *clear))


def bar(parts):
    return "<i>" + "".join(f"<u style='width:{w:.0f}%;background:{c}'></u>" for w, c in parts) + "</i>"


def go_district():
    S.site, S.tab = None, "Evacuate"
    bump()


def set_(key, value):
    S[key] = value
    bump()


def rows(key):
    try:
        return list(S[key]["selection"]["rows"])
    except Exception:
        return []


def on_table(key, df, target, col):
    r = rows(key)
    S[target] = df.iloc[r[0]][col] if r else None


def on_map(key, layer_to_state):
    """A click on the map selects the object in the panel."""
    try:
        objs = S[key]["selection"]["objects"]
    except Exception:
        return
    for lid, picked in objs.items():
        base = lid.rsplit("-", 1)[0]
        if picked and base in layer_to_state:
            target, col, *clear = layer_to_state[base]
            S[target] = picked[0][col]
            for c in clear:
                S[c] = None
            bump()
            return


# ------------------------------------------------------------------------------------------------ the screen
left, right = st.columns([2, 3], gap="medium")
with left:
    # the brief's first action is the headline of the panel, on every tab; a district opens its own list
    with st.container(key="act"):
        st.html(f"<div class='act'><i></i><h2>First action: evacuate the {len(care)} hospitals and care homes that "
                "sat in the 2021 water</h2></div>")
        st.pills("District", ["All", *by_d.index], key="dfilt", label_visibility="collapsed", on_change=go_district,
                 format_func=lambda d: f"All {len(care)}" if d == "All" else f"{d} {by_d[d]}")
    st.html(f"<p class='ctx'><b>{about(obs['no_shelter'])}</b> with no shelter place within 1.5 km "
            f"· <b>{sum(m[4] == DONE for m in MEASURES)} of {len(MEASURES)}</b> measures since 2021 done</p>")
    with st.container(key="tabs"):
        tab = st.segmented_control("View", TABS, key="tab", required=True, label_visibility="collapsed",
                                   width="stretch")
    panel = st.container(height=PANEL_H, border=False, key="panel")

layers, view, picks = list(WATER), None, {}

# ================================================================================================ Evacuate
if tab == "Evacuate":
    with panel:
        dist = S.dfilt or "All"
        sites = evac_order(care if dist == "All" else care[care.district == dist])
        site = sites[sites.name == S.site].iloc[0] if S.site in set(sites.name) else None
        dest = recv[recv.from_name == site["name"]] if site is not None else recv.iloc[0:0]
        st.html(f"<p class='cap'>Evacuate in this order{'' if dist == 'All' else ' · ' + dist + ' district'}"
                "<span class='ctx'> · most flooded first, hospitals before care homes</span></p>")
        with st.container(height=PANEL_H - 34, key="list", border=False):
            for r in sites.itertuples():
                on = site is not None and r.name == site["name"]
                pct = r.share_of_site_flooded * 100
                row(f"ev-{r.order}", f"<span class='no'>{r.order}</span><div class='tx'><b>{r.name}</b><span>{r.type}"
                    f" · {r.town}</span></div><div class='m'>{bar([(pct, core.EVACUATE)])}{pct:.0f}%</div>",
                    on, "site", r.name)
                if on:
                    near = "".join(f"<div class='r'><span>{d.to_name} · dry {d.type}</span><b>{d.km:.1f} km</b></div>"
                                   for d in dest.itertuples()) or "<p>No dry site of the same kind within 30 km.</p>"
                    st.html(f"<div class='det'><div class='h'>Nearest dry sites of the same kind</div>{near}"
                            "<p style='color:#8e8e93'>Free beds are not in any dataset: confirm with each operator.</p>"
                            "</div>")
    pts = sites.assign(tname=[f"{o}. {n}" for o, n in zip(sites.order, sites.name)],
                       tinfo=[f"{t} · {w} · {s:.0%} under water" for t, w, s in
                              zip(sites.type, sites.town, sites.share_of_site_flooded)])
    layers.append(dots(pts, "sites", RED))
    picks = {"sites": ("site", "name")}
    if site is not None:
        legs = dest.assign(flon=site.lon, flat=site.lat, tname=dest.to_name,
                           tinfo=[f"dry {t} · {k} km" for t, k in zip(dest.type, dest.km)])
        layers += [pdk.Layer("LineLayer", legs, get_source_position=["flon", "flat"], get_target_position=["lon", "lat"],
                             get_color=[36, 138, 61, 200], get_width=3, width_units="'pixels'"),
                   dots(legs, "recv", GREEN, 8), ring(site.lon, site.lat)]
        view = fit(pd.concat([legs[["lon", "lat"]], pd.DataFrame([{"lon": site.lon, "lat": site.lat}])]), 1.3)
    else:
        view = fit(sites, 1.2)
    key_html = (core.swatch(core.EVACUATE, "Hospital / care home to evacuate", True)
                + (core.swatch(core.SHELTER, "Nearest dry site of the same kind", True) if site is not None else ""))

# ================================================================================================ Shelters
elif tab == "Shelters":
    tl = T[T.no_shelter > 0].sort_values("no_shelter", ascending=False).reset_index(drop=True)
    tl["short"] = tl.label.str.replace(" (modelled)", " *")
    sel = tl[tl.short == S.town].iloc[0] if S.town in set(tl.short) else None
    ring_key = ("<span><i style='border:2px solid #d70015;border-radius:50%;background:none'></i>"
                "School in the 2021 water</span>")
    if sel is not None:
        cands = (shel[(shel.town == sel["name"]) & (shel.area == sel.area)]
                 .sort_values("capacity_central", ascending=False).reset_index(drop=True))
        cands["label"] = [n if isinstance(n, str) else f"Unnamed {c}" for n, c in zip(cands.name, cands.cat)]
        tsch = schools[(schools.town == sel["name"]) & (schools.area == sel.area)]
        stop = cands[cands.label == S.shelter].iloc[0] if S.shelter in set(cands.label) else None
    with panel:
        st.html("<p class='cap'>Residents in the 2021 water<span class='ctx'> · shelter place within 1.5 km: "
                f"<b style='color:{core.SHELTER}'>has one</b> / <b style='color:{core.EVACUATE}'>none</b></span></p>")
        with st.container(height=PANEL_H - 34, key="list", border=False):
            for i, r in enumerate(tl.itertuples()):
                on = sel is not None and r.short == sel.short
                split = [(100 * r.covered / r.people, core.SHELTER), (100 * r.no_shelter / r.people, core.EVACUATE)]
                row(f"tw-{i}", f"<span class='no' style='background:#e5e5ea;color:#3a3a3c'>{i + 1}</span><div class='tx'><b>"
                    f"{r.short}</b><span>{about(r.people)} in the water · {about(r.covered)} have a place</span></div>"
                    f"<div class='m'>{bar(split)}{about(r.no_shelter)}</div>", on, "town", r.short, "shelter")
                if on:
                    st.html(f"<div class='det'><div class='h'>{len(cands)} candidate shelters · {len(tsch)} schools in "
                            "the water</div></div>")
                    for j, c in enumerate(cands.head(8).itertuples()):
                        row(f"cs-{j}", f"<div class='tx'><b>{c.label}</b><span>{c.cat}</span></div>"
                            f"<div class='m'>≈ {about(c.capacity_central)}</div>",
                            stop is not None and c.label == stop.label, "shelter", c.label, sub=True)
                    more = f"Top 8 of {len(cands)} by size. " if len(cands) > 8 else ""
                    st.html("<div class='det' style='border:0;color:#8e8e93'>Candidates, not official shelters. "
                            f"{more}Places ≈ floor area × 50 % ÷ 4 m².</div>")
            st.html("<p class='note' style='margin:.4rem .6rem'>* modelled: the satellite missed the Vesdre.</p>")
    if sel is None:
        circ = tl.assign(r=lambda d: d.no_shelter ** .5 * .3 + 5, tname=tl.label,
                         tinfo=[f"{fmt(n)} of {fmt(p)} residents with no shelter place within 1.5 km"
                                for n, p in zip(tl.no_shelter, tl.people)])
        top = circ.head(5).assign(txt=lambda d: [f"{s}  {about(n)}" for s, n in zip(d.short, d.no_shelter)])
        west = [((core.km(x.lon, x.lat, top.lon, top.lat) < 15) & (top.lon > x.lon)).any() for x in top.itertuples()]
        top["off"] = [[0, -(r + 12)] if w else [0, r + 12] for r, w in zip(top.r, west)]
        sch = schools.assign(tname=schools.name, tinfo=[f"school in the 2021 water · {s:.0%} of the site"
                                                        for s in schools.share_of_site_flooded])
        layers += [dots(circ, "towns", core.rgb(core.EVACUATE, 190), get_radius="r"),
                   pdk.Layer("ScatterplotLayer", sch, get_position=["lon", "lat"], get_radius=5, radius_units="'pixels'",
                             filled=False, stroked=True, get_line_color=RED, line_width_min_pixels=1.5, pickable=True),
                   pdk.Layer("TextLayer", top, get_position=["lon", "lat"], get_text="txt", get_size=13,
                             get_color=[29, 29, 31], get_pixel_offset="off", get_alignment_baseline="'center'",
                             background=True, get_background_color=[255, 255, 255, 235], background_padding=[5, 3])]
        picks = {"towns": ("town", "short")}
        view = pdk.ViewState(longitude=6.3, latitude=50.75, zoom=7.6)
        key_html = core.swatch(core.EVACUATE, "Residents with no shelter place within 1.5 km (size)", True) + ring_key
    else:
        cs = cands.assign(tname=cands.label, tinfo=[f"candidate {c} · rough capacity ≈ {about(p)} places"
                                                    for c, p in zip(cands.cat, cands.capacity_central)],
                          r=lambda d: d.capacity_central ** .5 * .45 + 3)
        sch = tsch.assign(tname=tsch.name, tinfo=[f"school in the 2021 water · {s:.0%} of the site"
                                                  for s in tsch.share_of_site_flooded])
        layers += [dots(cs, "cands", GREEN, get_radius="r"),
                   pdk.Layer("ScatterplotLayer", sch, get_position=["lon", "lat"], get_radius=6, radius_units="'pixels'",
                             filled=False, stroked=True, get_line_color=RED, line_width_min_pixels=2, pickable=True)]
        picks = {"cands": ("shelter", "label")}
        if stop is not None:
            layers.append(ring(stop.lon, stop.lat))
            view = pdk.ViewState(longitude=stop.lon, latitude=stop.lat, zoom=15)
        else:
            pts = pd.concat([cands[["lon", "lat"]], tsch[["lon", "lat"]]])
            view = fit(pts, 1.1) if len(pts) else pdk.ViewState(longitude=sel.lon, latitude=sel.lat, zoom=12.5)
        key_html = (("" if stop is None else f"<b>◯ {stop.label}</b> · rough capacity ≈ {about(stop.capacity_central)}"
                     " places<br>")
                    + core.swatch(core.SHELTER, "Candidate shelter, dry (size = rough capacity)", True) + ring_key)

# ================================================================================================ Since 2021
else:
    # the map shows communes, the list shows measures: a commune dot filters the list to the measures naming it,
    # a picked measure rings its communes on the map
    place = T.drop_duplicates("name").set_index("name")[["lon", "lat"]]
    M = pd.DataFrame(MEASURES, columns=["area", "theme", "what", "communes", "status", "src", "url"])
    COL = {**STATUS, "Not found": "#c7c7cc"}
    M = pd.concat([M, pd.DataFrame([dict(area="", theme=t, what=f"{t}: {d}", communes=[], status="Not found", src="",
                                         url="") for t, d in GAPS])], ignore_index=True)
    M["id"] = range(len(M))
    M["where"] = M.area.str.split(" · ").str[0]
    M["places"] = [[anna.town(c) for c in cs if anna.town(c) in place.index] for cs in M.communes]
    n = M.status.value_counts().reindex(list(COL), fill_value=0)
    pick = M[M.id == S.meas].iloc[0] if S.meas in set(M.id) else None
    com = S.commune if S.commune in place.index else None
    rows_ = (M[M.places.map(lambda p: com in p)] if com else M).reset_index(drop=True)
    with panel:
        st.html("<div class='sbar'>" + "".join(f"<i style='flex:{c};background:{COL[s]}'></i>" for s, c in n.items()
                                               if c) + "</div><div class='slab'>"
                + "".join(f"<span><i style='background:{COL[s]}'></i><b>{c}</b>{s.lower()}</span>"
                          for s, c in n.items()) + "</div>")
        if com:
            st.button(f"All measures · showing {com}", icon=":material/arrow_back:", type="tertiary", on_click=set_,
                      args=("commune", None))
        with st.container(height=PANEL_H - 52 - (40 if com else 0), key="list", border=False):
            for r in rows_.itertuples():
                on = pick is not None and r.id == pick.id
                row(f"ms-{r.id}", f"<span class='dot' style='background:{COL[r.status]}'></span><div class='tx'><b>"
                    f"{r.where or 'Not found'} · {r.theme}</b><span{'' if on else ' class=clamp'}>{r.what}</span></div>"
                    f"<div class='m' style='font-weight:500;color:#6e6e73'>{r.status}</div>", on, "meas", r.id)
                if on:
                    where = ", ".join(anna.town(c) for c in r.communes) or ("Region-wide: not on the map" if r.area
                                                                            else "Not on the map")
                    src = (f"<div class='r'><span>Source</span><a href='{r.url}' target='_blank'>{r.src}</a></div>"
                           if r.url else "<p style='color:#8e8e93'>Absence in our search is not proof nothing was "
                           "done.</p>")
                    st.html(f"<div class='det'><div class='r'><span>Where</span><b>{where}</b></div>"
                            f"<div class='r'><span>Status, as the source reports it</span><b>{r.status}</b></div>{src}"
                            "</div>")
    per = M.explode("places").dropna(subset=["places"]).groupby("places")
    cdf = pd.DataFrame({"tname": list(per.groups)}).assign(
        lon=lambda d: d.tname.map(place.lon), lat=lambda d: d.tname.map(place.lat),
        k=lambda d: d.tname.map(per.size()),
        tinfo=lambda d: [f"{per.size()[t]} measures: " + ", ".join(f"{s} ({th})" for s, th in
                                                                    zip(per.get_group(t).status, per.get_group(t).theme))
                         for t in d.tname])
    cdf["r"] = 6 + 3 * cdf.k ** .5
    hl = pick.places if pick is not None else ([com] if com else [])
    layers.append(dots(cdf, "com", [72, 72, 74], get_radius="r"))
    layers += [ring(place.lon[h], place.lat[h]) for h in hl]
    picks = {"com": ("commune", "tname", "meas")}
    if hl:
        v = fit(place.loc[hl].reset_index(), 1.3)
        view = pdk.ViewState(longitude=v.longitude, latitude=v.latitude, zoom=min(v.zoom, 10.5))
    else:
        view = fit(cdf, 1.2)
    key_html = (core.swatch("#48484a", "Commune named in a measure (size = number of measures)", True)
                + "<span><i style='border:2px solid #1d1d1f;border-radius:50%;background:none'></i>Selected</span>")

with right:
    # one map per tab that stays mounted: a new view then glides there instead of redrawing. Streamlit's map does
    # not register deck.gl's FlyToInterpolator, so the controller's default (linear pan + zoom) animates it.
    # Streamlit only forwards view keys that changed since the last run, so the duration alternates by 1 ms to be
    # sent with every new view (otherwise the map jumps).
    mk = f"map-{tab}"
    S.tick = S.get("tick", 0) + 1
    view = pdk.ViewState(longitude=view.longitude, latitude=view.latitude, zoom=view.zoom,
                         transition_duration=1200 + S.tick % 2)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.CARTO_LIGHT,
                             views=[pdk.View(type="MapView", controller={"scrollZoom": False})], tooltip=TIP),
                    height=MAP_H, key=mk, on_select=partial(on_map, mk, picks), selection_mode="single-object")
    # the script rides in the legend's own block (no extra element under the map): it scrolls the open row into
    # view, since a map click can open a row that is off screen
    st.html("<div class='mapkey'><div class='legend'>" + key_html + core.swatch("rgba(0,113,227,.55)", "2021 water")
            + f"</div></div><script>/*{S.v}*/setTimeout(()=>document.querySelector('.lr.on')?.scrollIntoView("
            "{block:'nearest',behavior:'smooth'}),400)</script>", unsafe_allow_javascript=True)
