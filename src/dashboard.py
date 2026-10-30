"""Action dashboard for crisis managers, fire brigades and residents in the July 2021 flood areas, planning for a
10-, 100- or 500-year river flood (EFAS zones, outputs/rp; built by notebooks/pipeline.py with FLOOD=rp and
notebooks/rp_extras.py). The 2021 vs today page reads outputs/data. Run: streamlit run src/dashboard.py

On launch the visitor picks a role (crisis manager, fire brigade, resident); each role sees only its
pages. ?role=<key> in the URL skips the choice (demo links, test renders)."""
import pandas as pd
import streamlit as st

import anna
import core
import live

st.set_page_config(page_title="Flood desk", page_icon=":material/water:", layout="wide",
                   initial_sidebar_state="auto")

PAGES = core.PAGES
# role key: (name, icon, colour, who it is for, its pages in sections; the first page opens on arrival)
ROLES = {
    "manager": ("Crisis manager", ":material/crisis_alert:", "#d70015",
                "Pick the flood to plan for, decide which towns leave, follow who is safe, send the briefings.",
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
.st-key-scn{background:#fff;border-radius:14px;padding:.85rem .9rem .6rem;box-shadow:0 1px 2px rgba(0,0,0,.05),0 4px 14px rgba(0,0,0,.04)}
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
    st.markdown("**Plan for a 10-, 100- or 500-year river flood.** Belgium, the Netherlands and Germany, in the "
                "valleys hit in July 2021: who sits in the water, where they go, which doors to knock on. One shared "
                "scenario for the crisis room, the fire brigade and residents.",
                help="Flood zones: EFAS flood hazard maps (JRC), every river at that return period at once, no dikes "
                     "in the model. A planning map, not a forecast and not an official warning: those come from SPW, "
                     "Rijkswaterstaat and the German state flood centres.")
    st.space("small")
    cols = st.columns(len(ROLES), gap="medium")
    for col, (k, (name, ic, _c, who, _p)) in zip(cols, ROLES.items()):
        with col.container(border=True, key=f"role-{k}", height="stretch"):
            st.html(f"<div class='rchip' style='--c:{_c}'><span>{ic.split('/')[1].rstrip(':')}</span></div>")
            st.markdown(f"### {name}")
            st.markdown(who)
            st.button(f"Open as {name.lower()}", key=f"go-{k}", on_click=pick, args=(k,),
                      type="primary" if k == "manager" else "secondary", width="stretch")


RP_HELP = {10: "10 % chance in any year", 100: "1 % chance in any year", 500: "0.2 % chance in any year"}


def set_rps():
    live.set_rps(st.session_state.sc_rps or [])


def scenario(controls=True):
    """The shared scenario: which return periods are on. The crisis room switches them; every role sees the same.
    Several on = compare them; the response plans for the rarest one."""
    k = live.advance()
    p = k["plan"]
    with st.container(key="scn"):
        col = "#d70015" if p else "#248a3d"
        st.html(f"<div class='clock' style='--c:{col}'><i class='ld'></i><div><b>"
                + (f"{p}-year flood" if p else "Normal") + "</b><small>"
                + (f"Planning for a {p}-year river flood · {RP_HELP[p]}" if p else "No flood scenario switched on")
                + "</small></div></div>")
        if not controls:
            return
        st.session_state.sc_rps = k["rps"]
        st.segmented_control("Return period", list(live.RPS), selection_mode="multi", key="sc_rps",
                             format_func=lambda r: f"{r}-year", on_change=set_rps,
                             help="Switch on one flood to plan for it, or several to compare them: the map shows each "
                                  "zone, the plan follows the rarest one switched on. EFAS flood hazard maps, all "
                                  "rivers at that return period at once; no dikes in the model. Every role sees "
                                  "the same scenario.")
        if k["rps"]:
            st.button("Back to normal", icon=":material/restart_alt:", type="tertiary", width="stretch",
                      on_click=lambda: live.set_rps([]),
                      help="Switch every flood off: alerts, briefings and closed roads clear; check-ins stay.")


if role is None:  # the opening page: flood, town, then the homes in order; the role desk is one click down
    st.navigation([st.Page("views/start.py", title="Who leaves first", icon=":material/water:", default=True),
                   st.Page(launch, title="Flood desk", icon=":material/apps:", url_path="desk")],
                  position="hidden").run()
    st.stop()

name, ric, rcol, _who, sections = ROLES[role]
keys = [k for ks in sections.values() for k in ks]
pages = {k: st.Page(PAGES[k][0], title=PAGES[k][1], icon=PAGES[k][2], default=(k == keys[0])) for k in keys}
nav = st.navigation(list(pages.values()), position="hidden")
st.session_state._nav = keys  # core.next_steps offers only this role's pages
if st.session_state.get("_goto") in pages:  # sent here from a town on the opening page
    st.switch_page(pages[st.session_state.pop("_goto")])
st.session_state.pop("_goto", None)

with st.sidebar:
    a, b = st.columns([5, 1], vertical_alignment="center")
    a.html(f"<div class='who'><div class='rchip' style='--c:{rcol};--s:2.1rem'><span>{ric.split('/')[1].rstrip(':')}"
           f"</span></div>{name}</div>")
    b.button("", icon=":material/swap_horiz:", type="tertiary", help="Back to the start", on_click=core.restart)
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
        v = live.variant()
        tw = tw[(tw.variant == v) & (tw.people >= 10)].sort_values("people", ascending=False)
        if st.session_state.get("_town") not in set(tw.municipality):
            st.session_state._town = tw.municipality.iloc[0]
        st.session_state.town = st.session_state._town
        lab = dict(zip(tw.municipality, tw.label + " · " + tw.people.map(core.about) + f" in the {v[2:]}-year zone"))
        st.space("small")
        st.selectbox("Town", list(lab), format_func=lab.get, key="town",
                     on_change=lambda: st.session_state.update(_town=st.session_state.town))
    st.space("small")
    scenario(controls=role != "resident")

nav.run()
