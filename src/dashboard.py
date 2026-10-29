"""Action dashboard for crisis and risk managers in the July 2021 flood areas. Reads the cleaned data in
outputs/data; the river outlook needs forecast.py (once) and build_priority.py (replay). The First action page reads
notebooks/pipeline.py, dq_report.py and q4_ranking.py outputs. Run: streamlit run src/dashboard.py

On launch the visitor picks a role (resident, crisis manager, fire brigade, policy maker); each role sees only its
pages. ?role=<key> in the URL skips the choice (demo links, test renders)."""
import pandas as pd
import streamlit as st

import anna
import core
import live

st.set_page_config(page_title="Flood desk", page_icon=":material/water:", layout="wide",
                   initial_sidebar_state="auto")

# page key: (file, title, icon, colour, what it is for: the sidebar ? tooltip)
PAGES = {
    "crisis": ("views/crisis.py", "Crisis room", ":material/crisis_alert:", "red",
               "The whole region at a glance: which towns must evacuate, what is still coming, and the briefings for "
               "mayors and fire brigades. Tabs for the priorities (care sites, shelter gaps) and the river outlook."),
    "plan": ("views/evacuate.py", "Town plan", ":material/directions_run:", "orange",
             "One town: who leaves, where they go, the roads out, who gives the order, its shelters and its valley "
             "in 3D. Pick the town in the sidebar."),
    "doors": ("views/checkin.py", "Door-knock list", ":material/how_to_reg:", "orange",
              "Homes in the 2021 water that have not reported safe, street by street, and the roads crews have "
              "closed."),
    "resident": ("views/resident.py", "Am I at risk?", ":material/home_pin:", "blue",
                 "Type your address: do you need to leave, where to and how long it takes. Tell crews you are safe, "
                 "or offer a spare bed."),
    "assess": ("views/then_now.py", "2021, today, next", ":material/history:", "violet",
               "What the July 2021 water covered, what has been done there since, and what still needs fixing, "
               "with the money that exists for it."),
    "limits": ("views/limits.py", "Data & limits", ":material/info:", "gray",
               "Where every number comes from, and what it cannot tell you."),
}
# role key: (name, icon, colour, who it is for, its pages; the first opens on arrival)
ROLES = {
    "manager": ("Crisis manager", ":material/crisis_alert:", "red",
                "Mayors, district and provincial crisis staff. Decide who leaves and give the order.",
                ["crisis", "plan", "doors", "assess", "limits"]),
    "brigade": ("Fire brigade", ":material/fire_truck:", "orange",
                "Crews on the ground. Who has not left yet, the way out, the roads to close.",
                ["doors", "plan", "crisis", "limits"]),
    "resident": ("Resident", ":material/home:", "blue",
                 "People who live in the flood areas. Do I need to leave, and where do I go?",
                 ["resident"]),
    "policy": ("Policy maker", ":material/account_balance:", "violet",
               "What 2021 hit, what has changed since, and how the region would do if it came back.",
               ["assess", "crisis", "plan", "limits"]),
}
EU, EU_YELLOW = "#203e5f", "#ffcc00"  # EU navy for icons, EU yellow for the role tiles' accent bar
TOWN_PAGES = {"Town plan", "Door-knock list"}

if st.query_params.get("role") in ROLES and "role" not in st.session_state:
    st.session_state.role = st.query_params["role"]
role = st.session_state.get("role")

# coloured icons: each nav row and role tile is a keyed container, styled by its key
st.html("<style>" + "".join(
    f".st-key-nav-{k} [data-testid=stIconMaterial]{{color:{EU}}}" for k in PAGES) + "".join(
    f".st-key-role-{k}{{border-top:3px solid {EU_YELLOW}!important}}.st-key-role-{k} [data-testid=stIconMaterial]{{color:{EU}}}"
    for k in ROLES) + """
[class*=st-key-nav-] [data-testid=stPageLink] a{padding:.3rem .55rem;border-radius:8px;position:relative}
/* the page's explanation is a tooltip on the row; a ? appears on hover to say so */
[class*=st-key-nav-] [data-testid=stPageLink] a::after{content:"?";position:absolute;right:.55rem;top:50%;
  transform:translateY(-50%);width:1.05rem;height:1.05rem;border-radius:50%;border:1.5px solid #5a6e87;color:#4f6580;
  font-size:.7rem;font-weight:700;display:grid;place-items:center;opacity:0;transition:opacity .15s ease-out}
[class*=st-key-nav-] [data-testid=stPageLink] a:hover::after,
[class*=st-key-nav-] [data-testid=stPageLink] a:focus-visible::after{opacity:1}
.st-key-roles [data-testid=stVerticalBlockBorderWrapper],[class*=st-key-role-]{background:#fff}
</style>""")


def pick(k):
    st.session_state.role = k
    st.query_params["role"] = k


def launch():
    st.title("Flood desk")
    st.markdown(f"**Replay of the 2021 forecast, from {live.drill(live.START):%A %-d %B %Y}.** The July 2021 flood in Belgium, the Netherlands "
                "and Germany, replayed as if it were arriving now.",
                help="The river flows are those of 12-17 July 2021, modelled afterwards (GloFAS). Only the dates move. "
                     "Not an official warning: those come from SPW, Rijkswaterstaat and the German state flood centres.")
    st.subheader("Who are you?")
    cols = st.columns(4, gap="small")
    for col, (k, (name, ic, _c, who, _p)) in zip(cols, ROLES.items()):
        with col.container(border=True, key=f"role-{k}", height="stretch"):
            st.markdown(f"## :{_c}[{ic}]")
            st.markdown(f"**{name}**")
            st.caption(who)
            st.button(f"Continue as {name.lower()}", key=f"go-{k}", on_click=pick, args=(k,),
                      type="primary" if k == "manager" else "secondary", width="stretch")


# the replay's days, to jump to: its start, then each midnight (flows are daily, so status changes at midnight)
DAYS = [live.START] + list(pd.date_range(live.START.normalize() + pd.Timedelta(days=1), live.END, freq="D"))


def seek():
    live.seek(st.session_state.sc_time)
    st.session_state._seeked = True  # the fragment reruns the whole page, so the other views follow


def now():
    """Where the shared clock stands, and a slider to jump to any day of the replay; moves the clock while playing,
    so every role sees the same moment."""
    k = live.advance()
    t = f"{live.drill(k['t']):%a %-d %b, %H:%M}" if k["mode"] == "replay" else f"{k['t']:%a %-d %b, %H:%M}"
    st.caption(f":material/{'play_arrow' if k['playing'] else 'pause'}: **{t}**"
               + (" · replay of the 2021 forecast" if k["mode"] == "replay" else " · live forecast"))
    if k["mode"] == "replay":
        st.session_state.sc_time = max(d for d in DAYS if d <= k["t"])
        st.select_slider("Jump to", DAYS, key="sc_time", on_change=seek,
                         format_func=lambda d: f"{live.drill(d):%a %-d %b}" + (" 06:00" if d == live.START else ""),
                         help="Pick a day of the replay. Going back rebuilds that moment: alerts, briefings, "
                              "closed roads and simulated check-ins as they stood then.")
    if st.session_state.pop("_seeked", False):
        st.rerun()


def scenario():
    """The scenario player, for every role: one clock shared by all sessions (src/live.py), so what the crisis
    manager plays, the fire brigade and the residents see too. Widgets follow the clock, not the other way round:
    another session may have changed it."""
    c = live.clock()
    st.session_state.sc_mode = c["mode"]
    st.session_state.sc_speed = float(c["speed"]) if c["speed"] in (1, 3, 6, 12) else 3.0
    st.caption("Scenario", help="Replay the July 2021 river flows as if they started today, to see how the tool "
                                "works in practice. The clock is shared: every role sees the same moment.")
    st.segmented_control("Mode", ["replay", "live"], key="sc_mode", label_visibility="collapsed",
                         format_func={"replay": "Replay: 2021 forecast", "live": "Live forecast"}.get,
                         on_change=lambda: st.session_state.sc_mode and live.set_mode(st.session_state.sc_mode))
    b1, b2 = st.columns(2)
    if c["playing"]:
        b1.button("Pause", icon=":material/pause:", on_click=live.pause, width="stretch")
    else:
        b1.button("Play", icon=":material/play_arrow:", on_click=live.play, type="primary", width="stretch")
    b2.button("Reset", icon=":material/replay:", on_click=live.reset, width="stretch",
              help=f"Back to {live.drill(live.START):%a %d %b} 06:00 (the 12 July 2021 river flows); clears alerts, "
                   "reports, closures and simulated check-ins")
    st.select_slider("Speed", [1.0, 3.0, 6.0, 12.0], key="sc_speed", format_func=lambda x: f"{x:g} h per second",
                     on_change=lambda: live.set_speed(st.session_state.sc_speed))
    st.fragment(now, run_every=1.5 if c["playing"] else None)()


if role is None:
    st.navigation([st.Page(launch, title="Flood desk", icon=":material/water:")], position="hidden").run()
    st.stop()

name, ric, rcol, _who, keys = ROLES[role]
pages = {k: st.Page(PAGES[k][0], title=PAGES[k][1], icon=PAGES[k][2], default=(k == keys[0])) for k in keys}
nav = st.navigation(list(pages.values()), position="hidden")

with st.sidebar:
    a, b = st.columns([3, 2], vertical_alignment="center")
    a.markdown(f":{rcol}[{ric}] **{name}**")
    b.button("Switch", icon=":material/swap_horiz:", type="tertiary", help="Choose another role",
             on_click=lambda: (st.session_state.pop("role", None), st.query_params.clear()))
    for k in keys:
        with st.container(key=f"nav-{k}"):
            st.page_link(pages[k], label=PAGES[k][1], icon=PAGES[k][2], help=PAGES[k][4], width="stretch")
    # one Town picker for every page that works on a town; _town keeps the choice while other pages are open
    if nav.title in TOWN_PAGES:
        st.divider()
        tw = anna.load()[1]
        tw = tw[(tw.variant == "worst") & (tw.people >= 10)].sort_values("people", ascending=False)
        st.session_state.setdefault("_town", tw.municipality.iloc[0])
        st.session_state.town = st.session_state._town
        lab = dict(zip(tw.municipality, tw.label + " · " + tw.people.map(core.about) + " in the 2021 water"))
        st.selectbox("Town", list(lab), format_func=lab.get, key="town",
                     on_change=lambda: st.session_state.update(_town=st.session_state.town))

    st.divider()
    scenario()

nav.run()

# footer last, so each page's own sidebar controls sit right under the navigation
if role != "resident":
    with st.sidebar:
        st.divider()
        gauges, *_, fetched, err = core.outlook()
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.caption("Live river outlook" + (f" · {fetched:%H:%M}" if fetched is not None else " · unavailable"),
                   help="Open-Meteo GloFAS, the real 30-day outlook for today (not the replay).")
        if c2.button("", icon=":material/refresh:", type="tertiary", help="Refresh the live outlook"):
            core._outlook.clear()
            st.rerun()
