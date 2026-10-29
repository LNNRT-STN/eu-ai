import altair as alt
import pandas as pd
import streamlit as st

import core
import forecast

gauges, series, rain, fetched, err = core.outlook()
color, head, detail, w = core.status(gauges, rain, err)

core.header("Rivers", "30-day GloFAS outlook at ten points, each rated against the same model's July 2021 peak.")
core.banner(color, head, detail)
if gauges is None:
    st.stop()
st.space("small")

tab = gauges.sort_values(["level", "pct_2021"], ascending=False).reset_index(drop=True)
tab = tab.assign(status=[forecast.LEVELS[l][0] for l in tab.level], pct=tab.pct_2021 * 100,
                 worst_status=[forecast.LEVELS[l][0] for l in tab.level_worst])
left, right = st.columns([1, 1], gap="large")
with left:
    st.html("<div class='gh'>Forecast points · select one for its curve</div>")
    pick = st.dataframe(tab[["gauge", "status", "peak", "peak_day", "pct"]], hide_index=True, on_select="rerun",
                        selection_mode="single-row", key="gauge", height=400, column_config={
                            "gauge": "River · place", "status": st.column_config.TextColumn("Expected", width="small"),
                            "peak": st.column_config.NumberColumn("Peak m³/s", format="%.0f"),
                            "peak_day": st.column_config.DateColumn("Peak day", format="ddd D MMM"),
                            "pct": st.column_config.ProgressColumn("Of July 2021", format="%.0f%%", min_value=0, max_value=100)})
rows = pick.selection.rows
g = tab.iloc[rows[0] if rows else 0]
d = series[series.gauge == g.gauge]
with right:
    st.html(f"<div class='gh'>{g.gauge}</div>")
    refs = pd.DataFrame({"q": [g.q2, g.q2021 / 2, g.q2021], "lab": ["2-year flood", "half of July 2021", "July 2021 peak"]})
    base = alt.Chart(d).encode(x=alt.X("time:T", title=None))
    st.altair_chart(alt.layer(
        base.mark_area(color="#0071e3", opacity=.15).encode(y="river_discharge_median:Q", y2="river_discharge_max:Q"),
        base.mark_line(color="#0071e3", strokeWidth=2).encode(y=alt.Y("river_discharge_median:Q", title="m³/s")),
        alt.Chart(refs).mark_rule(strokeDash=[4, 3], color="#c4501f").encode(y="q:Q"),
        alt.Chart(refs).mark_text(align="left", dx=4, dy=-6, color="#c4501f", fontSize=11).encode(
            y="q:Q", text="lab:N", x=alt.value(0)),
        alt.Chart(pd.DataFrame({"t": [pd.Timestamp.today().normalize()]})).mark_rule(color="#8e8e93").encode(x="t:T"),
    ).properties(height=330, background="#ffffff").configure_view(stroke=None)
     .configure_axis(gridColor="#ececf0", domain=False, labelColor="#6e6e73", titleColor="#6e6e73"), width="stretch")
    core.group([("Now", f"{core.fmt(g.now)} m³/s"), ("Wettest forecast run", g.worst_status)],
               foot="Line: ensemble median. Band: up to the wettest run. Dashed: reference flows from the same model.")

st.space("small")
with st.expander("Rain in the headwaters, next 7 days"):
    st.dataframe(rain[["area", "max_2day", "week", "july_2021"]], hide_index=True, column_config={
        "area": "Headwater", "max_2day": st.column_config.NumberColumn("Max in 2 days, mm", format="%.0f"),
        "week": st.column_config.NumberColumn("Next 7 days, mm", format="%.0f"),
        "july_2021": st.column_config.NumberColumn("13–15 July 2021, mm", format="%.0f",
                                                   help="ERA5 reanalysis; it smooths local peaks, rain gauges measured more.")})
st.caption("GloFAS (~5 km) resolves the Meuse well but small, steep valleys poorly: a “normal” Vesdre reading is not reassurance.")
