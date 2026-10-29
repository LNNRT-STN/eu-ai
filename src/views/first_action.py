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
MAP_H = 610
PANEL_H = MAP_H - 132        # map height minus the number strip and the tabs above the panel: both columns end level
TABS = ["Evacuate", "Shelters", "Since 2021"]
TIP = {"html": "<b>{tname}</b><br/>{tinfo}",
       "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}}
WATER = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=True, line_width_min_pixels=1,
                   get_fill_color=[0, 113, 227, 70 if a in anna.MODELLED else 140], get_line_color=[0, 90, 200, 200])
         for a in anna.AREA]
GREEN, RED = core.rgb(core.SHELTER), core.rgb(core.EVACUATE)
S = st.session_state
for k, v in {"tab": TABS[0], "site": None, "dfilt": "All", "town": None, "shelter": None, "meas": None,
             "v": 0}.items():
    S.setdefault(k, v)

st.html("""<style>
.block-container{padding-top:2.6rem;padding-bottom:1rem}
.kpi{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border-radius:12px}
.kpi div{padding:.6rem .8rem;position:relative}
.kpi div+div::before{content:"";position:absolute;left:0;top:.7rem;bottom:.7rem;border-left:1px solid #e3e3e8}
.kpi b{display:block;font-size:1.35rem;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:#1d1d1f;
  font-variant-numeric:tabular-nums}
.kpi span{display:block;font-size:.75rem;color:#6e6e73;line-height:1.3;margin-top:.15rem}
.card{background:#fff;border-radius:12px;padding:.85rem 1rem}
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
[class*=st-key-panel]{background:transparent}
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
    return pdk.Layer("ScatterplotLayer", df, id=lid, get_position=["lon", "lat"], get_radius=kw.pop("get_radius", r),
                     radius_units="'pixels'", get_fill_color=color, get_line_color=[255, 255, 255],
                     line_width_min_pixels=2, stroked=True, pickable=True, auto_highlight=True, **kw)


def bump():
    S.v += 1                                           # new widget keys: clears stale table and map selections


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
    for lid, (target, col) in layer_to_state.items():
        if objs.get(lid):
            S[target] = objs[lid][0][col]
            bump()
            return


# ------------------------------------------------------------------------------------------------ the screen
left, right = st.columns([2, 3], gap="medium")
with left:
    st.html("<div class='kpi'>"
            f"<div><b>{len(care)}</b><span>hospitals and care homes to evacuate</span></div>"
            f"<div><b>{about(obs['no_shelter'])}</b><span>residents with no shelter place within 1.5 km</span></div>"
            f"<div><b>{sum(m[4] == DONE for m in MEASURES)} of {len(MEASURES)}</b><span>measures since 2021 done</span>"
            "</div></div>")
    tab = st.segmented_control("View", TABS, key="tab", required=True, label_visibility="collapsed", width="stretch")
    panel = st.container(height=PANEL_H, border=False, key="panel")

layers, view, picks = list(WATER), None, {}

# ================================================================================================ Evacuate
if tab == "Evacuate":
    opts = ["All", *by_d.index]
    with panel:
        st.pills("District", opts, key="dfilt", label_visibility="collapsed", on_change=set_, args=("site", None),
                 format_func=lambda d: f"All {len(care)}" if d == "All" else f"{d} {by_d[d]}")
        dist = S.dfilt or "All"
        sites = evac_order(care if dist == "All" else care[care.district == dist])
        site = sites[sites.name == S.site].iloc[0] if S.site in set(sites.name) else None
        if site is None:
            k = f"sites-{dist}-{S.v}"
            st.dataframe(sites.assign(pct=sites.share_of_site_flooded * 100)[["order", "name", "town", "pct"]], key=k,
                         on_select=partial(on_table, k, sites, "site", "name"), selection_mode="single-row",
                         hide_index=True, height=min(36 * len(sites) + 38, PANEL_H - 84), column_config={
                             "order": st.column_config.NumberColumn("#", width=34),
                             "name": st.column_config.TextColumn("Site", width=178),
                             "town": st.column_config.TextColumn("Town", width=115),
                             "pct": st.column_config.NumberColumn("Flooded", format="%d%%", width=80)})
            st.html("<p class='note'>Order: most of the site under water first, hospitals before care homes.</p>")
        else:
            dest = recv[recv.from_name == site["name"]]
            st.button("All sites", icon=":material/arrow_back:", type="tertiary", on_click=set_, args=("site", None))
            near = "".join(f"<div class='r'><div>{r.to_name}<span>dry {r.type}</span></div><b>{r.km:.1f} km</b></div>"
                           for r in dest.itertuples()) or "<p>No dry site of the same kind within 30 km.</p>"
            st.html(f"<div class='card'><h3>{site.order}. {site['name']}</h3><div class='sub'>{site.type} · {site.town}"
                    f" · {site.district} district · {site.share_of_site_flooded:.0%} of the site under water</div>"
                    f"<p><b>Nearest dry sites of the same kind</b></p>{near}</div>")
            st.html("<p class='note'>Free beds and residents are not in any dataset: confirm with each operator.</p>")
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
    with panel:
        if sel is None:
            k = f"towns-{S.v}"
            rnd = lambda c: tl[c].map(lambda n: round(n, -2) if n >= 1000 else round(n, -1) if n >= 100 else round(n))
            st.dataframe(tl.assign(people=rnd("people"), covered=rnd("covered"), no_shelter=rnd("no_shelter"))
                         [["short", "people", "covered", "no_shelter"]], key=k, on_select=partial(on_table, k, tl, "town", "short"), selection_mode="single-row", hide_index=True,
                         height=PANEL_H - 34, column_config={
                             "short": st.column_config.TextColumn("Town", width=176),
                             "people": st.column_config.NumberColumn("In water", format="localized", width=76),
                             "covered": st.column_config.NumberColumn("Has place", format="localized", width=76),
                             "no_shelter": st.column_config.NumberColumn("No place", format="localized", width=76)})
            st.html("<p class='note'>Residents in the 2021 water. * modelled: the satellite missed the Vesdre.</p>")
        else:
            cands = (shel[(shel.town == sel["name"]) & (shel.area == sel.area)]
                     .sort_values("capacity_central", ascending=False).reset_index(drop=True))
            cands["label"] = [n if isinstance(n, str) else f"Unnamed {c}" for n, c in zip(cands.name, cands.cat)]
            tsch = schools[(schools.town == sel["name"]) & (schools.area == sel.area)]
            stop = cands[cands.label == S.shelter].iloc[0] if S.shelter in set(cands.label) else None
            st.button("All towns", icon=":material/arrow_back:", type="tertiary", on_click=set_, args=("town", None))
            st.html(f"<div class='card'><h3>{sel.label}</h3><div class='sub'>residents in the 2021 water</div>"
                    f"<div class='trio'><div><b style='color:{core.SHELTER}'>{about(sel.covered)}</b><span>have a "
                    f"shelter place within 1.5 km</span></div><div><b style='color:{core.EVACUATE}'>"
                    f"{about(sel.no_shelter)}</b><span>have none</span></div><div><b>{len(tsch)}</b><span>schools in "
                    "the water</span></div></div></div>")
            k = f"cands-{sel.short}-{S.v}"
            st.dataframe(cands[["label", "cat", "capacity_central"]], key=k, on_select=partial(on_table, k, cands, "shelter", "label"), selection_mode="single-row", hide_index=True,
                         height=min(36 * len(cands) + 38, PANEL_H - 258), column_config={
                             "label": st.column_config.TextColumn("Candidate shelter", width=234),
                             "cat": st.column_config.TextColumn("Type", width=105),
                             "capacity_central": st.column_config.NumberColumn("Places ≈", format="localized",
                                                                               width=80)})
            st.html("<p class='note'>Candidates, not official shelters. Places ≈ floor area × 50 % ÷ 4 m² per person.</p>")
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
    place = T.drop_duplicates("name").set_index("name")[["lon", "lat"]]
    M = pd.DataFrame(MEASURES, columns=["area", "theme", "what", "communes", "status", "src", "url"])
    COL = {**STATUS, "Not found": "#c7c7cc"}
    M = pd.concat([M, pd.DataFrame([dict(area="", theme=t, what=f"{t}: {d}", communes=[], status="Not found", src="",
                                         url="") for t, d in GAPS])], ignore_index=True)
    M["id"] = range(len(M))
    M["where"] = M.area.str.split(" · ").str[0]
    n = M.status.value_counts().reindex(list(COL), fill_value=0)
    pick = M[M.id == S.meas].iloc[0] if S.meas in set(M.id) else None
    with panel:
        st.html("<div class='sbar'>" + "".join(f"<i style='flex:{c};background:{COL[s]}'></i>" for s, c in n.items()
                                               if c) + "</div><div class='slab'>"
                + "".join(f"<span><i style='background:{COL[s]}'></i><b>{c}</b>{s.lower()}</span>"
                          for s, c in n.items()) + "</div>")
        if pick is None:
            k = f"meas-{S.v}"
            st.dataframe(M[["status", "where", "what"]], key=k, on_select=partial(on_table, k, M, "meas", "id"),
                         selection_mode="single-row", hide_index=True, height=PANEL_H - 92, column_config={
                             "status": st.column_config.TextColumn("Status", width=88),
                             "where": st.column_config.TextColumn("Where", width=70),
                             "what": st.column_config.TextColumn("What changed", width=250)})
            st.html("<p class='note'>Desk research, Oct 2026. Status as each source reports it.</p>")
        else:
            st.button("All measures", icon=":material/arrow_back:", type="tertiary", on_click=set_, args=("meas", None))
            where = ", ".join(anna.town(c) for c in pick.communes) or ("Region-wide" if pick.area else "Not on the map")
            src = (f"<div class='r'><div>Source</div><a href='{pick.url}' target='_blank'>{pick.src}</a></div>"
                   if pick.url else "<div class='r'><div>Not found in the public record<span>absence in our search is "
                   "not proof nothing was done</span></div></div>")
            st.html(f"<div class='card'><h3>{(pick.area + ' · ') if pick.area else ''}{pick.theme}</h3><div class='sub'>"
                    f"{where}</div><p>{pick.what}</p><div class='r'><div>Status<span>as the source reports it</span></div>"
                    f"<b>{pick.status}</b></div>{src}</div>")
    pts = pd.DataFrame([dict(id=m.id, lon=place.lon[anna.town(c)], lat=place.lat[anna.town(c)], tname=anna.town(c),
                             tinfo=f"{m.status} · {m.area} · {m.theme}", fill=core.rgb(COL[m.status]))
                        for m in M.itertuples() for c in m.communes if anna.town(c) in place.index])
    show = pts[pts.id == pick.id] if pick is not None else pts
    show = show.groupby("tname", as_index=False).first() if pick is None else show
    layers.append(dots(show, "meas", "fill", 8))
    picks = {"meas": ("meas", "id")}
    view = fit(show, 1.3) if len(show) else pdk.ViewState(longitude=6.0, latitude=50.7, zoom=7.6)
    key_html = "".join(core.swatch(STATUS[s], s, True) for s in STATUS) + "<span>one dot per commune named</span>"

with right:
    mk = f"map-{tab}-{S.v}"
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.CARTO_LIGHT,
                             views=[pdk.View(type="MapView", controller={"scrollZoom": False})], tooltip=TIP),
                    height=MAP_H, key=mk, on_select=partial(on_map, mk, picks), selection_mode="single-object")
    st.html("<div class='mapkey'><div class='legend'>" + key_html + core.swatch("rgba(0,113,227,.55)", "2021 water")
            + "</div></div>")
