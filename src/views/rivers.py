"""Crisis room, Rivers tab. Two parts, kept apart on purpose:
  1 the live 30-day GloFAS outlook at ten river points (real, today), with each point's curve
  2 when each river peaked in the July 2021 flows, on the drill dates (briefing's heatmap; a replay, not a forecast)."""
import altair as alt
import pandas as pd
import streamlit as st

import core
import forecast
import live

ORDER = ["Lesse · Rochefort", "Ourthe · Tabreux", "Vesdre · Verviers", "Vesdre · Chaudfontaine", "Meuse · Liège",
         "Meuse · Maastricht", "Meuse · Roermond", "Meuse · Venlo", "Inde · Eschweiler", "Rur · Wassenberg"]
DAY0 = pd.Timestamp("2021-07-12")  # the replay's first day: rivers still normal, the rain has not fallen yet


def levels():
    """River status per point and day of the 2021 replay: 0 normal · 1 above 2-year flood · 2 above half of July 2021
    · 3 at July 2021."""
    flow, ref = core.load_replay(), forecast.refs()
    return flow, ref, pd.DataFrame({g: [sum(q >= x for x in (ref[g][0], ref[g][1] / 2, ref[g][1])) for q in flow[g]]
                                    for g in flow}, index=flow.index)


def outlook():
    gauges, series, rain, fetched, err = core.outlook()
    color, head, detail, _ = core.status(gauges, rain, err)
    st.subheader(":blue[:material/sensors:] Live outlook, next 30 days",
                 help="Open-Meteo GloFAS ensemble, fetched " + (f"{fetched:%a %d %b %H:%M}" if fetched is not None
                                                                else "never") +
                      ". Ten river points, each rated against the same model's July 2021 peak. Refresh it from the "
                      "sidebar.")
    st.caption("Real and current: today's forecast, not the replay. A heads-up from a model, not an official warning.")
    core.banner(color, head, detail, note=False)
    if gauges is None:
        return
    st.space("small")
    tab = gauges.sort_values(["level", "pct_2021"], ascending=False).reset_index(drop=True)
    tab = tab.assign(status=[forecast.LEVELS[l][0] for l in tab.level], pct=tab.pct_2021 * 100)
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("**Forecast points**", help="Select a row to see its curve.")
        pick = st.dataframe(core.paint(tab[["gauge", "status", "peak", "peak_day", "pct"]], "status",
                                       dict(forecast.LEVELS)),
                            hide_index=True, on_select="rerun", selection_mode="single-row", key="gauge",
                            column_config={
                                "gauge": "River · place", "status": st.column_config.TextColumn("Expected", width="small"),
                                "peak": st.column_config.NumberColumn("Peak m³/s", format="%.0f"),
                                "peak_day": st.column_config.DateColumn("Peak day", format="ddd D MMM"),
                                "pct": st.column_config.ProgressColumn("% of 2021", format="%.0f%%", min_value=0,
                                                                       max_value=100)})
    rows = pick.selection.rows
    g = tab.iloc[rows[0] if rows else 0]
    d = series[series.gauge == g.gauge]
    with right:
        st.markdown(f"**{g.gauge}**", help="Line: ensemble median. Band: up to the wettest run. Dashed: reference "
                                           "flows from the same model. Grey rule: today.")
        # each reference line in the colour of the status it starts, so the curve reads against the table and the map
        refs = pd.DataFrame({"q": [g.q2, g.q2021 / 2, g.q2021],
                             "lab": ["2-year flood", "half of July 2021", "July 2021 peak"],
                             "c": [c for _, c in forecast.LEVELS[1:]],
                             "txt": ["#4566d1", *[c for _, c in forecast.LEVELS[2:]]]})
        base = alt.Chart(d).encode(x=alt.X("time:T", title=None))
        st.altair_chart(alt.layer(
            base.mark_area(color="#1d1d1f", opacity=.08).encode(y="river_discharge_median:Q", y2="river_discharge_max:Q"),
            base.mark_line(color="#1d1d1f", strokeWidth=2).encode(y=alt.Y("river_discharge_median:Q", title="m³/s")),
            alt.Chart(refs).mark_rule(strokeDash=[4, 3], strokeWidth=1.5).encode(y="q:Q", color=alt.Color("c:N", scale=None)),
            alt.Chart(refs).mark_text(align="left", dx=4, dy=-6, fontSize=11, fontWeight=600).encode(
                y="q:Q", text="lab:N", x=alt.value(0), color=alt.Color("txt:N", scale=None)),  # 2-year label at 4.5:1
            alt.Chart(pd.DataFrame({"t": [pd.Timestamp.today().normalize()]})).mark_rule(color="#8e8e93").encode(x="t:T"),
        ).properties(height=300, background="#ffffff").configure_view(stroke=None)
         .configure_axis(gridColor="#ececf0", domain=False, labelColor="#6e6e73", titleColor="#6e6e73"), width="stretch")
        core.group([("Now", f"{core.fmt(g.now)} m³/s"),
                    ("Wettest forecast run", core.chip(forecast.LEVELS[g.level_worst][0],
                                                       forecast.LEVELS[g.level_worst][1]))])
    st.caption("GloFAS (~5 km) resolves the Meuse well but small, steep valleys poorly: a “normal” Vesdre reading is "
               "not reassurance.")
    with st.expander("Rain in the headwaters, next 7 days", icon=":material/rainy:"):
        st.dataframe(rain[["area", "max_2day", "week", "july_2021"]], hide_index=True, column_config={
            "area": "Headwater", "max_2day": st.column_config.NumberColumn("Max in 2 days, mm", format="%.0f"),
            "week": st.column_config.NumberColumn("Next 7 days, mm", format="%.0f"),
            "july_2021": st.column_config.NumberColumn("13–15 July 2021, mm", format="%.0f",
                                                       help="ERA5 reanalysis; it smooths local peaks, rain gauges "
                                                            "measured more.")})


def peaks():
    """The 2021 river peaks on the drill dates; the black frame follows the drill clock (briefing's step control,
    folded into the scenario player)."""
    flow, ref, lvl = levels()
    c = live.clock()
    day = min(max(c["t"].normalize(), DAY0), DAY0 + pd.Timedelta(days=5)) if c["mode"] == "replay" else None
    heat = pd.DataFrame([(t, g, flow.loc[t, g] / ref[g][1], *forecast.LEVELS[lvl.loc[t, g]]) for t in flow.index
                         for g in ORDER], columns=["day", "gauge", "pct", "status", "fill"])
    heat["ink"] = heat.fill.map(core.ink)
    heat = heat[(heat.day >= DAY0) & (heat.day <= DAY0 + pd.Timedelta(days=5))]
    heat["d"] = heat.day.map(live.drill).dt.strftime("%a %d")  # plain labels: a year-less time unit prints 2012 weekdays
    x = alt.X("d:O", sort=list(heat.d.unique()), title=None, axis=alt.Axis(labelAngle=0, orient="top"))
    y = alt.Y("gauge:N", sort=ORDER, title=None, axis=alt.Axis(labelLimit=220))
    base = alt.Chart(heat).encode(x=x, y=y)
    layers = [
        base.mark_rect(stroke="#fff", strokeWidth=2, cornerRadius=4).encode(
            color=alt.Color("status:N", scale=alt.Scale(domain=[l for l, _ in forecast.LEVELS],
                                                        range=[c for _, c in forecast.LEVELS]), legend=None),
            tooltip=[alt.Tooltip("gauge:N", title="River"),
                     alt.Tooltip("day:T", format="%d %b %Y", title="July 2021 flow of"),
                     alt.Tooltip("status:N"), alt.Tooltip("pct:Q", format=".0%", title="Of July 2021 peak")]),
        base.mark_text(fontSize=11).encode(text=alt.Text("pct:Q", format=".0%"), color=alt.Color("ink:N", scale=None))]
    if day is not None:
        layers.append(alt.Chart(pd.DataFrame({"d": [f"{live.drill(day):%a %d}"]})).mark_rect(
            fill=None, stroke="#1d1d1f", strokeWidth=2).encode(x=alt.X("d:O", sort=list(heat.d.unique()))))
    st.altair_chart(alt.layer(*layers).properties(
        height=330, background="#ffffff", padding={"left": 12, "right": 12, "top": 8, "bottom": 8})
                    .configure_view(stroke=None)
                    .configure_axis(domain=False, ticks=False, labelColor="#1d1d1f", labelFontSize=12), width="stretch")
    core.legend("".join(core.swatch(c, lab) for lab, c in forecast.LEVELS)
                + ("<span><i style='border:2px solid #1d1d1f;background:none'></i>replay clock</span>" if day is not None
                   else ""))


def render():
    outlook()
    st.divider()
    flow = core.load_replay()
    lag = (flow["Meuse · Venlo"].idxmax() - flow["Vesdre · Chaudfontaine"].idxmax()).days
    st.subheader(":orange[:material/timeline:] When each river peaks in the replay",
                 help="Daily river flow from the GloFAS model for 12–17 July 2021, as % of each point's own July 2021 "
                      "peak, on the replay dates. Top to bottom follows the water: the Ardennes tributaries peak first. "
                      "Covers the Meuse basin only, not the Ahr or Erft.")
    st.caption(f"Replay of the 2021 forecast: the July 2021 flows, dated from {live.drill(DAY0):%a %-d %b}. Dutch Limburg "
               f"peaks about {lag} day{'s' if lag != 1 else ''} after the Vesdre: that gap is the downstream lead time.")
    st.fragment(peaks, run_every=6 if live.clock()["playing"] else None)()

    st.space("small")
    with st.expander("Who issues the real warnings", icon=":material/campaign:"):
        core.group([
            ("<b>Emergency services</b>", "BE · NL · DE", "112"),
            ("<b>Belgium · Wallonia</b>", "SPW river levels and flood warnings, hydrometrie.wallonie.be · FR, DE",
             "Official"),
            ("<b>Netherlands</b>", "Rijkswaterstaat water levels, waterinfo.rws.nl · NL", "Official"),
            ("<b>Germany · North Rhine-Westphalia</b>", "State flood portal, hochwasserportal.nrw · DE", "Official"),
            ("<b>Germany · Rhineland-Palatinate (Ahr)</b>", "State flood warning service, hochwasser.rlp.de · DE",
             "Official"),
            ("<b>Your own focal points</b>", "Add each agency's contact person, phone and radio channel before an event",
             "To fill"),
        ], foot="A training and planning tool. Check the official warning for your river before acting.")
    with st.expander("How this is computed", icon=":material/info:"):
        st.markdown(
            "- **Live outlook:** Open-Meteo GloFAS 30-day ensemble at ten points of the Meuse basin. Status: the "
            "ensemble median against the same model's 2-year flood, half the July 2021 peak and the July 2021 peak. "
            "The wettest run is shown beside it.\n"
            "- **Replay peaks:** GloFAS reanalysis, daily, computed after the event. Each cell is that day's flow as a "
            "share of the point's own July 2021 peak. The black frame is the day the replay clock stands on.\n"
            f"- **Source:** {core.AS_OF['replay']}.")
