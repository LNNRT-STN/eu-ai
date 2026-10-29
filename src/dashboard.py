"""Action dashboard for cross-border crisis and risk managers (Meuse and Rhine side: Ahr, Eifel, Erft).
Run build.py, build_meuse.py, build_regions.py, build_sites.py (and forecast.py once) for the Meuse pages, and
notebooks/pipeline.py, dq_report.py, q4_ranking.py for the First action page, then: streamlit run src/dashboard.py"""
import streamlit as st

import core

st.set_page_config(page_title="Flood desk", page_icon=":material/water:", layout="wide",
                   initial_sidebar_state="auto")
core.style()

nav = st.navigation({
    "": [st.Page("views/first_action.py", title="First action", icon=":material/flag:", default=True)],
    "For analysts": [st.Page("views/briefing.py", title="Meuse replay", icon=":material/space_dashboard:"),
            st.Page("views/rivers.py", title="Rivers", icon=":material/water:"),
            st.Page("views/risk_areas.py", title="Risk areas", icon=":material/map:"),
            st.Page("views/shelters.py", title="Shelters", icon=":material/home_health:")],
    "Reference": [st.Page("views/limits.py", title="Data & limits", icon=":material/info:")],
})

with st.sidebar:
    gauges, *_, fetched, err = core.outlook()
    st.caption("Meuse, Ahr, Eifel, Erft · BE · NL · DE")
    if fetched is not None:
        st.caption(f"Outlook from {fetched:%H:%M}, Open-Meteo GloFAS")
    if st.button("Refresh outlook", icon=":material/refresh:", type="tertiary"):
        core._outlook.clear()
        st.rerun()

nav.run()
