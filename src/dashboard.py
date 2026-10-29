"""Action dashboard for crisis and risk managers in the July 2021 flood areas. Reads the cleaned data in
outputs/data; the river outlook needs forecast.py (once) and build_priority.py (replay). The First action page reads
notebooks/pipeline.py, dq_report.py and q4_ranking.py outputs. Run: streamlit run src/dashboard.py"""
import streamlit as st

import anna
import core

st.set_page_config(page_title="Flood desk", page_icon=":material/water:", layout="wide",
                   initial_sidebar_state="auto")

nav = st.navigation({
    "Crisis room": [st.Page("views/crisis.py", title="Crisis room", icon=":material/crisis_alert:", default=True),
                    st.Page("views/evacuate.py", title="Town plan", icon=":material/directions_run:"),
                    st.Page("views/view3d.py", title="3D view", icon=":material/landscape:"),
                    st.Page("views/long_term.py", title="Long term", icon=":material/construction:")],
    "Residents": [st.Page("views/resident.py", title="Do I need to leave?", icon=":material/home_pin:"),
                  st.Page("views/host.py", title="Offer a bed", icon=":material/volunteer_activism:")],
    "Responders": [st.Page("views/checkin.py", title="Check-ins and door-knock list", icon=":material/how_to_reg:")],
    "More": [st.Page("views/first_action.py", title="All towns and care sites", icon=":material/flag:"),
                     st.Page("views/briefing.py", title="Briefing", icon=":material/space_dashboard:"),
                     st.Page("views/rivers.py", title="Rivers", icon=":material/water:"),
                     st.Page("views/risk_areas.py", title="Risk areas", icon=":material/map:"),
                     st.Page("views/shelters.py", title="Shelters", icon=":material/home_health:")],
    "Reference": [st.Page("views/then_now.py", title="2021 and today", icon=":material/history:"),
                  st.Page("views/limits.py", title="Data & limits", icon=":material/info:")],
}, expanded=True)

# one Town picker for every page that works on a town; _town keeps the choice while other pages are open
TOWN_PAGES = {"Town plan", "Check-ins and door-knock list", "3D view"}
with st.sidebar:
    if nav.title in TOWN_PAGES:
        tw = anna.load()[1]
        tw = tw[(tw.variant == "worst") & (tw.people >= 10)].sort_values("people", ascending=False)
        st.session_state.setdefault("_town", tw.municipality.iloc[0])
        st.session_state.town = st.session_state._town
        lab = dict(zip(tw.municipality, tw.label + " · " + tw.people.map(core.about) + " in the 2021 water"))
        st.selectbox("Town", list(lab), format_func=lab.get, key="town",
                     on_change=lambda: st.session_state.update(_town=st.session_state.town))

nav.run()

# footer last, so each page's own sidebar controls sit right under the Town picker
with st.sidebar:
    st.divider()
    gauges, *_, fetched, err = core.outlook()
    st.caption("July 2021 flood areas · BE · NL · DE")
    if fetched is not None:
        st.caption(f"Outlook from {fetched:%H:%M}, Open-Meteo GloFAS")
    if st.button("Refresh outlook", icon=":material/refresh:", type="tertiary"):
        core._outlook.clear()
        st.rerun()
