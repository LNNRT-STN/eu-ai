"""Crisis room: the whole region for the flood the room plans for, in three tabs: Board (this file), Priorities
(views/first_action.py and views/briefing.py) and Rivers (views/rivers.py, the live outlook for context).
The crisis manager switches on one or several return periods in the sidebar (dashboard.py); the plan follows the
rarest one. Every town with people in that zone goes to evacuate: the tool queues briefings for its mayor and its fire
brigade (drafted by Claude from the tool's numbers) and closes its busiest evacuation roads inside the zone.
State: src/live.py (data/live.db). Zones: EFAS flood hazard maps (outputs/rp), modelled, no dikes."""
import json
import re

import pandas as pd
import shapely
import streamlit as st
from shapely.geometry import mapping, shape

import anna
import core
import live
from views import briefing, checkin, first_action, rivers
from regionmap import ATTRIBUTION, region_map
from core import about, fmt

COL = {"evacuate": "#d70015", "warn": "#f2994a", "watch": "#f2c94c", "none": "#8e8e93"}
WORD = {"evacuate": "Evacuate", "warn": "Warn", "watch": "Watch", "none": "Normal"}
towns = anna.load()[1]


def town_rows(v):
    """app_towns for one return period, one row per town."""
    return towns[towns.variant == v].drop_duplicates("municipality").set_index("municipality")


@st.cache_data
def water_by_town(v):
    """Each area's zone for one return period cut by the real municipality outlines (Eurostat GISCO LAU), one feature
    per town, tagged with its return period (the map colours the nested zones)."""
    flood = anna.load()[4]
    outl = {f["properties"]["municipality"]: shapely.make_valid(shape(f["geometry"]))
            for f in json.loads((core.DATA / "municipality_outlines.geojson").read_text())["features"]}
    T, feats = town_rows(v), []
    for area in anna.AREA:
        fs = flood[(area, v)]["features"]
        if not fs:
            continue
        water = shapely.make_valid(shape(fs[0]["geometry"]))
        for m in T.index[T.area == area]:
            if m in outl:
                part = water.intersection(outl[m]).simplify(.0001)
                if not part.is_empty:
                    feats.append({"type": "Feature", "geometry": mapping(part),
                                  "properties": {"municipality": m, "rp": int(v[2:])}})
    return feats


def zones(sel):
    """The zones switched on, widest first (the map draws the rarer flood as a lighter rim around the frequent one);
    the 100-year zone, for context, when the scenario is normal."""
    return {"type": "FeatureCollection",
            "features": [f for rp in sorted(sel or [100], reverse=True) for f in water_by_town(f"rp{rp}")]}

# the scenario switch is in every role's sidebar (dashboard.py)
c = live.clock()


# the absorbed pages draw with core's grouped-list classes; take those, not its page padding or sidebar rules
st.html(re.sub(r"\.block-container\{[^}]*\}|\[data-testid=st(Sidebar|SidebarNav|NavSectionHeader)\][^{]*\{[^}]*\}", "",
               core.CSS))
TEXT = {"Evacuate": "#b0000f", "Warn": "#a85400", "Watch": "#7a5d00"}  # status words, AA on white
ROWS = {"evacuate": "red", "warn": "orange", "watch": "yellow", "none": "gray"}


def when(t):
    return f"{pd.Timestamp(t):%d %b %H:%M}"


@st.cache_data
def outlines():
    return json.loads((core.DATA / "municipality_outlines.geojson").read_text())


def homes_now(v):
    """Every home in the zone of return period v with its newest report: needs help | no news | safe."""
    D = checkin.doors(v)
    ck = live.latest(live.checkins())
    st_ = (ck.set_index(["municipality", "door"]).status if len(ck) else
           pd.Series(dtype=str, index=pd.MultiIndex.from_arrays([[], []], names=["municipality", "door"])))
    D = D.join(st_.rename("s"), on=["municipality", "door"])
    D["s"] = D.s.fillna("no news")
    return D


def towns_now(s, H):
    """One row per town that is not at normal: its status, people in the water and how far its homes are cleared."""
    n = H.groupby(["municipality", "s"]).size().unstack(fill_value=0).reindex(columns=["needs help", "no news", "safe"],
                                                                               fill_value=0)
    d = s[s.status.isin(["evacuate", "warn"])].copy()
    d = d.join(n, on="municipality").fillna({"needs help": 0, "no news": 0, "safe": 0})
    d["homes"] = d["needs help"] + d["no news"] + d.safe
    d["todo"] = d["needs help"] + d["no news"]
    d["left"] = (d.safe / d.homes.where(d.homes > 0)).fillna(0)
    return d.sort_values(["level", "people"], ascending=False)


def verdict(s, d, p):
    """The one sentence the room needs: what to do, how many, and how much a rarer flood would add."""
    if p is None:
        return core.SHELTER, "Normal. No flood scenario is switched on.", (
            "Switch on a 10-, 100- or 500-year flood in the sidebar to see who sits in the water, where they go and "
            "which doors to knock on. Several at once compare them.")
    ev, wt = d[d.status == "evacuate"], s[s.status == "watch"]
    head = (f"{p}-year flood: evacuate {len(ev)} town{'s' if len(ev) != 1 else ''}, about {about(ev.people.sum())} "
            f"people in the zone, {fmt(ev.todo.sum())} homes still to clear.")
    lo = min(live.rps())
    detail = " ".join(x for x in (
        f"That is about {about(s.people.sum() - s[f'people_rp{lo}'].sum())} people more than in the {lo}-year flood, "
        "in the same valleys: the water climbs further up the streets." if lo < p else "",
        f"{fmt(ev['needs help'].sum())} homes asked for help: crews go there first." if ev["needs help"].sum() else "",
        f"A 500-year flood would add {len(wt)} town{'s' if len(wt) != 1 else ''} and about "
        f"{about(s.people_rp500.sum() - s.people.sum())} people." if p < 500 and len(wt) else "",
        "Modelled zone (EFAS, no dikes): towns behind the Meuse dikes are an upper bound.") if x)
    return COL["evacuate"], head, detail


@st.cache_data
def compare_table(_stamp):
    """One row per return period: what the zone holds and what the plan can do (central assumptions)."""
    head = anna.load()[0]
    sh = core.load()["shelters"]
    rows = []
    for rp in live.RPS:
        v, h = f"rp{rp}", head[f"rp{rp}"]
        m, tw = h["modelled"], towns[(towns.variant == f"rp{rp}") & (towns.people >= live.MIN_PEOPLE)]
        rows.append({"Flood": f"{rp}-year", "Chance a year": f"{100 / rp:g} %", "Towns": len(tw),
                     "People in the zone": m["people"], "Buildings": m["buildings"],
                     "Shelter in walking reach": m["sheltered"], "No place within 10 km": m["bus_no_shelter"],
                     "Care sites in the water": h["sites"]["vulnerable"],
                     "Shelter sites lost": int(sh[f"in_{v}"].astype(bool).sum())})
    return pd.DataFrame(rows)


def compare(sel):
    """The return periods side by side; the ones switched on stand out."""
    t = compare_table(max(f.stat().st_mtime for f in core.DATA.glob("*.*")))
    on = [f"{r}-year" for r in sel]
    st.markdown("**Return periods compared**",
                help="All ten study areas. A return period says how rare a flood is (a 100-year flood has a 1 % "
                     "chance in any year), not when it comes. Zones: EFAS, modelled, no dikes. Shelter in walking "
                     "reach: candidate sites within 1.5 km that stay dry in that zone; no place within 10 km: "
                     "people buses could not place either. Shelter sites lost: candidate sites inside the zone.")
    sty = t.style.apply(lambda r: ["font-weight:650;background:#fdecee" if r.Flood in on else "color:#4f6580"] * len(r),
                        axis=1).format({c: "{:,.0f}" for c in t.columns if c not in ("Flood", "Chance a year")})
    st.dataframe(sty, hide_index=True, width="stretch")


def pick_row(key, rows):
    sel = st.session_state[key].selection.rows
    if sel:
        st.session_state.cr_sel = rows[sel[0]]
        if town_rows(live.variant()).people.get(rows[sel[0]], 0) >= 10:  # only towns the sidebar Town picker lists
            st.session_state.town = st.session_state._town = rows[sel[0]]


def where_to_act(d):
    """The ranked list of towns to act in; a click opens the town."""
    st.markdown("**Where to act**", help="Towns to evacuate in the planned flood, the most people first.")
    if d.empty:
        st.caption("Every town is at normal.")
        return
    v = st.session_state.get("cr_v", 0)
    key = f"cr_rows_{v}"
    t = pd.DataFrame({"Status": d.status.map(WORD), "Town": d.municipality.map(anna.town),
                      "People": d.people.astype(int), "To clear": d.todo.astype(int), "Left": d.left})
    rows = d.municipality.tolist()
    st.caption("Tick a town, or click it on the map, to see its homes and streets.")
    t = t.style.map(lambda w: f"color:{TEXT.get(w, '#1d1d1f')};font-weight:600", subset=["Status"])
    st.dataframe(t, hide_index=True, key=key, on_select=lambda: pick_row(key, rows), selection_mode="single-row",
                 height=min(36 * len(d) + 38, 440),
                 column_config={
                     "Left": st.column_config.ProgressColumn("Left", format="percent", min_value=0, max_value=1,
                                                             help="Share of the town's homes that have left"),
                     "Status": st.column_config.TextColumn("Status", width="small"),
                     "Town": st.column_config.TextColumn("Town"),
                     "People": st.column_config.NumberColumn("People", width="small", format="localized",
                                                             help="Residents in the planned zone (modelled)"),
                     "To clear": st.column_config.NumberColumn("To clear", width="small",
                                                               help="Homes with no news or asking for help")},
                 )


def back():
    st.session_state.cr_sel = None
    st.session_state.cr_v = st.session_state.get("cr_v", 0) + 1  # a fresh table, no row still selected


def town_card(m, d, H, s):
    """One town: what to do there, its homes, its worst-hit streets and where its people go."""
    r = d.set_index("municipality").loc[m] if m in d.municipality.values else None
    status = r.status if r is not None else "none"
    h = H[H.municipality == m]
    n = h.s.value_counts()
    a, b = st.columns([3, 1], vertical_alignment="center")
    a.markdown(f"### :{ROWS[status]}-badge[{WORD[status]}] {anna.town(m)}")
    b.button("Region", icon=":material/arrow_back:", on_click=back, width="stretch", key="cr_back")
    z = s.set_index("municipality").loc[m] if m in s.municipality.values else None
    if z is not None:
        st.caption(" · ".join(f"{rp}-year zone: about {about(z[f'people_rp{rp}'])} people" for rp in live.RPS))
    if h.empty:
        st.caption("No homes in this flood zone in our data.")
        return
    todo = int(n.get("no news", 0) + n.get("needs help", 0))
    st.markdown({"evacuate": f"**Clear {fmt(todo)} homes now.** Help requests first, then single-storey homes.",
                 "warn": f"**Get {fmt(todo)} homes ready to leave.** No order yet.",
                 "watch": "**Not in this flood.** A 500-year flood would reach it: keep the list ready."}.get(
        status, "**Normal.** No action needed."))
    with st.container(horizontal=True, gap="small"):
        st.metric(":red[:material/sos:] Help", fmt(n.get("needs help", 0)), border=True, width="stretch")
        st.metric(":orange[:material/door_front:] No news", fmt(n.get("no news", 0)), border=True, width="stretch")
        st.metric(":green[:material/check_circle:] Left", fmt(n.get("safe", 0)), border=True, width="stretch")
    st.progress(n.get("safe", 0) / len(h), text=f"{fmt(n.get('safe', 0))} of {fmt(len(h))} homes have left")
    sx = h[h.street.notna()].assign(todo=h.s != "safe").groupby("street").agg(Homes=("door", "size"),
                                                                              Left_to_clear=("todo", "sum"))
    sx = sx.sort_values(["Left_to_clear", "Homes"], ascending=False).head(6).reset_index()
    st.markdown("**Streets most hit**")
    st.dataframe(sx.rename(columns={"street": "Street", "Left_to_clear": "To clear"}), hide_index=True,
                 height=36 * len(sx) + 38)
    go = anna.plan_shelters(live.variant()).query("municipality == @m").nlargest(3, "people")
    if len(go):
        st.markdown("**Where they go**", help="The town's 10 km shelter plan: candidate sites that stay dry in this "
                                              "flood zone. Not official shelters.")
        st.markdown("  \n".join(f":green[:material/home_health:] **{g.label}** · {g.address or 'no street address'}"
                                f" · {about(g.people)} people" for g in go.itertuples()))
    if town_rows(live.variant()).people.get(m, 0) >= 10:
        a, b = st.columns(2)
        a.page_link("views/checkin.py", label="Door-knock list", icon=":material/how_to_reg:")
        b.page_link("views/evacuate.py", label="Town plan", icon=":material/directions_run:")


def named(n):
    """A road's name, or '' for unnamed OSM ways that carry their type ("service", "footway") as name."""
    return n if isinstance(n, str) and n[:1].isupper() else ""


def roads(s, v):
    """Evacuation roads (the busiest ways out, notebooks/evac_sim.py) of the towns at evacuate, each with its people
    and whether it lies inside the zone; closed roads as lines where their OSM way is known."""
    E = checkin.edges(v)["features"]
    act = set(s.municipality[s.status.isin(["warn", "evacuate"])])
    cl = live.closures()
    shut = set(cl.osm_id.dropna().astype(str))
    routes = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": f["geometry"],
         "properties": {"people": float(f["properties"]["people"] or 0), "name": named(f["properties"]["name"]),
                        "flooded": bool(f["properties"]["in_flood_2021"])}}
        for f in E if f["properties"]["municipality"] in act and str(f["properties"]["osm_id"]) not in shut]}
    geo = {str(f["properties"]["osm_id"]): f["geometry"] for f in E}
    closed = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": geo.get(str(r.osm_id)) or {"type": "Point", "coordinates": [r.lon, r.lat]},
         "properties": {"name": named(r.name)}} for r in cl.dropna(subset=["lon"]).itertuples()]}
    return routes, closed


def residents_feed():
    """Real check-ins (typed by residents or crews, not simulated): the newest first. A new one pops a toast."""
    ck = live.checkins()
    real = ck[~ck.sim].tail(5).iloc[::-1]
    if len(real) and real.id.iloc[0] != st.session_state.get("cr_seen"):
        if "cr_seen" in st.session_state:
            r = real.iloc[0]
            st.toast(f"**{r.door}, {anna.town(r.municipality)}**: "
                     + ("safe" if r.status == "safe" else "needs help" if r.status == "needs help" else "report undone"),
                     icon=":material/check_circle:" if r.status == "safe" else ":material/sos:")
        st.session_state.cr_seen = real.id.iloc[0]
    with st.container(key="feed", gap="small"):
        st.markdown(":green[:material/sensors:] **Reported by residents**",
                    help="Check-ins sent from the resident page (Am I at risk?) or entered by crews, as they arrive.")
        if real.empty:
            st.caption("None yet. A resident who taps *I am safe* appears here at once.")
            return
        for r in real.itertuples():
            ok = r.status == "safe"
            where = (r.where or "").split(",")[0]
            st.markdown(f"{':green[:material/check_circle:]' if ok else ':red[:material/sos:]'} **{r.door}**, "
                        f"{anna.town(r.municipality)}  \n"
                        + (f":gray[Safe · {r.people} {'person' if r.people == 1 else 'people'}"
                           + (f" · {where}" if where else "") + "]" if ok else
                           ":red[Needs help: crews go first]" if r.status == "needs help" else ":gray[Report undone]"))


def briefings():
    """Alerts on the left, the briefing drafts on the right: newest draft open, the others one click away."""
    ev = live.events().tail(6).iloc[::-1]
    allob = live.outbox()
    ob = allob.tail(8).iloc[::-1]
    st.subheader(":blue[:material/campaign:] Alerts and briefings",
                 help="When a flood is switched on, the tool drafts one briefing for the mayor and one for the "
                      "fire brigade of every town to evacuate. Claude writes the words, every figure comes from the tool; a template "
                      "when no AI is available. Nothing is sent from here.")
    a, b = st.columns([2, 3], gap="large")
    with a:
        st.markdown("**Latest alerts**")
        if ev.empty:
            st.caption("Nothing yet. Switch on a flood in the sidebar.")
        for r in ev.itertuples():
            st.markdown(f":{ROWS.get(r.to, 'gray')}-badge[{WORD.get(r.to, r.to)}] **{anna.town(r.municipality)}** "
                        f"· {when(r.t)}")
    with b:
        st.markdown(f"**Drafts ready to send** :blue-badge[{len(allob)}]")
        if ob.empty:
            st.caption("A draft appears here for every town to evacuate.")
            return
        lab = {r.id: f"{r.recipient} · {when(r.t)}" for r in ob.itertuples()}
        rid = st.selectbox("Draft", list(lab), format_func=lab.get, key="cr_draft",
                           label_visibility="collapsed") or ob.id.iloc[0]
        r = ob.set_index("id").loc[rid]
        with st.container(border=True, key="draft"):
            st.markdown(f":gray-badge[Draft · not sent] &nbsp; **To:** {r.recipient}")
            text = live.report(rid)
            st.markdown(text if text else "_Drafting…_")
            st.caption("Template: no AI available." if r.source == "template" else
                       "Words by Claude, numbers by the tool. Check before sending.")


def board():
    c = live.advance()
    v, sel, p = c["variant"], c["rps"], c["plan"]
    T = town_rows(v)
    s = live.towns_status()
    H = homes_now(v)
    d = towns_now(s, H)
    color, head, detail = verdict(s, d, p)
    core.banner(color, head, detail, note=False)
    st.space("small")
    compare(sel)
    st.space("small")

    left, right = st.columns([3, 2], gap="medium")
    sel_t = st.session_state.get("cr_sel")
    with left:
        g = s.dropna(subset=["lon"])
        hs = H[H.municipality == sel_t] if sel_t else H.iloc[0:0]
        routes, closed = roads(s, v)
        pick = region_map(dict(
            towns=[dict(municipality=r.municipality, label=anna.town(r.municipality), lon=r.lon, lat=r.lat,
                        status=r.status if r.status in COL else "none", people=float(r.people),
                        people_expected=float(r.people), modelled=False)
                   for r in g.itertuples()],
            areas=outlines(), flood=zones(sel), routes=routes,
            homes={"type": "FeatureCollection", "sig": str(hs.s.value_counts().to_dict()), "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                 "properties": {"s": r.s}} for r in hs.itertuples()]},
            closures=closed, selected=sel_t), key="crisis_map", height=560)
        if pick and pick.get("selected") and pick.get("clicks") != st.session_state.get("cr_clicks"):
            st.session_state.cr_clicks = pick["clicks"]
            st.session_state.cr_sel = sel_t = pick["selected"]
            if T.people.get(sel_t, 0) >= 10:  # only towns the sidebar Town picker lists
                st.session_state.town = st.session_state._town = sel_t
        st.html("<div class='legend'>" + "".join(
            f"<span><i style='background:{COL[k]};opacity:.75'></i>{WORD[k]}</span>" for k in ("evacuate", "watch"))
            + "".join(f"<span><i style='background:{core.RP_COL[f'rp{rp}']};opacity:.8'></i>{rp}-year zone</span>"
                      for rp in sorted(sel or [100]))
            + "<span><i style='background:#0071e3;height:.25rem;border-radius:2px'></i>Road out</span>"
            + "<span><i style='background:repeating-linear-gradient(90deg,#c93400 0 4px,transparent 4px 7px);height:.25rem'></i>Road out, inside the zone</span>"
            + "<span><i style='background:#d70015;height:.3rem;border-radius:2px'></i>Closed</span>"
            + ("<span><i style='background:#d70015;border-radius:50%'></i>Asked for help</span>"
               "<span><i style='background:#f2994a;border-radius:50%'></i>No news</span>"
               "<span><i style='background:#248a3d;border-radius:50%'></i>Has left</span>" if sel_t else
               "<span>Click a town to see its homes and roads</span>") + "</div>")
    with right:
        residents_feed()
        st.space("small")
        if sel_t:
            town_card(sel_t, d, H, s)
        else:
            where_to_act(d)
    st.space("medium")
    briefings()


st.title("Crisis room")
st.html("<style>.st-key-feed{background:#fff;border-radius:12px;padding:.8rem 1rem .75rem}"
        ".st-key-feed p{margin-bottom:.15rem}.st-key-draft{background:#fff;max-height:340px;overflow:auto}"
        ".st-key-draft p,.st-key-draft li{font-size:.95rem;line-height:1.5;max-width:75ch}</style>")
t1, t2, t3 = st.tabs([":red[:material/crisis_alert:] Board", ":violet[:material/priority_high:] Priorities",
                      ":blue[:material/water:] Rivers"])
with t1:
    st.fragment(board, run_every=3)()
    st.space("small")
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(
            "- **Flood zones:** EFAS flood hazard maps (JRC) for the 10-, 100- and 500-year river flood, water deeper "
            "than 10 cm. Every river at that return period at once: a planning map, not one storm and not a "
            "forecast. No dikes or flood walls in the model, so towns behind the Meuse dikes (Liège, Venlo) are an "
            "upper bound. Rivers with less than 500 km² upstream are not modelled.\n"
            "- **Plan:** for the rarest flood switched on. A town with at least 10 residents in that zone evacuates; "
            "a town reached only by the 500-year flood is on watch.\n"
            "- **People:** GHS-POP 2020 residents spread over the GHS-OBAT homes of each cell by floor volume, counted "
            "inside the zone. An order of magnitude, not a census.\n"
            "- **Shelters:** OpenStreetMap schools, sports halls and civic buildings that stay dry in that zone; "
            "places = floor area × 50 % ÷ 4 m². Walking reach 1.5 km; the 10 km plan adds buses. Candidates, not "
            "official shelters.\n"
            "- **Roads out:** shortest routes on OSM roads to the plan's shelters (notebooks/evac_sim.py); the three "
            "busiest roads inside the zone close when a town evacuates.\n"
            "- **Homes left / need help:** check-ins per home from residents and crews.\n"
            "- **Briefings:** one for the mayor and one for the fire brigade of every town to evacuate; Claude writes "
            "the words, every figure comes from the tool. Nothing is sent.\n"
            f"- **Map:** {ATTRIBUTION}")
with t2:
    first_action.render()
    with st.expander("Shelter gap, municipality by municipality", icon=":material/map:"):
        briefing.render()
    st.space("small")
    with st.expander("How this is computed", icon=":material/info:"):
        first_action.how()
        briefing.how()
with t3:
    rivers.render()

core.next_steps("crisis")
