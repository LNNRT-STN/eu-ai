"""Crisis room: the whole region, live, in three tabs: Live board (this file), Priorities (views/first_action.py and
views/briefing.py) and Rivers (views/rivers.py). A replay of July 2021 (or the live forecast) drives each town's alert level;
at each rise the tool queues briefings for the mayor and the district fire brigade (drafted by Claude from the tool's
numbers), simulated check-ins arrive, and roads in the 2021 water close. State: src/live.py (data/live.db).
Status uses the highest river flow reached so far (it never drops in a replay); daily GloFAS flows are held for their
whole day, so the replay gives the day, not the hour."""
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
T = towns[towns.variant == "worst"].drop_duplicates("municipality").set_index("municipality")


@st.cache_data
def water_by_town():
    """Each area's 2021 water cut by the real municipality outlines (Eurostat GISCO LAU), one feature per town."""
    flood = anna.load()[4]
    outl = {f["properties"]["municipality"]: shapely.make_valid(shape(f["geometry"]))
            for f in json.loads((core.DATA / "municipality_outlines.geojson").read_text())["features"]}
    feats = []
    for area in anna.AREA:
        water = shapely.make_valid(shape(flood[(area, "worst")]["features"][0]["geometry"]))
        for m in T.index[T.area == area]:
            if m in outl:
                part = water.intersection(outl[m]).simplify(.0001)
                if not part.is_empty:
                    feats.append({"type": "Feature", "geometry": mapping(part), "properties": {"municipality": m}})
    return {"type": "FeatureCollection", "features": feats}

# the scenario player is in every role's sidebar (dashboard.py)
c = live.clock()


# the absorbed pages draw with core's grouped-list classes; take those, not its page padding or sidebar rules
st.html(re.sub(r"\.block-container\{[^}]*\}|\[data-testid=st(Sidebar|SidebarNav|NavSectionHeader)\][^{]*\{[^}]*\}", "",
               core.CSS))
TEXT = {"Evacuate": "#b0000f", "Warn": "#a85400", "Watch": "#7a5d00"}  # status words, AA on white
ROWS = {"evacuate": "red", "warn": "orange", "watch": "yellow", "none": "gray"}


def when(t, mode):
    return f"{live.drill(t):%a %d %b}" if mode == "replay" else f"{pd.Timestamp(t):%d %b %H:%M}"


def coming(t):
    """What the 2021 flows still hold after t: '4 more towns reach evacuate, the first on Thu 1 Nov.' or ''."""
    tm = live._replay()["times"]
    ahead = tm.t_evacuate[tm.t_evacuate > t].dropna()
    if ahead.empty:
        return ""
    return (f"{len(ahead)} more town{'s' if len(ahead) > 1 else ''} reach evacuate, the first on "
            f"{live.drill(ahead.min()):%A %-d %B}.")


@st.cache_data
def outlines():
    return json.loads((core.DATA / "municipality_outlines.geojson").read_text())


def homes_now():
    """Every home in the 2021 water with its newest report: needs help | no news | safe."""
    D = checkin.doors()
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
    d = s[s.status.isin(["evacuate", "warn", "watch"])].copy()
    d = d.join(n, on="municipality").fillna({"needs help": 0, "no news": 0, "safe": 0})
    d["homes"] = d["needs help"] + d["no news"] + d.safe
    d["todo"] = d["needs help"] + d["no news"]
    d["left"] = (d.safe / d.homes.where(d.homes > 0)).fillna(0)
    return d.sort_values(["level", "people"], ascending=False)


def verdict(m, d, t, replay):
    """The one sentence the room needs: what to do, how many, and what is still coming."""
    ev, wn = d[d.status == "evacuate"], d[d.status == "warn"]
    obs = ev[~ev.area.isin(anna.MODELLED)]
    nxt = coming(t) if replay else ""
    if len(ev):
        head = (f"Evacuate {len(ev)} town{'s' if len(ev) > 1 else ''} now: about {about(obs.people.sum())} people, "
                f"{fmt(ev.todo.sum())} homes still to clear.")
        mod = ev[ev.area.isin(anna.MODELLED)].people.sum()
        detail = " ".join(x for x in (
            f"Plus about {about(mod)} people in the modelled Vesdre zone, counted apart." if mod else "",
            f"{fmt(ev['needs help'].sum())} homes asked for help: crews go there first." if ev["needs help"].sum() else "",
            f"{len(wn)} more town{'s' if len(wn) != 1 else ''} warned." if len(wn) else "", nxt) if x)
        return COL["evacuate"], head, detail
    if len(wn):
        return COL["warn"], f"No evacuation yet. {len(wn)} town{'s' if len(wn) > 1 else ''} warned: get ready.", nxt
    return core.SHELTER, "No town needs to act now.", nxt or "No river is above its 2-year flood."


def pick_row(key, rows):
    sel = st.session_state[key].selection.rows
    if sel:
        st.session_state.cr_sel = rows[sel[0]]
        if T.people.get(rows[sel[0]], 0) >= 10:  # only towns the sidebar Town picker lists
            st.session_state.town = st.session_state._town = rows[sel[0]]


def where_to_act(d):
    """The ranked list of towns to act in; a click opens the town."""
    st.markdown("**Where to act**", help="Towns above normal, the most urgent first.")
    if d.empty:
        st.caption("Every town is at normal.")
        return
    v = st.session_state.get("cr_v", 0)
    key = f"cr_rows_{v}"
    t = pd.DataFrame({"Status": d.status.map(WORD), "Town": d.municipality.map(anna.town),
                      "To clear": d.todo.astype(int), "Left": d.left})
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
                     "To clear": st.column_config.NumberColumn("To clear", width="small",
                                                               help="Homes with no news or asking for help")},
                 )


def back():
    st.session_state.cr_sel = None
    st.session_state.cr_v = st.session_state.get("cr_v", 0) + 1  # a fresh table, no row still selected


def town_card(m, d, H):
    """One town: what to do there, its homes, its worst-hit streets and where its people go."""
    r = d.set_index("municipality").loc[m] if m in d.municipality.values else None
    status = r.status if r is not None else "none"
    h = H[H.municipality == m]
    n = h.s.value_counts()
    a, b = st.columns([3, 1], vertical_alignment="center")
    a.markdown(f"### :{ROWS[status]}-badge[{WORD[status]}] {anna.town(m)}")
    b.button("Region", icon=":material/arrow_back:", on_click=back, width="stretch", key="cr_back")
    if h.empty:
        st.caption("No homes in the 2021 water here in our data.")
        return
    todo = int(n.get("no news", 0) + n.get("needs help", 0))
    st.markdown({"evacuate": f"**Clear {fmt(todo)} homes now.** Help requests first, then single-storey homes.",
                 "warn": f"**Get {fmt(todo)} homes ready to leave.** No order yet.",
                 "watch": "**River rising.** No action yet; check the list is ready."}.get(
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
    go = anna.plan_shelters().query("municipality == @m").nlargest(3, "people")
    if len(go):
        st.markdown("**Where they go**", help="The town's 10 km shelter plan: candidate sites that stayed dry in 2021 "
                                              "and in the 100-year model. Not official shelters.")
        st.markdown("  \n".join(f":green[:material/home_health:] **{g.label}** · {g.address or 'no street address'}"
                                f" · {about(g.people)} people" for g in go.itertuples()))
    if T.people.get(m, 0) >= 10:
        a, b = st.columns(2)
        a.page_link("views/checkin.py", label="Door-knock list", icon=":material/how_to_reg:")
        b.page_link("views/evacuate.py", label="Town plan", icon=":material/directions_run:")


def named(n):
    """A road's name, or '' for unnamed OSM ways that carry their type ("service", "footway") as name."""
    return n if isinstance(n, str) and n[:1].isupper() else ""


def roads(s):
    """Evacuation roads (the busiest ways out, notebooks/evac_sim.py) of the towns at warn or evacuate, each with
    its people and whether it sat in the 2021 water; closed roads as lines where their OSM way is known."""
    E = checkin.edges()["features"]
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


def residents_feed(t, replay):
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
                    help="Check-ins sent from the resident page (Am I at risk?) or entered by crews, as they arrive. "
                         "Simulated replay check-ins are not listed here.")
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


def briefings(c):
    """Alerts on the left, the briefing drafts on the right: newest draft open, the others one click away."""
    ev = live.events().tail(6).iloc[::-1]
    allob = live.outbox()
    ob = allob.tail(8).iloc[::-1]
    st.subheader(":blue[:material/campaign:] Alerts and briefings",
                 help="At each rise of a town's alert the tool drafts one briefing for the mayor and one for the "
                      "district fire brigade. Claude writes the words, every figure comes from the tool; a template "
                      "when no AI is available. Nothing is sent from here.")
    a, b = st.columns([2, 3], gap="large")
    with a:
        st.markdown("**Latest alerts**")
        if ev.empty:
            st.caption("Nothing yet. Press Play in the sidebar.")
        for r in ev.itertuples():
            st.markdown(f":{ROWS.get(r.to, 'gray')}-badge[{WORD.get(r.to, r.to)}] **{anna.town(r.municipality)}** "
                        f"· {when(r.t, c['mode'])}")
    with b:
        st.markdown(f"**Drafts ready to send** :blue-badge[{len(allob)}]")
        if ob.empty:
            st.caption("A draft appears here each time a town's alert rises.")
            return
        lab = {r.id: f"{r.recipient} · {when(r.t, c['mode'])}" for r in ob.itertuples()}
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
    t = c["t"]
    live.tick(t)
    replay = c["mode"] == "replay"
    s = live.towns_status(t).sort_values("level").drop_duplicates("municipality", keep="last")  # worst status
    H = homes_now()
    d = towns_now(s, H)
    color, head, detail = verdict(live.summary(t), d, t, replay)
    core.banner(color, head, detail + (" Homes: simulated check-ins in the replay." if replay else ""), note=False)
    st.space("small")

    left, right = st.columns([3, 2], gap="medium")
    sel_t = st.session_state.get("cr_sel")
    with left:
        g = s.assign(lon=s.municipality.map(T.lon), lat=s.municipality.map(T.lat)).dropna(subset=["lon"])
        hs = H[H.municipality == sel_t] if sel_t else H.iloc[0:0]
        routes, closed = roads(s)
        sel = region_map(dict(
            towns=[dict(municipality=r.municipality, label=anna.town(r.municipality), lon=r.lon, lat=r.lat,
                        status=r.status if r.status in COL else "none", people=float(r.people),
                        people_expected=float(r.people_expected or 0), modelled=r.area in anna.MODELLED)
                   for r in g.itertuples()],
            areas=outlines(), flood=water_by_town(), routes=routes,
            homes={"type": "FeatureCollection", "sig": str(hs.s.value_counts().to_dict()), "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                 "properties": {"s": r.s}} for r in hs.itertuples()]},
            closures=closed, selected=sel_t), key="crisis_map", height=560)
        if sel and sel.get("selected") and sel.get("clicks") != st.session_state.get("cr_clicks"):
            st.session_state.cr_clicks = sel["clicks"]
            st.session_state.cr_sel = sel_t = sel["selected"]
            if T.people.get(sel_t, 0) >= 10:  # only towns the sidebar Town picker lists
                st.session_state.town = st.session_state._town = sel_t
        st.html("<div class='legend'>" + "".join(
            f"<span><i style='background:{COL[k]};opacity:.75'></i>{WORD[k]}</span>" for k in ("evacuate", "warn", "watch"))
            + "<span><i style='background:#0b3d91;opacity:.7'></i>2021 water</span>"
            + "<span><i style='background:#0071e3;height:.25rem;border-radius:2px'></i>Road out</span>"
            + "<span><i style='background:repeating-linear-gradient(90deg,#c93400 0 4px,transparent 4px 7px);height:.25rem'></i>Road out, flooded in 2021</span>"
            + "<span><i style='background:#d70015;height:.3rem;border-radius:2px'></i>Closed</span>"
            + ("<span><i style='background:#d70015;border-radius:50%'></i>Asked for help</span>"
               "<span><i style='background:#f2994a;border-radius:50%'></i>No news</span>"
               "<span><i style='background:#248a3d;border-radius:50%'></i>Has left</span>" if sel_t else
               "<span>Click a town to see its homes and roads</span>") + "</div>")
    with right:
        residents_feed(t, replay)
        st.space("small")
        if sel_t:
            town_card(sel_t, d, H)
        else:
            where_to_act(d)
    st.space("medium")
    briefings(c)


# 2021 for comparison: sourced times from docs/TIMELINE_2021.md (all verified in the cited document)
JRC = "https://european-flood.emergency.copernicus.eu/sites/default/files/2023-12/JRC135679_CEMS_EFAS_DetailedAssessmentReport_RhineMeuseFloodsJuly2021_FINAL.pdf"
Y2021 = [("ahr", "Ahr", f"13 Jul 11:25, flash-flood notice for the Koblenz region ([JRC]({JRC}))",
          "14 Jul 23:09, Kreis Ahrweiler: leave 50 m either side of the Ahr "
          "([Landtag RLP](https://dokumente.landtag.rlp.de/landtag/vorlagen/5776-V-18.pdf))"),
         ("vesdre", "Vesdre", f"13 Jul 11:26, flash-flood notice for Liège province ([JRC]({JRC}))",
          "14 Jul 17:57, Province of Liège: general order for the Vesdre valley ([Walloon Parliament](https://www."
          "wallonie.be/sites/default/files/2022-11/Inondations%20rapport%20de%20la%20commission%20parlementaire.pdf))"),
         ("erftstadt", "Erft", f"None received: NRW was not yet an EFAS partner ([JRC]({JRC}))",
          "15 Jul about 08:10, Erftstadt: evacuate Blessem and Bliesheim "
          "([Stadt Erftstadt](https://www.radioerft.de/files/pdf2/pm-stellungnahme-zur-wdr-berichterstattung-am-23.08.2021.pdf))")]


def then_2021():
    st.caption("EFAS notices and the first evacuation orders of 2021, against the first day the tool puts a town of "
               "that river at evacuate. Sources: docs/TIMELINE_2021.md. Tool column: the day, from flows computed afterwards; not the forecast available at the time.")
    # the day whose daily flow (placed at noon) first puts a town of the river at evacuate; the hourly replay
    # interpolates towards the next day's mean, which would claim hours the daily data cannot give
    rp, area = live._replay(), live._towns().area.values
    noon = [i for i, t in enumerate(rp["index"]) if t.hour == 12]
    day = {a: next((rp["index"][i] for i in noon if (rp["status"][i][area == a] == "evacuate").any()), None)
           for a, *_ in Y2021}
    # a four-column table cannot fit 390 px: it keeps its width and scrolls sideways inside its own box
    st.html("<style>.st-key-y2021{overflow-x:auto}.st-key-y2021 table{min-width:640px}</style>")
    st.container(key="y2021").markdown("| River | EFAS warned | 2021 evacuation order | Tool: river at evacuate level (replay day) |\n"
                "|---|---|---|---|\n" +
                "\n".join(f"| {name} | {efas} | {order} | " + (f"{day[a]:%d Jul} ({live.drill(day[a]):%a %d %b})"
                                                              if day[a] is not None else "not reached") + " |"
                           for a, name, efas, order in Y2021))


st.title("Crisis room")
st.html("<style>.st-key-feed{background:#fff;border-radius:12px;padding:.8rem 1rem .75rem}"
        ".st-key-feed p{margin-bottom:.15rem}.st-key-draft{background:#fff;max-height:340px;overflow:auto}"
        ".st-key-draft p,.st-key-draft li{font-size:.95rem;line-height:1.5;max-width:75ch}</style>")
t1, t2, t3 = st.tabs([":red[:material/crisis_alert:] Live board", ":violet[:material/priority_high:] Priorities",
                      ":blue[:material/water:] Rivers"])
with t1:
    st.fragment(board, run_every=1.5 if c["playing"] else 3)()
    st.space("small")
    if c["mode"] == "replay":
        with st.expander("Compared with July 2021: when the orders came", icon=":material/history:"):
            then_2021()
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(
            "- **Alert level:** GloFAS river flow on each town's river against that point's own 2-, 5- and 20-year "
            "floods (watch, warn, evacuate; src/impact.py). Live: the ensemble runs over the next 10 days, a level "
            "counting when 30 % of the runs reach it. Replay: the backtest, the 2021 flows on thresholds fitted on "
            "1997–2020, what was known before the flood. Status uses the highest flow reached so far: levels never "
            "drop during a replay.\n"
            "- **People expected:** residents in the EFAS flood zone of that return period (no dikes, so the Meuse is "
            "an upper bound; no zone on small streams such as the Urft at Kall).\n"
            "- **Replay of the 2021 forecast:** it steps on daily modelled flows (GloFAS reanalysis, computed afterwards), so it "
            f"gives the day, not the hour. Shown as if it began on {live.drill(live.START):%a %d %b %Y}: the dates are "
            "moved, the flows are those of 12-17 July 2021. A model replay, not official warnings.\n"
            "- **People to move:** residents inside the 2021 satellite flood of the towns at evacuate, a floor. The "
            "Vesdre valley has no satellite map: its residents come from the EFAS 500-year model and are shown apart.\n"
            "- **Homes safe / need help:** check-ins per home; in the replay they are simulated.\n"
            "- **Briefings:** queued at each rise for the mayor and the district fire brigade; Claude writes the words, "
            "every figure comes from the tool. Nothing is sent.\n"
            "- **July 2021 comparison:** the first day whose mean river flow puts a town of that river at evacuate. "
            "Times and sources: docs/TIMELINE_2021.md.\n"
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
