"""Live outlook from Open-Meteo (free, no key): GloFAS river discharge and rain forecasts, each compared with
the same model's own July 2021 values at the same spot, so the comparison is like for like."""
import json, time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

FLOOD = "https://flood-api.open-meteo.com/v1/flood"
RAIN = "https://api.open-meteo.com/v1/forecast"
RAIN_2021 = "https://archive-api.open-meteo.com/v1/archive"
REFS = Path(__file__).resolve().parent / "out" / "meuse" / "gauge_refs.json"  # thresholds don't change: fetch once
# GloFAS 0.05° cells on each river, picked as the highest-flow cell near the town (scan in a 3×3 neighbourhood)
GAUGES = {"Meuse · Liège": (50.675, 5.625), "Meuse · Maastricht": (50.925, 5.675), "Meuse · Roermond": (51.225, 5.925),
          "Meuse · Venlo": (51.425, 6.125), "Vesdre · Chaudfontaine": (50.575, 5.625), "Vesdre · Verviers": (50.575, 5.825),
          "Ourthe · Tabreux": (50.475, 5.525), "Lesse · Rochefort": (50.175, 5.175), "Rur · Wassenberg": (51.025, 6.175),
          "Inde · Eschweiler": (50.875, 6.325)}
# headwaters where the July 2021 rain fell
RAIN_AREAS = {"Upper Vesdre (Eupen)": (50.55, 6.05), "Upper Ourthe": (50.25, 5.65), "Eifel / upper Rur": (50.55, 6.35),
              "Amblève (Stavelot)": (50.40, 5.93)}
LEVELS = [("Normal", "#8db8ec"), ("Above 2-year flood", "#f5a47d"), ("Above half of July 2021", "#eb6834"),
          ("At or above July 2021", "#7a2c10")]


def _get(url, pts, **params):
    lat, lon = zip(*pts.values())
    r = requests.get(url, params={"latitude": ",".join(map(str, lat)), "longitude": ",".join(map(str, lon)), **params},
                     timeout=30)
    if r.status_code == 429:
        raise RuntimeError("Open-Meteo free-tier limit reached, try again in a minute")
    r.raise_for_status()
    j = r.json()
    return dict(zip(pts, j if isinstance(j, list) else [j]))  # one location → object, several → list


def refs():
    """Reference flows per gauge from the model's own history: 2-year flood (median annual peak 2011–2020) and the
    July 2021 peak. Free tier weighs requests by time span, so this runs once (python src/forecast.py) to a file."""
    if not REFS.exists():
        raise RuntimeError("reference flows missing, run python src/forecast.py once")
    return json.loads(REFS.read_text())


def build_refs():
    out = {}
    for g in GAUGES:
        h = _get(FLOOD, {g: GAUGES[g]}, daily="river_discharge", start_date="2011-01-01", end_date="2021-12-31")[g]
        h = pd.Series(h["daily"]["river_discharge"], index=pd.to_datetime(h["daily"]["time"]))
        out[g] = [h[:"2020"].groupby(h[:"2020"].index.year).max().median(), h["2021-07-10":"2021-07-25"].max()]
        print(g, [round(q) for q in out[g]])
        time.sleep(20)  # stay under the per-minute weight limit
    REFS.write_text(json.dumps(out, indent=1))


def rivers():
    """Per gauge: forecast frame (median + ensemble max) rated against refs()."""
    ref = refs()
    fc = _get(FLOOD, GAUGES, daily="river_discharge,river_discharge_median,river_discharge_max",
              past_days=7, forecast_days=30)
    rows, series = [], []
    for g, (lat, lon) in GAUGES.items():
        q2, q21 = ref[g]
        d = pd.DataFrame(fc[g]["daily"]).assign(gauge=g, time=lambda x: pd.to_datetime(x.time))
        ahead = d[d.time.dt.date >= date.today()]
        peak, worst = ahead.river_discharge_median.max(), ahead.river_discharge_max.max()
        when = ahead.time[ahead.river_discharge_median.idxmax()]
        lvl = lambda q: sum(q >= x for x in (q2, q21 / 2, q21))
        rows.append({"gauge": g, "lat": lat, "lon": lon, "now": d.river_discharge[d.time.dt.date == date.today()].iloc[0],
                     "peak": peak, "peak_day": when, "worst": worst, "q2": q2, "q2021": q21,
                     "pct_2021": peak / q21, "level": lvl(peak), "level_worst": lvl(worst)})
        series.append(d)
    return pd.DataFrame(rows), pd.concat(series)


def rain():
    """7-day rain forecast per headwater area, with its largest 2-day total, next to the July 13–15 2021 total."""
    fc = _get(RAIN, RAIN_AREAS, daily="precipitation_sum", forecast_days=7, timezone="Europe/Brussels")
    old = _get(RAIN_2021, RAIN_AREAS, daily="precipitation_sum", start_date="2021-07-13", end_date="2021-07-15")
    rows = []
    for a in RAIN_AREAS:
        p = pd.Series(fc[a]["daily"]["precipitation_sum"]).fillna(0)
        rows.append({"area": a, "week": p.sum(), "max_2day": p.rolling(2).sum().max(),
                     "july_2021": sum(old[a]["daily"]["precipitation_sum"])})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    build_refs()
