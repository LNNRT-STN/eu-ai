"""Crisis room, Rivers tab. Two parts, kept apart on purpose:
  1 the live GloFAS ensemble outlook at the river points (real, today), rated on return periods, with each curve
  2 the backtest: the July 2021 flows on the drill dates, rated on thresholds fitted before 2021 (a replay)."""
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
    """Per point and day of the 2021 replay, on thresholds fitted on the record up to forecast.BACKTEST_YEAR (what
    was known before the flood): (flow, return period, level 0 normal · 1 above 2-year · 2 above 5-year · 3 above
    20-year flood)."""
    flow, thr = core.load_replay(), forecast.thresholds(forecast.BACKTEST_YEAR)
    flow = flow[[g for g in flow if g in thr]]
    return (flow, pd.DataFrame({g: forecast.period_of(thr[g]["fit"], flow[g].values) for g in flow}, index=flow.index),
            pd.DataFrame({g: forecast.level(flow[g].values, thr[g]) for g in flow}, index=flow.index))


def short(T):
    """A return period in a heatmap cell."""
    return "<2y" if T < 2 else ">100y" if T > 100 else f"{T:.0f}y"


def outlook():
    gauges, series, rain, fetched, err = core.outlook()
    color, head, detail, _ = core.status(gauges, rain, err)
    st.subheader(f":blue[:material/sensors:] Live outlook, next {forecast.HORIZON} days",
                 help="Open-Meteo GloFAS ensemble (51 runs), fetched " + (f"{fetched:%a %d %b %H:%M}" if fetched
                                                                          is not None else "never") +
                      ". Each river point is rated against its own 2-, 5-, 20- and 100-year floods from the same "
                      f"model's record. A level counts when {forecast.PROB:.0%} of the runs reach it. Refresh it "
                      "from the sidebar.")
    st.caption("Real and current: today's forecast, not the replay. A heads-up from a model, not an official warning.")
    core.banner(color, head, detail, note=False)
    if gauges is None:
        return
    st.space("small")
    tab = gauges.sort_values(["level", "chance", "rp_peak"], ascending=False).reset_index(drop=True)
    tab = tab.assign(status=[forecast.LEVELS[l][0] for l in tab.level], pct=tab.chance * 100,
                     rp=tab.rp_peak.map(forecast.rp_text))
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("**Forecast points**", help="Select a row to see its curve.")
        pick = st.dataframe(core.paint(tab[["gauge", "status", "pct", "rp", "peak_day"]], "status",
                                       dict(forecast.LEVELS)),
                            hide_index=True, on_select="rerun", selection_mode="single-row", key="gauge",
                            column_config={
                                "gauge": "River · place", "status": st.column_config.TextColumn("Expected", width="small"),
                                "pct": st.column_config.ProgressColumn(
                                    "Chance", format="%.0f%%", min_value=0, max_value=100,
                                    help="Share of the 51 forecast runs that reach this level (at normal: the "
                                         "2-year flood) within the next days."),
                                "rp": st.column_config.TextColumn("Median peak", help="How rare the median run's "
                                                                  "peak is at this point"),
                                "peak_day": st.column_config.DateColumn("Most likely", format="ddd D MMM")})
    rows = pick.selection.rows
    g = tab.iloc[rows[0] if rows else 0]
    d = series[series.gauge == g.gauge]
    with right:
        st.markdown(f"**{g.gauge}**", help="Line: ensemble median. Dark band: middle half of the runs. Light band: up "
                                           "to the wettest run. Dashed: return-period floods from the same model's "
                                           f"record ({g.years}); grey: its July 2021 peak, for scale. Grey rule: today.")
        # each threshold in the colour of the status it starts, so the curve reads against the table and the map
        refs = pd.DataFrame({"q": [g.q2, g.q5, g.q20, g.q100, g.q2021],
                             "lab": ["2-year flood", "5-year", "20-year", "100-year", "July 2021"],
                             "c": [*[c for _, c in forecast.LEVELS[1:]], "#1d1d1f", "#8e8e93"],
                             "txt": ["#4566d1", *[c for _, c in forecast.LEVELS[2:]], "#1d1d1f", "#6e6e73"]})
        base = alt.Chart(d).encode(x=alt.X("time:T", title=None))
        st.altair_chart(alt.layer(
            base.mark_area(color="#1d1d1f", opacity=.06).encode(y="river_discharge_median:Q", y2="river_discharge_max:Q"),
            base.mark_area(color="#1d1d1f", opacity=.12).encode(y="river_discharge_p25:Q", y2="river_discharge_p75:Q"),
            base.mark_line(color="#1d1d1f", strokeWidth=2).encode(y=alt.Y("river_discharge_median:Q", title="m³/s")),
            alt.Chart(refs).mark_rule(strokeDash=[4, 3], strokeWidth=1.5).encode(y="q:Q", color=alt.Color("c:N", scale=None)),
            alt.Chart(refs).mark_text(align="left", dx=4, dy=-6, fontSize=11, fontWeight=600).encode(
                y="q:Q", text="lab:N", x=alt.value(0), color=alt.Color("txt:N", scale=None)),  # 2-year label at 4.5:1
            alt.Chart(pd.DataFrame({"t": [pd.Timestamp.today().normalize()]})).mark_rule(color="#8e8e93").encode(x="t:T"),
        ).properties(height=300, background="#ffffff").configure_view(stroke=None)
         .configure_axis(gridColor="#ececf0", domain=False, labelColor="#4f6580", titleColor="#4f6580"), width="stretch")
        core.group([("Now", f"{core.fmt(g.now)} m³/s"),
                    ("Chance of a 5-year flood", f"{g.p5:.0%} of runs"),
                    ("Chance of a 20-year flood", f"{g.p20:.0%} of runs"),
                    ("Wettest forecast run", core.chip(forecast.LEVELS[g.level_worst][0],
                                                       forecast.LEVELS[g.level_worst][1]))])
    st.caption("GloFAS (~5 km) resolves the Meuse well but small, steep valleys poorly. Rating each point on its own "
               "record corrects a model that runs low there, not one that misses a storm: a “normal” Vesdre reading is "
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
    flow, rp, lvl = levels()
    c = live.clock()
    day = min(max(c["t"].normalize(), DAY0), DAY0 + pd.Timedelta(days=5)) if c["mode"] == "replay" else None
    heat = pd.DataFrame([(t, g, short(rp.loc[t, g]), forecast.rp_text(rp.loc[t, g]), *forecast.LEVELS[lvl.loc[t, g]])
                         for t in flow.index for g in ORDER], columns=["day", "gauge", "rp", "rp_long", "status", "fill"])
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
                     alt.Tooltip("status:N"), alt.Tooltip("rp_long:N", title="Return period, record to 2020")]),
        base.mark_text(fontSize=11).encode(text="rp:N", color=alt.Color("ink:N", scale=None))]
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
    st.subheader(":orange[:material/timeline:] Backtest: the 2021 flows on the same rule",
                 help="Daily river flow from the GloFAS model for 12–17 July 2021, as the return period it had on "
                      f"the record up to {forecast.BACKTEST_YEAR} (what was known before the flood), on the replay "
                      "dates. Top to bottom follows the water: the Ardennes tributaries peak first. Covers the Meuse "
                      "basin only, not the Ahr or Erft.")
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
            "- **Return periods:** a Gumbel fit (L-moments) to each point's annual peak flows in the GloFAS v4 "
            "reanalysis, 1997–2025, as EFAS and GloFAS set their own thresholds. Rating a point against its own "
            "model record cancels the model's bias at that spot. With 29 years, anything beyond the 100-year flood "
            "is shown as “above 100-year”: the record cannot tell 200 from 2,000 years.\n"
            f"- **Live outlook:** Open-Meteo GloFAS ensemble (control + 50 runs). Each run's peak over the next "
            f"{forecast.HORIZON} days is rated: above the 2-year flood → watch, 5-year → warn, 20-year → evacuate. A "
            f"level counts when at least {forecast.PROB:.0%} of the runs reach it (the EFAS notification rule). "
            "The wettest run is shown beside it.\n"
            "- **Backtest:** GloFAS reanalysis, daily, computed after the event, rated on thresholds fitted on "
            f"1997–{forecast.BACKTEST_YEAR} only. It tests the rule, not the forecasts available on the day. The "
            "black frame is the day the replay clock stands on.\n"
            f"- **Source:** {core.AS_OF['replay']}.")
