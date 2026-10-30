"""Action dashboard for crisis and risk managers in the July 2021 flood areas. Reads the cleaned data in
outputs/data; the river outlook needs forecast.py (once) and build_priority.py (replay). The First action page reads
notebooks/pipeline.py, dq_report.py and q4_ranking.py outputs. Run: streamlit run src/dashboard.py

On launch the visitor picks a role (crisis manager, fire brigade, resident); each role sees only its
pages. ?role=<key> in the URL skips the choice (demo links, test renders)."""
import pandas as pd
import streamlit as st

import anna
import core
import live

st.set_page_config(page_title="Flood desk", page_icon=":material/water:", layout="wide",
                   initial_sidebar_state="auto")

# page key: (file, title, icon, colour, what it is for)
PAGES = {
    "crisis": ("views/crisis.py", "Crisis room", ":material/crisis_alert:", "#d70015",
               "The whole region live: which towns evacuate, who has reported safe, and the briefings to send."),
    "plan": ("views/evacuate.py", "Town plan", ":material/directions_run:", "#c93400",
             "One town: who leaves, where they go, the roads out and who gives the order."),
    "doors": ("views/checkin.py", "Door-knock list", ":material/door_front:", "#a85400",
              "Homes in the 2021 water with no news yet, street by street, and the closed roads."),
    "resident": ("views/resident.py", "Am I at risk?", ":material/home_pin:", "#0071e3",
                 "Type your address: do you need to leave, where to, and tell crews you are safe."),
    "assess": ("views/then_now.py", "2021 vs today", ":material/history:", "#7b3fd1",
               "What the July 2021 water covered, what has been done since, and what still needs fixing."),
    "limits": ("views/limits.py", "Data & limits", ":material/info:", "#6e6e73",
               "Where every number comes from, and what it cannot tell you."),
}
# role key: (name, icon, colour, who it is for, its pages in sections; the first page opens on arrival)
ROLES = {
    "manager": ("Crisis manager", ":material/crisis_alert:", "#d70015",
                "Decide which towns leave, follow who is safe, send the briefings.",
                {"Respond": ["crisis", "plan", "doors"], "Background": ["assess", "limits"]}),
    "brigade": ("Fire brigade", ":material/fire_truck:", "#c93400",
                "Knock on the right doors first and take the open roads out.",
                {"On the ground": ["doors", "plan"]}),
    "resident": ("Resident", ":material/home:", "#0071e3",
                 "Do I need to leave, where do I go? Tell the crews you are safe.",
                 {"": ["resident"]}),
}
EU_YELLOW = "#ffcc00"  # the role tiles' accent bar
TOWN_PAGES = {"Town plan", "Door-knock list"}

if st.query_params.get("role") in ROLES and "role" not in st.session_state:
    st.session_state.role = st.query_params["role"]
role = st.session_state.get("role")
if role not in ROLES:  # an old link or session (the policy maker role is gone)
    role = st.session_state.role = None


def chip(c):
    """A rounded tinted square behind a material icon, in colour c."""
    return (f"background:color-mix(in srgb,{c} 13%,#fff);color:{c}!important;border-radius:8px;width:1.9rem;"
            f"height:1.9rem;display:inline-grid!important;place-items:center;font-size:1.15rem!important;flex:none")


# nav rows: a coloured icon chip each, the open page as a raised white row with a bar in its colour
st.html("<style>" + "".join(
    f".st-key-nav-{k} [data-testid=stIconMaterial]{{{chip(v[3])}}}"
    f".st-key-nav-{k} a[aria-current=page],.st-key-nav-{k} a.active{{box-shadow:inset 3px 0 0 {v[3]},0 1px 3px rgba(0,0,0,.08)}}"
    for k, v in PAGES.items()) + "".join(
    f".st-key-role-{k}{{border-top:3px solid {EU_YELLOW}!important}}"
    for k, v in ROLES.items()) + """
.rchip{display:grid;place-items:center;width:var(--s,3rem);height:var(--s,3rem);border-radius:calc(var(--s,3rem)*.27);flex:none;
  background:color-mix(in srgb,var(--c) 13%,#fff);color:var(--c)}
.rchip span{font-family:'Material Symbols Rounded';font-size:calc(var(--s,3rem)*.6);line-height:1;font-variation-settings:'FILL' 1}
.who{display:flex;align-items:center;gap:.55rem;font-weight:650;font-size:1rem;color:#1d1d1f}
[class*=st-key-nav-] [data-testid=stPageLink] a{gap:.65rem!important}
[class*=st-key-nav-] [data-testid=stPageLink] a{padding:.3rem .5rem;border-radius:10px;gap:.2rem;min-height:2.6rem}
[class*=st-key-nav-] [data-testid=stPageLink] a:hover{background:rgba(255,255,255,.8)}
[class*=st-key-nav-] [data-testid=stPageLink] a[aria-current=page]{background:#fff}
[class*=st-key-nav-] [data-testid=stPageLink] a[aria-current=page] p{font-weight:650}
[class*=st-key-nav-] [data-testid=stPageLink] p{font-size:.95rem}
.navh{font-size:.72rem;font-weight:650;color:#5a6e87;letter-spacing:.04em;text-transform:uppercase;margin:.6rem 0 -.2rem .55rem}
.st-key-scn{background:#fff;border-radius:14px;padding:.85rem .9rem .5rem;box-shadow:0 1px 2px rgba(0,0,0,.05),0 4px 14px rgba(0,0,0,.04)}
.clock{display:flex;align-items:center;gap:.6rem}
.clock .ld{width:.6rem;height:.6rem;border-radius:50%;background:var(--c);flex:none}
.clock.on .ld{animation:pulse 1.6s ease-out infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--c) 55%,transparent)}100%{box-shadow:0 0 0 .55rem transparent}}
@media (prefers-reduced-motion:reduce){.clock.on .ld{animation:none}}
.clock b{display:block;font-size:1.2rem;font-weight:700;letter-spacing:-.01em;color:#1d1d1f;font-variant-numeric:tabular-nums}
.clock small{display:block;font-size:.78rem;color:#4f6580}
.st-key-roles [data-testid=stVerticalBlockBorderWrapper],[class*=st-key-role-]{background:#fff}
</style>""")


def pick(k):
    st.session_state.role = k
    st.query_params["role"] = k


def launch():
    st.title("Flood desk")
    st.markdown(f"**The July 2021 flood, replayed as if it started {live.drill(live.START):%A %-d %B}.** Belgium, the "
                "Netherlands and Germany: one shared clock for the crisis room, the fire brigade and residents.",
                help="The river flows are those of 12-17 July 2021, modelled afterwards (GloFAS). Only the dates move. "
                     "Not an official warning: those come from SPW, Rijkswaterstaat and the German state flood centres.")
    st.space("small")
    cols = st.columns(len(ROLES), gap="medium")
    for col, (k, (name, ic, _c, who, _p)) in zip(cols, ROLES.items()):
        with col.container(border=True, key=f"role-{k}", height="stretch"):
            st.html(f"<div class='rchip' style='--c:{_c}'><span>{ic.split('/')[1].rstrip(':')}</span></div>")
            st.markdown(f"### {name}")
            st.markdown(who)
            st.button(f"Open as {name.lower()}", key=f"go-{k}", on_click=pick, args=(k,),
                      type="primary" if k == "manager" else "secondary", width="stretch")


# the replay's days, to jump to: its start, then each midnight (flows are daily, so status changes at midnight)
DAYS = [live.START] + list(pd.date_range(live.START.normalize() + pd.Timedelta(days=1), live.END, freq="D"))


def seek():
    live.seek(st.session_state.sc_time)
    st.session_state._seeked = True  # the fragment reruns the whole page, so the other views follow


def now(controls=True):
    """Where the shared clock stands, big; a slider to jump to any day of the replay. Moves the clock while
    playing, so every role sees the same moment."""
    k = live.advance()
    replay = k["mode"] == "replay"
    t = live.drill(k["t"]) if replay else k["t"]
    st.html(f"<div class='clock{' on' if k['playing'] else ''}' style='--c:{'#248a3d' if k['playing'] else '#8e8e93'}'>"
            f"<i class='ld'></i><div><b>{t:%a %-d %b · %H:%M}</b><small>"
            + ("Replay of July 2021" if replay else "Live forecast") + (" · playing" if k["playing"] else " · paused")
            + "</small></div></div>")
    if replay and controls:
        st.session_state.sc_time = max(d for d in DAYS if d <= k["t"])
        st.select_slider("Jump to day", DAYS, key="sc_time", on_change=seek, label_visibility="collapsed",
                         format_func=lambda d: f"{live.drill(d):%a %-d %b}" + (" 06:00" if d == live.START else ""),
                         help="Pick a day of the replay. Going back rebuilds that moment: alerts, briefings, "
                              "closed roads and simulated check-ins as they stood then.")
    if st.session_state.pop("_seeked", False):
        st.rerun()


def scenario(controls=True):
    """The scenario player: one clock shared by all sessions (src/live.py), so what the crisis manager plays, the
    fire brigade and the residents see too. Play and the day are in view; mode, speed and the outlook fold away."""
    c = live.clock()
    with st.container(key="scn"):
        st.fragment(now, run_every=1.5 if c["playing"] else 4)(controls)
        if not controls:
            return
        b1, b2 = st.columns(2)
        if c["playing"]:
            b1.button("Pause", icon=":material/pause:", on_click=live.pause, width="stretch")
        else:
            b1.button("Play", icon=":material/play_arrow:", on_click=live.play, type="primary", width="stretch")
        b2.button("Reset", icon=":material/replay:", on_click=live.reset, width="stretch",
                  help=f"Back to {live.drill(live.START):%a %d %b} 06:00 (the 12 July 2021 river flows); clears "
                       "alerts, reports, closures and simulated check-ins")
        with st.expander("Settings", icon=":material/tune:"):
            st.session_state.sc_mode = c["mode"]
            st.session_state.sc_speed = float(c["speed"]) if c["speed"] in (1, 3, 6, 12) else 3.0
            st.segmented_control("Mode", ["replay", "live"], key="sc_mode",
                                 format_func={"replay": "Replay 2021", "live": "Live forecast"}.get,
                                 on_change=lambda: st.session_state.sc_mode and live.set_mode(st.session_state.sc_mode),
                                 help="Replay the July 2021 river flows as if they started today, or follow today's "
                                      "real GloFAS outlook. The clock is shared: every role sees the same moment.")
            st.select_slider("Speed", [1.0, 3.0, 6.0, 12.0], key="sc_speed", format_func=lambda x: f"{x:g} h per second",
                             on_change=lambda: live.set_speed(st.session_state.sc_speed))
            fetched = core.outlook()[-2]
            if st.button("Refresh live outlook" + (f" · {fetched:%H:%M}" if fetched is not None else ""),
                         icon=":material/refresh:", type="tertiary",
                         help="Open-Meteo GloFAS, the real 30-day outlook for today (not the replay)."):
                core._outlook.clear()
                st.rerun()


if role is None:
    st.navigation([st.Page(launch, title="Flood desk", icon=":material/water:")], position="hidden").run()
    st.stop()

name, ric, rcol, _who, sections = ROLES[role]
keys = [k for ks in sections.values() for k in ks]
pages = {k: st.Page(PAGES[k][0], title=PAGES[k][1], icon=PAGES[k][2], default=(k == keys[0])) for k in keys}
nav = st.navigation(list(pages.values()), position="hidden")

with st.sidebar:
    a, b = st.columns([5, 1], vertical_alignment="center")
    a.html(f"<div class='who'><div class='rchip' style='--c:{rcol};--s:2.1rem'><span>{ric.split('/')[1].rstrip(':')}"
           f"</span></div>{name}</div>")
    b.button("", icon=":material/swap_horiz:", type="tertiary", help="Switch role",
             on_click=lambda: (st.session_state.pop("role", None), st.query_params.clear()))
    if len(keys) > 1:
        for sec, ks in sections.items():
            if sec:
                st.html(f"<div class='navh'>{sec}</div>")
            for k in ks:
                with st.container(key=f"nav-{k}"):
                    st.page_link(pages[k], label=PAGES[k][1], icon=PAGES[k][2], width="stretch")
    # one Town picker for every page that works on a town; _town keeps the choice while other pages are open
    if nav.title in TOWN_PAGES:
        tw = anna.load()[1]
        tw = tw[(tw.variant == "worst") & (tw.people >= 10)].sort_values("people", ascending=False)
        st.session_state.setdefault("_town", tw.municipality.iloc[0])
        st.session_state.town = st.session_state._town
        lab = dict(zip(tw.municipality, tw.label + " · " + tw.people.map(core.about) + " in the 2021 water"))
        st.space("small")
        st.selectbox("Town", list(lab), format_func=lab.get, key="town",
                     on_change=lambda: st.session_state.update(_town=st.session_state.town))
    st.space("small")
    scenario(controls=role != "resident")

nav.run()
