"""Door-knock list for fire crews and crisis managers: every home in the 2021 water with no news, those who asked for
help first, then single-storey homes; crews set each home's status in the table after knocking; and the roads
crews close and reopen. The town comes from the sidebar Town
picker. Residents report "I have left" or "I need help" on the resident page (views/resident.py, checkin_form), by
street and house number. Addresses: OpenStreetMap matched to GHS-OBAT buildings (notebooks/addresses.py, ODbL).
No names or phone numbers are stored: only the address, where people are and how many. Check-ins stay on this machine
(src/live.py, data/live.db, gitignored). The July 2021 replay adds simulated check-ins, labelled, removable in one click.

Imported by views/resident.py for doors() and WHERE; the page itself draws only when run as the page."""
import json
import re

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
import live
from core import fmt

COLS = ["when", "municipality", "door", "status", "where", "people", "drill"]
WHERE = ["A shelter", "Family or friends", "A spare bed offered by a resident", "Elsewhere, outside the flood zone"]


@st.cache_data
def doors():
    """One row per home address in the 2021 water; homes without an OSM address keep their building id."""
    a = pd.read_parquet(core.DATA / "addresses.parquet")
    a = a[a.use == 1].copy()
    a["door"] = a.label.where(a.label.astype(bool), "No address · " + a.bid)
    a.loc[a.label.astype(bool) & a.street.isna(), "door"] = "House no. " + a.housenumber + " (no street name)"
    a["single"] = (a.storeys == 1) & (a.height_m != 2.5)
    return (a.groupby(["municipality", "door"], as_index=False)
            .agg(street=("street", "first"), number=("housenumber", "first"), lon=("lon", "mean"), lat=("lat", "mean"),
                 buildings=("bid", "size"), single=("single", "any"), has_address=("label", lambda x: x.iloc[0] != "")))


@st.cache_data
def edges():
    return json.loads((core.DATA / "evac_edges.geojson").read_text())


def munis():
    """Towns with homes in the 2021 water, most people first."""
    towns, D = anna.load()[1], doors()
    return (towns[towns.variant == "worst"].sort_values("people", ascending=False).municipality
            .drop_duplicates().loc[lambda m: m.isin(D.municipality)].tolist())


STATUS = {"needs help": "Needs help", "no news": "No news", "safe": "Has left"}
CODE = {v: k for k, v in STATUS.items()}
CREW = "Checked by a crew"


def save(muni, key):
    """Write a crew's status edits in the door table as check-ins (the newest report per home wins), then start the
    table afresh so the edited rows re-sort."""
    rows = st.session_state[f"{key}_rows"]
    for i, ch in st.session_state[key]["edited_rows"].items():
        r = rows[int(i)]
        lab = ch.get("label", STATUS[r["status"]])
        if lab not in CODE or (lab == STATUS[r["status"]] and "people" not in ch):
            continue
        ppl = pd.to_numeric(ch.get("people") or r["people"], errors="coerce")
        ppl = int(ppl) if pd.notna(ppl) and ppl > 0 else 1
        live.add_checkin(muni, r["door"], CODE[lab], CREW if lab == "Has left" else "", ppl)
    st.session_state.ci_v = st.session_state.get("ci_v", 0) + 1


def editor(df, key, muni, height=None):
    """Door table where only Status and People are editable; edits are saved by save()."""
    st.session_state[f"{key}_rows"] = df[["door", "status", "people"]].to_dict("records")
    df = df.assign(go_address=df.go_address.replace("", "no street address")) if "go_address" in df else df
    cfg = {"door": st.column_config.TextColumn("Address", width="medium", disabled=True),
           "label": st.column_config.SelectboxColumn("Status", options=list(CODE), required=True, width="small",
                                                     help="Set it after knocking: Has left takes the home off the list"),
           "single": st.column_config.CheckboxColumn("1 storey", width="small", disabled=True,
                                                     help="Single-storey home: no upper floor to escape to"),
           "where": st.column_config.TextColumn("Where they are", disabled=True),
           "go": st.column_config.TextColumn("Send them to", width="medium", disabled=True,
                                             help="Nearest shelter in the town's 10 km plan: a candidate site, dry in "
                                                  "2021, not an official shelter"),
           "go_address": st.column_config.TextColumn("Shelter address", width="medium", disabled=True),
           "people": st.column_config.TextColumn("People", width="small", validate=r"^\d{0,2}$",
                                                 help="People in this home, as reported; blank if unknown")}
    ppl = df.people.map(lambda n: str(int(n)) if pd.notna(n) and n else "")  # blank, not "None", when unknown
    st.data_editor(df.drop(columns="status").assign(people=ppl), hide_index=True, height=height or "auto",
                   column_config=cfg,
                   key=key, on_change=save, args=(muni, key), num_rows="fixed")


def crews(muni):
    here = doors()[lambda d: d.municipality == muni]
    c = live.clock()
    if c["mode"] == "replay":
        st.caption(f":orange[:material/history:] Replay of July 2021 · {live.drill(c['t']):%a %-d %b, %H:%M} · not a forecast")
    ci = live.checkins(muni)
    last = (live.latest(ci).set_index("door") if len(ci)
            else pd.DataFrame(columns=COLS + ["id", "sim"]).set_index("door"))
    L = here.merge(last[["status", "where", "people", "drill", "sim"]], left_on="door", right_index=True, how="left")
    L["status"] = L.status.fillna("no news")
    order = {"needs help": 0, "no news": 1, "safe": 2}
    L = L.assign(o=L.status.map(order), s=~L.single).sort_values(["o", "s", "street", "door"]).reset_index(drop=True)
    if bool(len(ci) and (ci.drill.astype(bool) | ci.sim.astype(bool)).any()):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.warning("Includes simulated check-ins from the July 2021 replay, not real ones.", icon=":material/science:")
        b.button("Clear simulated", icon=":material/restart_alt:", key="ci_clear", on_click=live.clear_drill,
                 args=(muni,), help="Remove the simulated check-ins for this town. None come back until Reset.")
    L = anna.destinations(muni, L)
    n = L.status.value_counts()
    single_open = int((L.single & (L.status == "no news")).sum())
    lvl = live.towns_status().sort_values("level").drop_duplicates("municipality", keep="last")
    town_status = lvl.set_index("municipality").status.get(muni, "none")
    todo_n = int(n.get("needs help", 0) + n.get("no news", 0))
    st.markdown({"evacuate": f":red-badge[Evacuate] **Knock on {fmt(todo_n)} doors.** "
                             f"{fmt(n.get('needs help', 0))} asked for help: go there first, then the "
                             f"{fmt(single_open)} single-storey homes.",
                 "warn": f":orange-badge[Warn] **Get ready: {fmt(todo_n)} homes to clear if the order comes.**",
                 "watch": f":yellow-badge[Watch] **River rising. {fmt(todo_n)} homes on the list, no order yet.**"}.get(
        town_status, f":gray-badge[Normal] **No order. {fmt(todo_n)} homes would be on the list.**"))
    st.progress(n.get("safe", 0) / max(len(L), 1),
                text=f"{fmt(n.get('safe', 0))} of {fmt(len(L))} homes have left")

    L["label"] = L.status.map(STATUS)
    v = st.session_state.get("ci_v", 0)
    show = st.segmented_control(
        "Show", ["To knock", "Asked for help", "Has left"], default="To knock", key=f"ci_show_{muni}",
        label_visibility="collapsed",
        format_func={"To knock": f"To knock · {fmt(todo_n)}",
                     "Asked for help": f"Asked for help · {fmt(n.get('needs help', 0))}",
                     "Has left": f"Has left · {fmt(n.get('safe', 0))}"}.get) or "To knock"
    rows = {"To knock": L[L.status != "safe"], "Asked for help": L[L.status == "needs help"],
            "Has left": L[L.status == "safe"]}[show]
    cols = (["door", "label", "people", "status", "where"] if show == "Has left" else
            ["door", "label", "people", "status", "single", "go", "go_address"])
    st.caption(":material/edit: Knocked? Set the Status: the list, the map and the crisis room follow.")
    editor(rows[cols], f"ci_{show}_{muni}_{v}", muni, height=min(36 * len(rows) + 38, 420))
    a, b = st.columns([1, 3], vertical_alignment="center")
    a.download_button("Download the list", rows[["door", "status", "single", "people", "go", "go_address", "lat", "lon"]]
                      .to_csv(index=False), file_name=f"door_knock_{anna.town(muni).replace(' ', '_')}.csv",
                      mime="text/csv", icon=":material/download:", key="ci_dl")

    color = {"needs help": core.rgb(core.EVACUATE), "no news": core.rgb("#c93400", 170),
             "safe": core.rgb(core.SHELTER, 200)}
    size = {"needs help": 8, "no news": 3, "safe": 4}  # help requests stand out, drawn last (on top)
    pts = L.assign(c=L.status.map(color), r=L.status.map(size), tname=L.door,
                   tinfo=[f"{STATUS[s]}{' · single-storey' if one else ''} · go to {g}"
                          for s, one, g in zip(L.status, L.single, L.go)]).sort_values("o", ascending=False)
    st.pydeck_chart(pdk.Deck(
        layers=[pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_fill_color="c", get_radius="r",
                          radius_units="'pixels'", stroked=True, get_line_color=[255, 255, 255],
                          line_width_min_pixels=1, pickable=True)],
        initial_view_state=pdk.ViewState(longitude=here.lon.median(), latitude=here.lat.median(), zoom=14),
        map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "<b>{tname}</b><br/>{tinfo}"},
        views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=380)
    st.caption(":red[⬤] Asked for help · :orange[●] No news · :green[●] Has left")

    # road closures: crews close and reopen; the crisis room map shows them
    cl = live.closures()
    cl = cl[cl.municipality == muni]
    roads_box = st.expander(f"Roads closed · {len(cl)}", icon=":material/block:")
    roads_box.caption("Closed here, they show on the Crisis room map. 'Auto' closures come from the replay: evacuation "
                      "roads in the 2021 water once the river reaches its 2021 peak.")
    with roads_box:
        roads(muni, cl)


def roads(muni, cl):
    for r in cl.itertuples():
        a, b = st.columns([5, 1], vertical_alignment="center")
        a.markdown(f"**{r.name or r.osm_id}** · {'auto, in the 2021 water' if r.auto else 'by ' + r.by}"
                   f"{' · ' + r.note if r.note else ''}")
        b.button("Reopen", key=f"reopen{r.id}", on_click=live.reopen, args=(r.id,))
    if cl.empty:
        st.caption("No road closed in this town.")
    E = edges()
    here_E = [f for f in E["features"] if f["properties"]["municipality"] == muni]
    # OSM fills a missing name with the road type ("secondary", "footway"): not a name a crew can use
    roads = [f["properties"]["name"] for f in here_E if f["properties"]["name"]
             and not re.fullmatch(r"[a-z_]+", f["properties"]["name"])]
    with st.form(f"close_{muni}", border=False):
        a, b, c3 = st.columns([3, 2, 1], vertical_alignment="bottom")
        road = a.selectbox("Road", list(dict.fromkeys(roads)), index=None, accept_new_options=True,
                           placeholder="Busiest evacuation roads first, or type a name")
        note = b.text_input("Why", placeholder="e.g. bridge under water")
        if c3.form_submit_button("Close road", icon=":material/block:") and road:
            f = next((f for f in here_E if f["properties"]["name"] == road), None)
            xy = f["geometry"]["coordinates"][0] if f else None
            if xy and isinstance(xy[0], list):
                xy = xy[0]
            if xy is None:  # typed name, not in our roads: pin it at the town centre so the Crisis room shows it
                ctr = anna.load()[1].drop_duplicates("municipality").set_index("municipality")
                xy, note = [ctr.at[muni, "lon"], ctr.at[muni, "lat"]], (note + " · " if note else "") + "position: town centre"
            live.close_road(road, muni, by="fire crew", note=note, lon=xy[0], lat=xy[1])
            st.rerun()


def method(muni):
    here = doors()[lambda d: d.municipality == muni]
    no_addr = int((~here.has_address).sum())
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(
            f"- **Doors.** {fmt(len(here))} doors to check: {fmt(int(here.buildings.sum()))} homes in the 2021 water, "
            f"grouped by address (several buildings can share one). {fmt(no_addr)} have no OpenStreetMap address and "
            "are listed by map point" + (" (most Venlo-area homes)."
                                         if "(NL)" in muni else ".") + "\n"
            "- **Order.** Help requests first, then homes with no news, single-storey first, then by street.\n"
            "- **Crew updates.** A status a crew sets in the table is stored as a check-in. The newest report per home "
            "counts, here and in the Crisis room.\n"
            "- **Check-ins.** Residents report on the *Am I at risk?* page, by street and house number. No name or "
            "phone number is stored: only the address, where people are and how many. In the replay, a growing share "
            "of homes in towns told to evacuate check in by simulation (one in several asks for help); these are "
            "labelled and can be cleared.\n"
            "- **Reached by alert.** BE-Alert SMS delivery reports or help-line call results would plug in here; no "
            "feed is connected, and cell broadcast cannot confirm delivery.\n"
            "- **Sources.** Addresses: OpenStreetMap (ODbL) matched to GHS-OBAT buildings and the July 2021 satellite "
            "flood map. Heights (single-storey): GHS-OBAT. Map: © CARTO, © OpenStreetMap contributors.")


def page():
    M = munis()
    muni = st.session_state.get("town") if st.session_state.get("town") in M else M[0]
    st.title("Door-knock list", help="Residents say they have left. Crews see who has not, and go there first. "
                                     "Pick the town in the sidebar.")
    st.subheader(anna.town(muni))
    st.fragment(crews, run_every=3 if live.clock()["playing"] else None)(muni)
    method(muni)


if __name__ == "__main__":  # run as the page (Streamlit runs page files as __main__), not when imported
    page()
