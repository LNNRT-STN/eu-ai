"""Door-knock list for fire crews and crisis managers: every home in the flood zone of the scenario (the rarest
return period the crisis room switched on; the 100-year zone when none is) with no news, those who asked for help
first, then single-storey homes; what to tell each home (its nearest dry shelter of the plan, the address, road km);
crews set each home's status in the table after knocking; and the roads crews close and reopen. The town comes from
the sidebar Town picker. Residents report "I have left" or "I need help" on the resident page (views/resident.py, checkin_form), by
street and house number. Addresses: OpenStreetMap matched to GHS-OBAT buildings (notebooks/addresses.py, ODbL).
No names or phone numbers are stored: only the address, where people are and how many. Check-ins stay on this machine
(src/live.py, data/live.db, gitignored). Drill check-ins are labelled and removable in one click.

Imported by views/resident.py (WHERE) and views/crisis.py (doors, edges); the page draws only when run as the page."""
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
def doors(variant):
    """One row per home address in a return period's zone (variant rp10 / rp100 / rp500); homes without an OSM
    address keep their building id."""
    a = pd.read_parquet(core.DATA / "addresses.parquet")
    a = a[(a.use == 1) & a[f"in_{variant}"]].copy()
    a["door"] = a.label.where(a.label.astype(bool), "No address · " + a.bid)
    a.loc[a.label.astype(bool) & a.street.isna(), "door"] = "House no. " + a.housenumber + " (no street name)"
    a["single"] = (a.storeys == 1) & (a.height_m != 2.5)
    return (a.groupby(["municipality", "door"], as_index=False)
            .agg(street=("street", "first"), number=("housenumber", "first"), lon=("lon", "mean"), lat=("lat", "mean"),
                 buildings=("bid", "size"), single=("single", "any"), has_address=("label", lambda x: x.iloc[0] != "")))


@st.cache_data
def edges(variant):
    """Evacuation roads of one return period (notebooks/evac_sim.py); in_flood_2021 = inside that variant's zone."""
    E = json.loads((core.DATA / "evac_edges.geojson").read_text())
    return {"type": "FeatureCollection", "features": [f for f in E["features"] if f["properties"]["variant"] == variant]}


def munis(v):
    """Towns with homes in the zone, most people first."""
    towns, D = anna.load()[1], doors(v)
    return (towns[towns.variant == v].sort_values("people", ascending=False).municipality
            .drop_duplicates().loc[lambda m: m.isin(D.municipality)].tolist())


MIN = live.MIN_PEOPLE
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
                                             help="Nearest shelter in the town's 10 km plan: a candidate site outside "
                                                  "the flood zone, not an official shelter"),
           "go_address": st.column_config.TextColumn("Shelter address", width="medium", disabled=True),
           "go_km": st.column_config.NumberColumn("km", format="%.1f", width="small", disabled=True,
                                                  help="By road, about: straight line × 1.3"),
           "people": st.column_config.TextColumn("People", width="small", validate=r"^\d{0,2}$",
                                                 help="People in this home, as reported; blank if unknown")}
    ppl = df.people.map(lambda n: str(int(n)) if pd.notna(n) and n else "")  # blank, not "None", when unknown
    st.data_editor(df.drop(columns="status").assign(people=ppl), hide_index=True, height=height or "auto",
                   column_config=cfg,
                   key=key, on_change=save, args=(muni, key), num_rows="fixed")


def crews(muni, v):
    here = doors(v)[lambda d: d.municipality == muni]
    p = live.plan()
    ci = live.checkins(muni)
    last = (live.latest(ci).set_index("door") if len(ci)
            else pd.DataFrame(columns=COLS + ["id", "sim"]).set_index("door"))
    L = here.merge(last[["status", "where", "people", "drill", "sim"]], left_on="door", right_index=True, how="left")
    L["status"] = L.status.fillna("no news")
    order = {"needs help": 0, "no news": 1, "safe": 2}
    L = L.assign(o=L.status.map(order), s=~L.single).sort_values(["o", "s", "street", "door"]).reset_index(drop=True)
    if bool(len(ci) and (ci.drill.astype(bool) | ci.sim.astype(bool)).any()):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.warning("Includes drill check-ins, not real ones.", icon=":material/science:")
        b.button("Clear drill", icon=":material/restart_alt:", key="ci_clear", on_click=live.clear_drill,
                 args=(muni,), help="Remove the drill check-ins for this town.")
    L = anna.destinations(muni, L, v)
    n = L.status.value_counts()
    single_open = int((L.single & (L.status == "no news")).sum())
    town_status = live.towns_status().set_index("municipality").status.get(muni, "none")
    todo_n = int(n.get("needs help", 0) + n.get("no news", 0))
    st.markdown({"evacuate": f":red-badge[Evacuate] **Knock on {fmt(todo_n)} doors in the {p}-year zone.** "
                             f"{fmt(n.get('needs help', 0))} asked for help: go there first, then the "
                             f"{fmt(single_open)} single-storey homes.",
                 "watch": f":yellow-badge[Watch] **Under {MIN} residents in the {p}-year zone: no order. "
                          f"{fmt(todo_n)} homes on the list.**"}.get(
        town_status, f":gray-badge[Normal] **No flood scenario is on. In a 100-year flood, {fmt(todo_n)} homes "
                     "would be on the list.**"))
    # what crews tell each home: its shelter, the address, and the roads to avoid
    cl = live.closures()
    cl = cl[cl.municipality == muni]
    go = (L[L.status != "safe"].groupby(["go", "go_address"], as_index=False)
          .agg(homes=("door", "size"), km=("go_km", "median")).sort_values("homes", ascending=False))
    go = go[go.go != ""]
    if len(go):
        tell = "; ".join(f"**{g.go}**{', ' + g.go_address if g.go_address else ''} ({fmt(g.homes)} homes, about "
                         f"{g.km:.1f} km)" for g in go.head(3).itertuples())
        st.markdown(f":material/campaign: **Tell each home:** leave now, take medicines, papers and a charger, go to "
                    f"its shelter (column *Send them to*): {tell}"
                    + (f"; {len(go) - 3} more" if len(go) > 3 else "") + "."
                    + (" **Roads closed:** " + ", ".join(cl.name.fillna(cl.osm_id).astype(str)) + "." if len(cl) else ""),
                    help="The nearest dry shelter in the town's 10 km plan for this flood, by straight line × 1.3. "
                         "Candidate sites, not official shelters: confirm each is open before sending people.")
    else:
        st.markdown(":material/campaign: **No dry shelter in the 10 km plan for this town:** ask the crisis room "
                    "where to send people.")
    st.progress(n.get("safe", 0) / max(len(L), 1),
                text=f"{fmt(n.get('safe', 0))} of {fmt(len(L))} homes have left")

    L["label"] = L.status.map(STATUS)
    ver = st.session_state.get("ci_v", 0)
    show = st.segmented_control(
        "Show", ["To knock", "Asked for help", "Has left"], default="To knock", key=f"ci_show_{muni}",
        label_visibility="collapsed",
        format_func={"To knock": f"To knock · {fmt(todo_n)}",
                     "Asked for help": f"Asked for help · {fmt(n.get('needs help', 0))}",
                     "Has left": f"Has left · {fmt(n.get('safe', 0))}"}.get) or "To knock"
    rows = {"To knock": L[L.status != "safe"], "Asked for help": L[L.status == "needs help"],
            "Has left": L[L.status == "safe"]}[show]
    cols = (["door", "label", "people", "status", "where"] if show == "Has left" else
            ["door", "label", "people", "status", "single", "go", "go_address", "go_km"])
    st.caption(":material/edit: Knocked? Set the Status: the list, the map and the crisis room follow.")
    editor(rows[cols], f"ci_{show}_{muni}_{ver}", muni, height=min(36 * len(rows) + 38, 420))
    a, b = st.columns([1, 3], vertical_alignment="center")
    a.download_button("Download the list", rows[["door", "status", "single", "people", "go", "go_address", "go_km",
                                                 "lat", "lon"]]
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
    roads_box = st.expander(f"Roads closed · {len(cl)}", icon=":material/block:")
    roads_box.caption("Closed here, they show on the Crisis room map. 'Auto' closures come from the scenario: the "
                      "busiest evacuation roads inside the flood zone of towns told to evacuate.")
    with roads_box:
        roads(muni, cl, v)


def roads(muni, cl, v):
    for r in cl.itertuples():
        a, b = st.columns([5, 1], vertical_alignment="center")
        a.markdown(f"**{r.name or r.osm_id}** · {'auto, in the ' + v[2:] + '-year zone' if r.auto else 'by ' + r.by}"
                   f"{' · ' + r.note if r.note else ''}")
        b.button("Reopen", key=f"reopen{r.id}", on_click=live.reopen, args=(r.id,))
    if cl.empty:
        st.caption("No road closed in this town.")
    E = edges(v)
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


def method(muni, v):
    here = doors(v)[lambda d: d.municipality == muni]
    no_addr = int((~here.has_address).sum())
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(
            f"- **Doors.** {fmt(len(here))} doors to check: {fmt(int(here.buildings.sum()))} homes in the {v[2:]}-year "
            "flood zone (EFAS model, no dikes: towns behind dikes are an upper bound), "
            f"grouped by address (several buildings can share one). {fmt(no_addr)} have no OpenStreetMap address and "
            "are listed by map point" + (" (most Venlo-area homes)."
                                         if "(NL)" in muni else ".") + "\n"
            "- **Order.** Help requests first, then homes with no news, single-storey first, then by street.\n"
            "- **Send them to.** The nearest shelter of the town's 10 km plan for this flood (candidate sites outside "
            "the zone, not official shelters); km by road is about the straight line × 1.3.\n"
            "- **Crew updates.** A status a crew sets in the table is stored as a check-in. The newest report per home "
            "counts, here and in the Crisis room.\n"
            "- **Check-ins.** Residents report on the *Am I at risk?* page, by street and house number. No name or "
            "phone number is stored: only the address, where people are and how many.\n"
            "- **Reached by alert.** BE-Alert SMS delivery reports or help-line call results would plug in here; no "
            "feed is connected, and cell broadcast cannot confirm delivery.\n"
            "- **Sources.** Addresses: OpenStreetMap (ODbL) matched to GHS-OBAT buildings and the EFAS 10-, 100- and "
            "500-year flood zones. Heights (single-storey): GHS-OBAT. Map: © CARTO, © OpenStreetMap contributors.")


def page():
    v = live.variant()
    M = munis(v)
    muni = st.session_state.get("town") if st.session_state.get("town") in M else M[0]
    st.title("Door-knock list", help="Residents say they have left. Crews see who has not, and go there first. "
                                     "Pick the town in the sidebar.")
    st.subheader(f"{anna.town(muni)} · {v[2:]}-year flood zone")
    st.fragment(crews)(muni, v)
    method(muni, v)
    core.next_steps("doors")


if __name__ == "__main__":  # run as the page (Streamlit runs page files as __main__), not when imported
    page()
