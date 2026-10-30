"""Live outlook from Open-Meteo (free, no key): GloFAS river discharge and rain forecasts.

River status works as EFAS and GloFAS do: return-period thresholds (2-, 5-, 20-, 100-year flows) come from the
same model's own record at the same cell, so a model that runs high or low in a small valley is rated against
itself. The 51 ensemble runs give a probability: a level counts when at least PROB of the runs reach it within
HORIZON days. The July 2021 peak is kept as context only. The 2021 replay (live.py) is the backtest: it rates the
2021 flows against thresholds fitted on the record up to BACKTEST_YEAR, what was known before the flood."""
import json, time
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import requests

FLOOD = "https://flood-api.open-meteo.com/v1/flood"
RAIN = "https://api.open-meteo.com/v1/forecast"
RAIN_2021 = "https://archive-api.open-meteo.com/v1/archive"
REFS = Path(__file__).resolve().parent / "out" / "meuse" / "gauge_refs.json"  # thresholds don't change: fetch once
AMAX = REFS.parent / "annual_max.json"  # annual peak per gauge and year, for the return-period thresholds
# GloFAS 0.05° cells on each river, picked as the highest-flow cell near the town (scan in a 3×3 neighbourhood)
GAUGES = {"Meuse · Liège": (50.675, 5.625), "Meuse · Maastricht": (50.925, 5.675), "Meuse · Roermond": (51.225, 5.925),
          "Meuse · Venlo": (51.425, 6.125), "Vesdre · Chaudfontaine": (50.575, 5.625), "Vesdre · Verviers": (50.575, 5.825),
          "Ourthe · Tabreux": (50.475, 5.525), "Lesse · Rochefort": (50.175, 5.175), "Rur · Wassenberg": (51.025, 6.175),
          "Inde · Eschweiler": (50.875, 6.325), "Hoëgne · Theux": (50.525, 5.775), "Ourthe · Hotton": (50.275, 5.425),
          "Geul · Gulpen-Wijlre": (50.825, 5.825), "Ahr · Schuld": (50.425, 6.875), "Ahr · Altenahr": (50.525, 6.975),
          "Ahr · Bad Bodendorf": (50.525, 7.175), "Erft · Bad Münstereifel": (50.625, 6.775),
          "Erft · Erftstadt": (50.775, 6.775), "Urft · Gemünd": (50.625, 6.425)}
# Bad Bodendorf: the Rhine cells next door carry ~2,400 m³/s, so the scan keeps to the Ahr cell (~10 m³/s mean).
# Urft · Gemünd sits just above the Urft reservoir; Geul · Gulpen-Wijlre is ~15 km downstream of Kelmis.
# headwaters where the July 2021 rain fell
RAIN_AREAS = {"Upper Vesdre (Eupen)": (50.55, 6.05), "Upper Ourthe": (50.25, 5.65), "Eifel / upper Rur": (50.55, 6.35),
              "Amblève (Stavelot)": (50.40, 5.93)}
RP = (2, 5, 20, 100)  # return periods (years) on screen; levels 1-3 are the first three
PROB = .3             # a level counts when at least 30 % of the ensemble runs reach it (EFAS notification rule)
HORIZON = 10          # days ahead that set the status: GloFAS skill falls off beyond about ten days
BACKTEST_YEAR = 2020  # the 2021 replay uses thresholds fitted on the record up to this year
# river status in the water family, light blue → deep violet (EFAS marks its severe level purple): never the orange
# of residents or the red/amber of commune priority, so the three keys on one map can't be confused
LEVELS = [("Normal", "#b9d3f2"), ("Above 2-year flood", "#7c9cf0"), ("Above 5-year flood", "#6c3fd1"),
          ("Above 20-year flood", "#3f1170")]


def _get(url, pts, retries=0, **params):
    lat, lon = zip(*pts.values())
    for _ in range(retries + 1):
        r = requests.get(url, params={"latitude": ",".join(map(str, lat)), "longitude": ",".join(map(str, lon)), **params},
                         timeout=60)
        if r.status_code != 429:
            break
        time.sleep(30)  # free tier: wait for the per-minute weight to clear
    if r.status_code == 429:
        raise RuntimeError("Open-Meteo free-tier limit reached, try again in a minute")
    r.raise_for_status()
    j = r.json()
    return dict(zip(pts, j if isinstance(j, list) else [j]))  # one location → object, several → list


def refs():
    """Context flows per gauge from the model's own history: median annual peak 2011–2020 and the July 2021 peak.
    Free tier weighs requests by time span, so this runs once (python src/forecast.py) to a file."""
    if not REFS.exists():
        raise RuntimeError("reference flows missing, run python src/forecast.py once")
    return json.loads(REFS.read_text())


def build_refs():
    out = json.loads(REFS.read_text()) if REFS.exists() else {}  # keep the points already fetched
    for g in [g for g in GAUGES if g not in out]:
        h = _get(FLOOD, {g: GAUGES[g]}, retries=5, daily="river_discharge", start_date="2011-01-01", end_date="2021-12-31")[g]
        h = pd.Series(h["daily"]["river_discharge"], index=pd.to_datetime(h["daily"]["time"]))
        out[g] = [h[:"2020"].groupby(h[:"2020"].index.year).max().median(), h["2021-07-10":"2021-07-25"].max()]
        print(g, [round(q) for q in out[g]], "peak", h["2021-07-10":"2021-07-25"].idxmax().date())
        REFS.write_text(json.dumps(out, indent=1))
        time.sleep(20)  # stay under the per-minute weight limit


def build_annual_maxima():
    """Annual peak flow per gauge, GloFAS v4 reanalysis 1997–2025 (the record Open-Meteo serves), to AMAX. Once."""
    out = json.loads(AMAX.read_text()) if AMAX.exists() else {}  # keep the points already fetched
    for g in [g for g in GAUGES if g not in out]:
        h = _get(FLOOD, {g: GAUGES[g]}, retries=5, daily="river_discharge", start_date="1984-01-01",
                 end_date="2025-12-31")[g]
        h = pd.Series(h["daily"]["river_discharge"], index=pd.to_datetime(h["daily"]["time"])).dropna()
        out[g] = {str(y): round(float(q), 2) for y, q in h.groupby(h.index.year).max().items()}
        print(g, len(out[g]), "years", flush=True)
        AMAX.write_text(json.dumps(out, indent=1, ensure_ascii=False))
        time.sleep(20)


# ---------------------------------------------------------------- return periods

def gumbel(peaks):
    """Gumbel (EV1) fit by L-moments to annual peaks → (mu, beta), the distribution EFAS and GloFAS fit for their
    thresholds. L-moments rather than plain moments: one outlying year moves the fit less."""
    x = np.sort(np.asarray(peaks, float))
    n = len(x)
    l1 = x.mean()
    l2 = 2 * (np.arange(n) / (n - 1) * x).mean() - l1
    beta = l2 / np.log(2)
    return l1 - .5772 * beta, beta


def flow_for(fit, T):
    """Flow of the T-year flood."""
    mu, beta = fit
    return mu - beta * np.log(-np.log(1 - 1 / T))


def period_of(fit, q):
    """Return period (years) of flow q; 1 for flows below the usual yearly peak. Beyond ~2x the record length the
    number is an extrapolation: show it as "more than 100-year" (rp_text)."""
    mu, beta = fit
    with np.errstate(over="ignore", divide="ignore"):
        return np.maximum(1 / -np.expm1(-np.exp(-(np.asarray(q, float) - mu) / beta)), 1.0)


def rp_text(T):
    return "below 2-year" if T < 2 else "above 100-year" if T > 100 else f"{T:.0f}-year"


@lru_cache(4)
def thresholds(upto=None):
    """{gauge: {"fit": (mu, beta), "years": "1997–2025", "q": {T: flow}}} from the annual peaks up to year `upto`
    (the whole record when None). Live uses the whole record, the 2021 backtest stops at BACKTEST_YEAR."""
    out = {}
    for g, by in json.loads(AMAX.read_text()).items():
        ys = [int(y) for y in by if upto is None or int(y) <= upto]
        fit = gumbel([by[str(y)] for y in ys])
        out[g] = {"fit": fit, "years": f"{min(ys)}–{max(ys)}", "q": {T: float(flow_for(fit, T)) for T in RP}}
    return out


def level(q, thr):
    """0-3 for one flow (or an array): how many of the 2-, 5- and 20-year flows it reaches."""
    q = np.asarray(q, float)
    return sum((q >= thr["q"][T]).astype(int) for T in RP[:3])


def ensemble_level(peaks, thr):
    """(level 0-3, {T: probability}) for the ensemble runs' peaks: the highest level reached by at least PROB of
    the runs, and the share of runs that reach each return-period flow."""
    peaks = np.atleast_1d(np.asarray(peaks, float))
    p = {T: float((peaks >= thr["q"][T]).mean()) for T in RP}
    return max([0] + [i + 1 for i, T in enumerate(RP[:3]) if p[T] >= PROB]), p


# ---------------------------------------------------------------- live outlook

def members(d):
    """The ensemble columns of one gauge's daily frame (control run + 50 members)."""
    return [c for c in d if c.startswith("m") and c[1:].isdigit()]


def rivers():
    """Per gauge: the 30-day ensemble forecast, rated against the return-period flows over the next HORIZON days.
    Returns (gauges, series); series is daily per gauge with the control run, median, quartiles, wettest run and
    every run (m00 control, m01-m50)."""
    thr, ref = thresholds(), refs()
    fc = _get(FLOOD, GAUGES, daily="river_discharge", ensemble="true", past_days=7, forecast_days=30)
    today = pd.Timestamp(date.today())
    rows, series = [], []
    for g, (lat, lon) in GAUGES.items():
        raw = fc[g]["daily"]
        runs = pd.DataFrame({f"m{0 if k == 'river_discharge' else int(k[-2:]):02d}": v for k, v in raw.items()
                             if k.startswith("river_discharge")})
        d = runs.assign(time=pd.to_datetime(raw["time"]), gauge=g, river_discharge=runs.m00,
                        river_discharge_median=runs.median(1), river_discharge_p25=runs.quantile(.25, axis=1),
                        river_discharge_p75=runs.quantile(.75, axis=1), river_discharge_max=runs.max(1))
        t = thr[g]
        ahead = d[(d.time >= today) & (d.time < today + pd.Timedelta(days=HORIZON))]
        peaks = ahead[members(d)].max()
        lvl, p = ensemble_level(peaks, t)
        peak = ahead.river_discharge_median.max()
        # the day the runs most agree on crossing the status flow (or, at normal, the median's peak day)
        daily_p = (ahead[members(d)] >= t["q"][RP[max(lvl, 1) - 1]]).mean(1)
        when = ahead.time[daily_p.idxmax()] if lvl else ahead.time[ahead.river_discharge_median.idxmax()]
        rows.append({"gauge": g, "lat": lat, "lon": lon, "now": d.river_discharge[d.time == today].iloc[0],
                     "peak": peak, "peak_day": when, "worst": peaks.max(), "rp_peak": float(period_of(t["fit"], peak)),
                     "rp_worst": float(period_of(t["fit"], peaks.max())), "level": lvl,
                     "level_worst": int(level(peaks.max(), t)), "chance": p[RP[lvl - 1]] if lvl else p[RP[0]],
                     **{f"p{T}": p[T] for T in RP}, **{f"q{T}": t["q"][T] for T in RP},
                     "q2021": ref[g][1], "years": t["years"]})
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
    build_annual_maxima()
