"""Action dashboard for crisis and risk managers in the July 2021 flood areas. Reads the cleaned data in
outputs/data; the river outlook needs forecast.py (once) and build_priority.py (replay). The First action page reads
notebooks/pipeline.py, dq_report.py and q4_ranking.py outputs. Run: streamlit run src/dashboard.py"""
import streamlit as st

import core

st.set_page_config(page_title="Flood desk", page_icon=":material/water:", layout="wide",
                   initial_sidebar_state="auto")
core.style()

nav = st.navigation({
    "": [st.Page("views/evacuate.py", title="Evacuation plan", icon=":material/directions_run:", default=True),
         st.Page("views/long_term.py", title="Long term", icon=":material/construction:"),
         st.Page("views/host.py", title="Offer a bed", icon=":material/volunteer_activism:")],
    "More": [st.Page("views/first_action.py", title="All towns and care sites", icon=":material/flag:"),
                     st.Page("views/briefing.py", title="Briefing", icon=":material/space_dashboard:"),
                     st.Page("views/rivers.py", title="Rivers", icon=":material/water:"),
                     st.Page("views/risk_areas.py", title="Risk areas", icon=":material/map:"),
                     st.Page("views/shelters.py", title="Shelters", icon=":material/home_health:")],
    "Reference": [st.Page("views/then_now.py", title="2021 and today", icon=":material/history:"),
                  st.Page("views/limits.py", title="Data & limits", icon=":material/info:")],
})

with st.sidebar:
    gauges, *_, fetched, err = core.outlook()
    st.caption("July 2021 flood areas · BE · NL · DE")
    if fetched is not None:
        st.caption(f"Outlook from {fetched:%H:%M}, Open-Meteo GloFAS")
    if st.button("Refresh outlook", icon=":material/refresh:", type="tertiary"):
        core._outlook.clear()
        st.rerun()

nav.run()
