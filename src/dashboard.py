"""Action dashboard for crisis and risk managers in the July 2021 flood areas. Reads the cleaned data in
outputs/data; the river outlook needs forecast.py (once) and build_priority.py (replay). The First action page reads
notebooks/pipeline.py, dq_report.py and q4_ranking.py outputs. Run: streamlit run src/dashboard.py

On launch the visitor picks a role (resident, crisis manager, fire brigade, policy maker); each role sees only its
pages. ?role=<key> in the URL skips the choice (demo links, test renders)."""
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
HEX = {"red": "#d70015", "orange": "#c93400", "blue": "#0071e3", "violet": "#7b3fd1", "gray": "#6e6e73"}
TOWN_PAGES = {"Town plan", "Door-knock list"}

if st.query_params.get("role") in ROLES and "role" not in st.session_state:
    st.session_state.role = st.query_params["role"]
role = st.session_state.get("role")

# coloured icons: each nav row and role tile is a keyed container, styled by its key
st.html("<style>" + "".join(
    f".st-key-nav-{k} [data-testid=stIconMaterial]{{color:{HEX[c]}}}" for k, (*_, c, _h) in PAGES.items()) + "".join(
    f".st-key-role-{k}{{border-top:3px solid {HEX[c]}!important}}" for k, (_, _, c, *_r) in ROLES.items()) + """
[class*=st-key-nav-] [data-testid=stPageLink] a{padding:.3rem .55rem;border-radius:8px;position:relative}
/* the page's explanation is a tooltip on the row; a ? appears on hover to say so */
[class*=st-key-nav-] [data-testid=stPageLink] a::after{content:"?";position:absolute;right:.55rem;top:50%;
  transform:translateY(-50%);width:1.05rem;height:1.05rem;border-radius:50%;border:1.5px solid #8e8e93;color:#6e6e73;
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
    st.markdown(f"**Drill: {live.drill(live.START):%A %-d %B %Y}.** The July 2021 flood in Belgium, the Netherlands "
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

nav.run()

# footer last, so each page's own sidebar controls sit right under the navigation
if role != "resident":
    with st.sidebar:
        st.divider()
        gauges, *_, fetched, err = core.outlook()
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.caption("Live river outlook" + (f" · {fetched:%H:%M}" if fetched is not None else " · unavailable"),
                   help="Open-Meteo GloFAS, the real 30-day outlook for today (not the drill).")
        if c2.button("", icon=":material/refresh:", type="tertiary", help="Refresh the live outlook"):
            core._outlook.clear()
            st.rerun()
