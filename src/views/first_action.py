"""Crisis room, Priorities tab (render), for the flood the room plans for (live.variant()), in order of importance:
  1 Do now   evacuate the hospitals and care homes in the flood zone: per district, in order, and where to take them
  2 Next     (brief Q3) who has a candidate shelter within walking distance, who does not; schools in the zone
  how()      'better prepared?', how the numbers were made: for the tab's How this is computed expander
Numbers come from outputs/rp/ (notebooks/pipeline.py with FLOOD=rp, rp_extras.py)."""
import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
import live
from core import about, fmt

head, towns, crit, shel, flood, summary, qc = anna.load()
recv, bus = anna.load_moves()
MAX_DISTRICTS = 4                                         # district cards side by side; the rest under "All"
MAP_H = 480
TIP = {"html": "<b>{tname}</b><br/>{tinfo}",
       "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}}
GREEN = core.rgb(core.SHELTER)


def scenario(v):
    """The tab's numbers for return period v (the module stays imported between reruns, so they are set per run)."""
    global V, RP, obs, T, C, care, by_d, WATER, ZONE
    V, RP = v, int(v[2:])
    ZONE = f"{RP}-year zone"
    obs = head[V]["modelled"]
    T = towns[towns.variant == V].assign(no_shelter=lambda d: d.no_reach + d.full)
    C = crit[crit.share_of_site_flooded.ge(.05) & crit[f"in_{V}_flood"].astype(bool)].copy()
    C["district"] = [live.district(a, m).replace("Province of ", "").replace(" (governor)", "")
                     for a, m in zip(C.area, C.municipality)]
    care = C[C.type.isin(["hospital", "care home"])]
    by_d = care.groupby("district").size().sort_values(ascending=False).head(MAX_DISTRICTS)
    WATER = [pdk.Layer("GeoJsonLayer", flood[(a, V)], filled=True, stroked=True, line_width_min_pixels=1,
                       get_fill_color=core.rgb(core.RP_COL[V], 120), get_line_color=core.rgb(core.RP_COL[V], 200))
             for a in anna.AREA]




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

CSS = """<style>
.act{background:#fff;border-radius:16px;padding:1.1rem 1.4rem;display:flex;gap:1rem;align-items:center}
.act i{flex:none;width:.9rem;height:.9rem;border-radius:50%;background:#d70015;box-shadow:0 0 0 5px #d7001522}
.act.next i{background:#203e5f;box-shadow:0 0 0 5px #203e5f22}
.act h2{font-size:1.35rem;font-weight:700;letter-spacing:-.02em;line-height:1.2;margin:0;padding:0;color:#1d1d1f}
.act p{margin:.3rem 0 0;color:#4f6580;font-size:.98rem}
.act p b{color:#1d1d1f}
.bars{background:#fff;border-radius:16px;padding:1rem 1.2rem}
.bars .r{display:grid;grid-template-columns:9.5rem 1fr 3.6rem;gap:.6rem;align-items:center;padding:.45rem 0}
.bars .n{font-weight:600;color:#1d1d1f;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bars .t{display:block;font-weight:400;color:#5a6e87;font-size:.78rem}
.bars .v{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;color:#1d1d1f}
.bars .cap{font-size:.8rem;font-weight:600;color:#4f6580;margin:0 0 .3rem}
.one b{display:block;font-size:2.2rem;font-weight:700;letter-spacing:-.03em;line-height:1.05;color:#1d1d1f}
.one span{display:block;margin-top:.3rem;color:#4f6580;font-size:.95rem}
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-top:.6rem}
.trio div{background:#f2f2f7;border-radius:10px;padding:.5rem .7rem}
.trio b{display:block;font-size:1.25rem;font-weight:700;color:#1d1d1f;font-variant-numeric:tabular-nums}
.trio span{display:block;font-size:.75rem;color:#4f6580}
.dc{background:#fff;border-radius:16px;padding:1rem 1.2rem;border:2px solid transparent;transition:border-color .15s}
.dc b{display:block;font-size:2.2rem;font-weight:700;letter-spacing:-.03em;line-height:1;color:#d70015}
.dc h3{font-size:1.05rem;font-weight:650;margin:.35rem 0 0;padding:0;color:#1d1d1f}
.dc span{display:block;margin-top:.2rem;color:#4f6580;font-size:.88rem}
.dc.on{border-color:#d70015}
[class*=st-key-dcard-]{position:relative;gap:0}
[class*=st-key-dcard-] [data-testid=stElementContainer]:has(button){position:absolute;inset:0;margin:0;width:100%!important;height:100%}
[class*=st-key-dcard-] [data-testid=stButton],[class*=st-key-dcard-] [data-testid=stButton]>*{width:100%;height:100%}
[class*=st-key-dcard-] [data-testid=stButton] button{width:100%;height:100%;opacity:0;cursor:pointer}
[class*=st-key-dcard-]:hover .dc{border-color:#d7001555}
@media (max-width:900px){.act h2{font-size:1.2rem}.trio{grid-template-columns:1fr}}
</style>"""


def render():
    scenario(live.variant())
    st.html(CSS)
    if live.plan() is None:
        st.info("No flood switched on: these are the priorities for a 100-year flood, for preparation.",
                icon=":material/info:")
    # =============================================================================== 1 · DO NOW
    st.html(f"<div class='act'><i></i><div><h2>Across all towns: move the {len(care)} hospitals and care homes in the {ZONE} first"
            "</h2><p>Pick a district: its sites in evacuation order, and the nearest dry hospitals and care homes."
            "</p></div></div>")
    st.space("small")
    st.session_state.setdefault("district", None)


    def pick_district(d):
        st.session_state.district = None if st.session_state.district == d else d
        st.session_state.v1 = st.session_state.get("v1", 0) + 1          # reset the site list selection


    cards = st.columns(len(by_d), gap="small")
    for col, (d, n) in zip(cards, by_d.items()):
        in_d = care[care.district == d].town.value_counts().head(4)
        with col, st.container(key=f"dcard-{d}"):
            st.html(f"<div class='dc{' on' if st.session_state.district == d else ''}'><b>{n}</b>"
                    f"<h3>{d} district crisis staff</h3><span>{' · '.join(f'{t} {k}' for t, k in in_d.items())}</span></div>")
            st.button(f"Show {d}", key=f"dbtn-{d}", on_click=pick_district, args=(d,))
    st.space("small")

    dist = st.session_state.district
    if dist not in by_d.index:  # the scenario changed under a picked district
        dist = st.session_state.district = None
    sites = evac_order(care[care.district == dist] if dist else care)
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
                    + core.swatch(core.RP_COL[V], ZONE))
    with right:
        head_txt = f"{dist} district crisis staff" if dist else "All districts"
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
            rows = "".join(f"<div class='r' style='grid-template-columns:1fr auto'><div class='n' style='white-space:normal'>"
                           f"{r.to_name}<span class='t'>dry {r.type}</span></div><div class='v'>{r.km:.1f} km</div></div>"
                           for r in dest.itertuples())
            st.html(f"<div class='bars'><div class='cap'>Nearest dry sites of the same kind</div>"
                    f"{rows or 'No dry site of the same kind within 30 km'}</div>")
        st.html("<p class='asof'>Free beds and residents are in no dataset: confirm with each operator.</p>")
    st.space("medium")

    # =============================================================================== 2 · NEXT (brief, Q3)
    # The brief's Q3: candidate shelters (schools, sports halls, civic buildings) that stayed dry and are big enough,
    # rough capacity; how many exposed residents have one within reach and how many don't; flag schools in the water.
    schools = C[C.type == "school"]
    far_more = obs["bus_covered"] - obs["sheltered"]
    st.html(f"<div class='act next'><i></i><div><h2>Next: {about(obs['no_shelter'])} people would have no shelter place "
            "within walking distance</h2>"
            f"<p>{about(obs['sheltered'])} of the {about(obs['people'])} residents in the {ZONE} have one within 1.5 km. "
            f"{len(schools)} schools lie in the zone themselves. Candidate shelters 1.5–10 km away have empty places for "
            f"{about(far_more)} more; about {about(obs['bus_no_shelter'])} have no place within 10 km.</p></div></div>")
    st.space("small")

    top = T.nlargest(5, "no_shelter").reset_index(drop=True)
    top["short"] = top.label.str.replace(" (modelled)", "")
    st.session_state.setdefault("pr_town", "All")
    pick = st.pills("Town", ["All", *top.short], label_visibility="collapsed", key="pr_town")
    sel = None if pick in (None, "All") else top[top.short == pick].iloc[0]
    dry = shel[~shel[f"in_{V}"].astype(bool)]  # candidate sites that stay dry in this zone
    cands = (dry[(dry.town == sel["name"]) & (dry.area == sel.area)].sort_values("capacity_central", ascending=False)
             .reset_index(drop=True) if sel is not None else shel.iloc[0:0])
    cands["label"] = [n if isinstance(n, str) else f"Unnamed {c}" for n, c in zip(cands.name, cands.cat)]
    town_schools = schools[(schools.town == sel["name"]) & (schools.area == sel.area)] if sel is not None else schools
    all2 = st.session_state.get(f"all2-{pick}", False)
    k2 = f"cand-{pick}-{all2}"
    i2 = picked_row(k2)
    stop = cands.iloc[i2] if i2 is not None and i2 < len(cands) else None

    left, right = st.columns([3, 2], gap="small")
    with left:
        sch = town_schools.assign(tname=town_schools.name, tinfo=[f"school in the {ZONE} · {s:.0%} of the site"
                                                                 for s in town_schools.share_of_site_flooded])
        school_layer = pdk.Layer("ScatterplotLayer", sch, get_position=["lon", "lat"], get_radius=6, radius_units="'pixels'",
                                 filled=False, stroked=True, get_line_color=core.rgb(core.EVACUATE), line_width_min_pixels=2,
                                 pickable=True)
        layers = list(WATER)
        if sel is None:
            circ = top.assign(r=lambda d: d.no_shelter ** .5 * .32 + 6, tname=top.label,
                              tinfo=[f"{fmt(n)} of {fmt(p)} residents with no shelter place within 1.5 km"
                                     for n, p in zip(top.no_shelter, top.people)],
                              txt=[f"{s}  {about(n)}" for s, n in zip(top.short, top.no_shelter)])
            west = [((core.km(x.lon, x.lat, top.lon, top.lat) < 15) & (top.lon > x.lon)).any() for x in circ.itertuples()]
            circ["off"] = [[0, -(r + 12)] if w else [0, r + 12] for r, w in zip(circ.r, west)]
            layers += [pdk.Layer("ScatterplotLayer", circ, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                                 get_fill_color=core.rgb(core.EVACUATE, 190), get_line_color=[255, 255, 255],
                                 line_width_min_pixels=2, stroked=True, pickable=True),
                       school_layer,
                       pdk.Layer("TextLayer", circ, get_position=["lon", "lat"], get_text="txt", get_size=13,
                                 get_color=[29, 29, 31], get_pixel_offset="off", get_alignment_baseline="'center'",
                                 background=True, get_background_color=[255, 255, 255, 235], background_padding=[5, 3])]
            view = pdk.ViewState(longitude=6.35, latitude=50.62, zoom=7.7)
        else:
            cs = cands.assign(tname=cands.label, tinfo=[f"candidate {c} · rough capacity ≈ {about(p)} places"
                                                        for c, p in zip(cands.cat, cands.capacity_central)],
                              r=lambda d: d.capacity_central ** .5 * .45 + 3)
            layers += [pdk.Layer("ScatterplotLayer", cs, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                                 get_fill_color=GREEN, get_line_color=[255, 255, 255], line_width_min_pixels=1.5,
                                 stroked=True, pickable=True),
                       school_layer]
            if stop is not None:
                layers.append(ring(stop.lon, stop.lat))
                view = pdk.ViewState(longitude=stop.lon, latitude=stop.lat, zoom=15)
            else:
                pts2 = pd.concat([cands[["lon", "lat"]], town_schools[["lon", "lat"]]])
                view = fit(pts2) if len(pts2) else pdk.ViewState(longitude=sel.lon, latitude=sel.lat, zoom=12.5)
        deck(layers, view)
        if sel is None:
            core.legend(core.swatch(core.EVACUATE, "People with no shelter place within 1.5 km (circle size)", True)
                        + f"<span><i style='border:2px solid #d70015;border-radius:50%;background:none'></i>School in the {ZONE}</span>"
                        + core.swatch(core.RP_COL[V], ZONE))
        else:
            core.legend(("" if stop is None else f"<b>◯ {stop.label}</b> · candidate {stop['cat']} · rough capacity "
                         f"≈ {about(stop.capacity_central)} places<br>")
                        + core.swatch(core.SHELTER, "Candidate shelter, dry (size = rough capacity)", True)
                        + f"<span><i style='border:2px solid #d70015;border-radius:50%;background:none'></i>School in the {ZONE}</span>"
                        + core.swatch(core.RP_COL[V], ZONE))
    with right:
        if sel is None:
            mx = top.people.max()
            bars = "".join(f"<div class='r'><div class='n'>{r.short}<span class='t'>{about(r.covered)} of {about(r.people)} "
                           f"have one</span></div><div style='display:flex;height:.7rem;border-radius:4px;overflow:hidden;"
                           f"background:#f2f2f7'><i style='width:{100 * r.covered / mx:.0f}%;background:{core.SHELTER}'></i>"
                           f"<i style='width:{100 * r.no_shelter / mx:.0f}%;background:{core.EVACUATE}'></i></div>"
                           f"<div class='v'>{about(r.no_shelter)}</div></div>" for r in top.itertuples())
            st.html(f"<div class='bars'><div class='cap'>Residents in the {ZONE}: shelter place within 1.5 km?</div>"
                    f"{bars}</div>")
            core.legend(core.swatch(core.SHELTER, "Has a place") + core.swatch(core.EVACUATE, "No place (number)"))
            st.html("<p class='asof'>Modelled zone (EFAS, no dikes): towns behind the Meuse dikes are an upper bound.</p>")
        else:
            st.html(f"<div class='bars'><div class='cap'>{sel.label} · residents in the {ZONE}</div><div class='trio'>"
                    f"<div><b style='color:{core.SHELTER}'>{about(sel.covered)}</b><span>have a shelter place within 1.5 km"
                    f"</span></div><div><b style='color:{core.EVACUATE}'>{about(sel.no_shelter)}</b><span>have none</span></div>"
                    f"<div><b>{len(town_schools)}</b><span>schools in the zone</span></div></div></div>")
            shown2 = cands if all2 else cands.head(3)
            st.dataframe(shown2[["label", "cat", "capacity_central"]], key=k2, on_select="rerun", selection_mode="single-row",
                         hide_index=True, height=min(36 * len(shown2) + 40, MAP_H - 230),
                         column_config={"label": st.column_config.TextColumn("Candidate shelter in the town", width="medium"),
                                        "cat": st.column_config.TextColumn("Type", width="small"),
                                        "capacity_central": st.column_config.NumberColumn("Rough capacity", format="localized",
                                                                                          width="small")})
            if len(cands) > 3:
                st.toggle(f"Show all {len(cands)} candidates", key=f"all2-{pick}")
            st.html("<p class='asof'>Candidates, not official shelters. Click one to find it.</p>")


def how():
    """Method notes for the How this is computed expander (no nested expander: this sits inside one)."""
    scenario(live.variant())
    st.markdown(
        f"- **No place on foot ({RP}-year flood):** {about(obs['no_shelter'])} people in the zone; "
        f"{about(obs['full'])} of them have a shelter within 1.5 km, but it is full (4 m² per person, half the floor "
        f"usable). Range {about(obs['no_shelter_range'][0])} to {about(obs['no_shelter_range'][1])} with stricter or "
        "looser assumptions.\n"
        f"- **Within 10 km:** the same candidate shelters, up to 10 km away in a straight line, have empty places for "
        f"{about(obs['bus_covered'] - obs['sheltered'])} of them.\n"
        "- **Hospitals and care homes:** at least 5 % of the site inside the 500-year zone and in this zone, most of "
        "the site under water first, hospitals before care homes. Receiving sites: the nearest OpenStreetMap hospitals "
        "or care homes outside the 500-year zone; free beds and residents are in no dataset.\n"
        "- **Candidate shelters:** schools, sports halls and civic buildings from OpenStreetMap, dry in this zone, at "
        "least 200 m². Rough capacity: floor area × 50 % usable ÷ 4 m² per person. A rarer flood takes sites away.\n"
        f"- **People in the flood zone:** {about(obs['people'])} in 2020, {about(obs['people_2025'])} in 2025 "
        "(projection). EFAS zone, modelled; no dikes in the model.\n"
        "- **Better prepared than 2021? Partly.** Warning: Germany's cell broadcast has run since Feb 2023 and a €88 m "
        "siren programme followed. Rail: the Ahr valley line reopened in Dec 2025. Still open: shelter places on foot, "
        "the Ahr's retention basins (unfunded). Partly verified desk research: docs/BUDGETS.md and the 2021 vs today "
        "page.\n"
        "- **Sources and checks:** Data & limits.")
