"""Live shared state for every role page, plus a scenario engine that replays July 2021.

One SQLite file (data/live.db, gitignored) in WAL mode, short transactions: several browser sessions read and write
at once. Pages call advance() on every refresh; it moves the shared clock and, from the river flows at that time,
raises town status, records events, auto-closes flooded evacuation roads, adds simulated (drill) check-ins and queues
briefings for mayors and fire brigades. Briefings are drafted in a background thread (reports.py) and stored here.

Both modes use the same rule (impact.py): the town's river against its 2-, 5- and 20-year flows. Live: the GloFAS
ensemble over the next forecast.HORIZON days, a level counting when forecast.PROB of the runs reach it. Replay: the
backtest, July 2021 flows against thresholds fitted on the record up to forecast.BACKTEST_YEAR.

Replay assumptions (say them in the UI): each GloFAS daily flow holds for its whole day (no interpolated hours); the
replay is shown as a drill that starts on DRILL_DAY0 (dates moved, data unchanged); a town's
level holds its highest value reached so far in the replay (water that has risen is not un-warned when it falls).
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
import zlib
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("LIVE_DB", ROOT / "data" / "live.db"))  # LIVE_DB: a scratch copy for test servers
CSV = ROOT / "data" / "checkins.csv"
DATA = ROOT / "outputs" / "data"
REFS = Path(__file__).resolve().parent / "out" / "meuse" / "gauge_refs.json"

START, END = pd.Timestamp("2021-07-12 06:00"), pd.Timestamp("2021-07-18 00:00")
# Drill: the replay is shown as if it began on the pitch day, so the July 2021 flood is "coming" now. The clock and the
# data stay in July 2021; only the dates on screen and in briefings move (12 Jul 2021 -> Fri 30 Oct 2026).
DRILL_DAY0 = pd.Timestamp("2026-10-30")
SHIFT = DRILL_DAY0 - START.normalize()
STATUS = ["none", "watch", "warn", "evacuate"]  # = level 0-3: river at the 2-, 5-, 20-year flood (impact.py)
ALERT = ("warn", "evacuate")
MODELLED_AREAS = {"vesdre"}  # as anna.MODELLED: no satellite map, EFAS 500-year model  # the steps that make an event and briefings
NO_POINT = "no river point"
RADIUS_KM = 15
CHECKIN_COLS = ["when", "municipality", "door", "status", "where", "people", "drill"]
WHERE = ["A shelter", "Family or friends", "A spare bed offered by a resident", "Elsewhere, outside the flood zone"]
SIM_CAP = 4000          # simulated check-in rows, all towns together
SIM_SHARE, SIM_HOURS = .85, 18  # share of doors that report safe, reached this many hours after "evacuate"
HELP_EVERY = 15         # one simulated door in this many asks for help
AUTO_ROADS = 3          # busiest flooded evacuation roads closed per town at level 3
# district that runs the response, copied from views/evacuate.py
CALL = {"ahr": "Kreis Ahrweiler", "erftstadt": "Rhein-Erft-Kreis", "schleiden": "Kreis Euskirchen",
        "euskirchen": "Kreis Euskirchen", "eschweiler": "StädteRegion Aachen", "wassenberg": "Kreis Heinsberg",
        "venlo": "Safety region Limburg-Noord", "liege": "Province of Liège (governor)",
        "vesdre": "Province of Liège (governor)", "rochefort": "Province of Namur (governor)"}
# Towns whose district differs from their study area's (team summary of the administrative map; check locally).
CALL_TOWN = {"Weilerswist (DE)": "Kreis Euskirchen", "Blankenheim (DE)": "Kreis Euskirchen", "Inden (DE)": "Kreis Düren",
             "Maastricht (NL)": "Safety region Zuid-Limburg", "Maasgouw (NL)": "Safety region Limburg-Noord",
             "Kinrooi (BE)": "Province of Limburg (governor)", "Maasmechelen (BE)": "Province of Limburg (governor)",
             "Riemst (BE)": "Province of Limburg (governor)", "Hamoir (BE)": "Province of Liège (governor)",
             "Durbuy (BE)": "Province of Luxembourg (governor)", "Hotton (BE)": "Province of Luxembourg (governor)",
             "La Roche-en-Ardenne (BE)": "Province of Luxembourg (governor)",
             "Rendeux (BE)": "Province of Luxembourg (governor)"}


def drill(t):
    """A replay time as the drill shows it (same hour, dates moved to start on DRILL_DAY0)."""
    return pd.Timestamp(t) + SHIFT


def district(area, municipality):
    """Who orders an evacuation across municipalities for this town (Kreis, safety region or governor)."""
    return CALL_TOWN.get(municipality, CALL.get(area, area))

SCHEMA = """
CREATE TABLE IF NOT EXISTS clock(id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT, t TEXT, playing INTEGER, speed REAL,
  wall REAL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS state(municipality TEXT PRIMARY KEY, status TEXT, level INTEGER, since TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, t TEXT, municipality TEXT, area TEXT, "from" TEXT, "to" TEXT,
  mode TEXT, UNIQUE(municipality, "to", mode));
CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, "when" TEXT, municipality TEXT, door TEXT, status TEXT,
  "where" TEXT, people INTEGER, drill INTEGER, sim INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS checkins_muni ON checkins(municipality);
CREATE TABLE IF NOT EXISTS closures(id INTEGER PRIMARY KEY, osm_id TEXT, name TEXT, municipality TEXT, "by" TEXT,
  note TEXT, lon REAL, lat REAL, t TEXT, auto INTEGER DEFAULT 0, open INTEGER DEFAULT 0, reopened_t TEXT);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, kind TEXT, recipient TEXT, municipality TEXT, t TEXT,
  facts TEXT, text TEXT, source TEXT, created REAL, UNIQUE(kind, recipient, municipality, t));
CREATE TABLE IF NOT EXISTS drafts(h TEXT PRIMARY KEY, text TEXT, source TEXT);
"""


# ---------- database ----------

def _connect(path):
    path.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(path, timeout=15, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=15000")
    return c


_ready = set()
_init = threading.Lock()


@contextmanager
def _db(write=False):
    path = DB
    c = _connect(path)
    try:
        if str(path) not in _ready:
            with _init:
                c.executescript(SCHEMA)
                _migrate_csv(c)
                _ready.add(str(path))
        if write:
            c.execute("BEGIN IMMEDIATE")
        yield c
        if write:
            c.execute("COMMIT")
    except BaseException:
        if write and c.in_transaction:
            c.execute("ROLLBACK")
        raise
    finally:
        c.close()


def _q(sql, args=()):
    with _db() as c:
        return pd.read_sql_query(sql, c, params=args)


def _migrate_csv(c):
    if c.execute("SELECT 1 FROM meta WHERE k='csv_migrated'").fetchone():
        return
    c.execute("BEGIN IMMEDIATE")
    if not c.execute("SELECT 1 FROM meta WHERE k='csv_migrated'").fetchone():
        if CSV.exists():
            try:
                df = pd.read_csv(CSV)
                for r in df.reindex(columns=CHECKIN_COLS).itertuples(index=False):
                    c.execute('INSERT INTO checkins("when",municipality,door,status,"where",people,drill) '
                              "VALUES(?,?,?,?,?,?,?)", (str(r.when), r.municipality, r.door, r.status,
                                                        None if pd.isna(r.where) else r.where,
                                                        int(r.people) if pd.notna(r.people) else 1,
                                                        int(str(r.drill).lower() in ("true", "1"))))
            except pd.errors.EmptyDataError:
                pass
        c.execute("INSERT INTO meta VALUES('csv_migrated', ?)", (str(pd.Timestamp.now()),))
    c.execute("COMMIT")


# ---------- clock ----------

def _ts(x):
    return pd.Timestamp(x).floor("s")


def _now():
    return pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None).floor("s")


def _row(c):
    r = c.execute("SELECT mode,t,playing,speed,wall FROM clock WHERE id=1").fetchone()
    if r is None:
        r = ("replay", str(START), 0, 1.0, time.time())
        c.execute("INSERT OR IGNORE INTO clock VALUES(1,?,?,?,?,?)", r)
    return r


def clock() -> dict:
    """mode "replay"|"live", t (pd.Timestamp, Brussels local time), playing, speed (hours per real second)."""
    with _db() as c:
        m, t, p, s, _ = _row(c)
    return dict(mode=m, t=_ts(t), playing=bool(p), speed=float(s))


def _set(**kw):
    with _db(write=True) as c:
        _row(c)
        if "playing" in kw or "speed" in kw:  # bank the time played so far before changing rate
            _advance(c)
        kw["wall"] = time.time()
        c.execute(f"UPDATE clock SET {', '.join(f'{k}=?' for k in kw)} WHERE id=1",
                  [str(v) if isinstance(v, pd.Timestamp) else v for v in kw.values()])


def play():
    _set(playing=1)


def pause():
    _set(playing=0)


def set_speed(x):
    _set(speed=float(x))


def set_mode(m):
    """Switching mode starts a clean scenario: the other mode's alerts, closures and simulated check-ins go."""
    assert m in ("replay", "live")
    if m != clock()["mode"]:
        reset()
    _set(mode=m, t=_now() if m == "live" else START, playing=int(m == "live"))


def reset(t0="2021-07-12 06:00", rewind=False):
    """Back to t0 in replay mode, paused. Clears events, status, outbox, closures and simulated check-ins;
    check-ins made by people (and by the check-in page's own drill) stay. rewind (going back on the day slider): keep
    what people did up to t0 (roads closed by hand, check-ins), drop what they did after it."""
    t0 = str(_ts(t0))
    with _db(write=True) as c:
        _row(c)
        c.execute("UPDATE clock SET mode='replay', t=?, playing=0, wall=? WHERE id=1", (t0, time.time()))
        for tb in ("events", "state", "outbox"):
            c.execute(f"DELETE FROM {tb}")
        if rewind:
            c.execute("DELETE FROM closures WHERE auto=1 OR t > ?", (t0,))
            c.execute("UPDATE closures SET open=0, reopened_t=NULL WHERE reopened_t > ?", (t0,))
            c.execute('DELETE FROM checkins WHERE sim=0 AND "when" > ?', (t0,))
        else:
            c.execute("DELETE FROM closures")
        c.execute("DELETE FROM checkins WHERE sim=1")
        c.execute("DELETE FROM meta WHERE k LIKE 'done:%' OR k LIKE 'sim_off:%'")


def seek(t):
    """Jump the replay to t (held to START..END), still playing if it was. Forward, the next tick applies everything
    passed on the way; back, the scenario is rebuilt from t (a replay never un-warns a town), and briefings already
    drafted come back from the drafts cache."""
    t, k = min(max(_ts(t), START), END), clock()
    if k["mode"] != "replay" or t < k["t"]:
        reset(t, rewind=k["mode"] == "replay")
    _set(t=t, playing=int(k["playing"] and k["mode"] == "replay" and t < END))
    tick(t, "replay")


def _advance(c):
    m, t, p, s, wall = _row(c)
    now = time.time()
    t = _ts(t)
    if m == "live":
        t = _now()
    elif p:
        t = t + pd.Timedelta(hours=(now - wall) * s)
        if t >= END:
            t, p = END, 0
    c.execute("UPDATE clock SET t=?, playing=?, wall=? WHERE id=1", (str(_ts(t)), p, now))
    return m, _ts(t)


def advance() -> dict:
    """Move the shared clock by real time elapsed × speed while playing, then apply the scenario at the new time.
    Call on every page refresh; safe from several sessions at once."""
    with _db(write=True) as c:
        _advance(c)
    k = clock()
    try:
        tick(k["t"], k["mode"])
    except sqlite3.OperationalError:  # another session holds the lock: it is ticking for us
        pass
    return k


# ---------- rivers ----------

_cache = {}
_WATCH = [REFS, REFS.parent / "replay_2021.json", REFS.parent / "annual_max.json", DATA / "town_gauge.csv",
          DATA / "town_efas.csv", DATA / "app_towns.csv"]


def _fresh():
    """Drop cached rivers and towns when another process rebuilds their files (the server keeps running)."""
    st = tuple(f.stat().st_mtime if f.exists() else 0 for f in _WATCH)
    if _cache.get("stamp") != st:
        _cache.clear()
        _cache["stamp"] = st


def _refs():
    if "refs" not in _cache:
        _cache["refs"] = json.loads(REFS.read_text())
    return _cache["refs"]


def _hourly():
    """GloFAS daily flows 10-20 Jul 2021, each held for its whole day (hourly grid). Not interpolated: a line
    towards the next day's mean would put tomorrow's flow into today's hours and claim a time the data cannot give."""
    if "hourly" not in _cache:
        r = pd.DataFrame(json.loads((REFS.parent / "replay_2021.json").read_text()))  # as core.load_replay(),
        r.index = pd.to_datetime(r.index)  # uncached so a rebuild shows up live
        grid = pd.date_range(r.index[0], r.index[-1] + pd.Timedelta(hours=23), freq="h")
        _cache["hourly"] = r.reindex(grid, method="ffill")
    return _cache["hourly"]


def _live_runs(t):
    """Per gauge, each ensemble run's peak over the HORIZON days from t's day: what the live status is judged on."""
    import core
    import forecast
    _, series, *_ = core.outlook()
    if series is None or "m00" not in series:
        return {}
    d0 = t.normalize()
    w = series[(pd.to_datetime(series.time) >= d0) & (pd.to_datetime(series.time) < d0 + pd.Timedelta(days=forecast.HORIZON))]
    return {g: x[forecast.members(x)].max().values for g, x in w.groupby("gauge")}


def _live_flows(t):
    import core
    gauges, series, *_ = core.outlook()
    if gauges is None:
        return {}
    out = {}
    for g, d in (series.groupby("gauge") if series is not None else []):
        s = d.set_index("time").river_discharge.dropna()
        s.index = pd.to_datetime(s.index) + pd.Timedelta(hours=12)
        if len(s) and s.index[0] <= t <= s.index[-1]:
            out[g] = float(np.interp(t.as_unit("ns").value, s.index.as_unit("ns").asi8, s.values))
    for g, q in zip(gauges.gauge, gauges.now):
        out.setdefault(g, float(q))
    return out


def flows(t, mode=None) -> dict:
    """Flow (m³/s) per river point at time t: the 2021 replay, or in live mode the latest live forecast."""
    t = _ts(t)
    _fresh()
    if (mode or clock()["mode"]) == "live":
        return _live_flows(t)
    h = _hourly()
    t = min(max(t, h.index[0]), h.index[-1])
    x, xp = t.as_unit("ns").value, h.index.as_unit("ns").asi8
    return {g: float(np.interp(x, xp, h[g].values)) for g in h.columns}


# ---------- towns ----------

def _km(lon0, lat0, lon, lat):
    return np.hypot((lon - lon0) * 111.32 * np.cos(np.radians(lat0)), (lat - lat0) * 110.57)


def _town_gauge():
    """area, municipality, gauge: outputs/data/town_gauge.csv, else the nearest forecast.GAUGES point within 15 km."""
    import impact
    return impact.load_town_gauge()


def _towns():
    """Towns of the worst-case map with their river point and its modelled July 2021 peak (context)."""
    if "towns" in _cache:
        return _cache["towns"]
    import anna
    t = anna.load()[1]
    t = t[t.variant == "worst"].drop_duplicates("municipality")[
        ["area", "municipality", "people", "lon", "lat"]].reset_index(drop=True)
    tg = _town_gauge().drop_duplicates("municipality")
    t = t.merge(tg[["municipality", "gauge"]], on="municipality", how="left")
    refs = _refs()
    t["gauge"] = t.gauge.where(t.gauge.map(lambda g: isinstance(g, str)), None).astype(object)
    t["q2021"] = t.gauge.map(lambda g: refs[g][1] if isinstance(g, str) and g in refs else np.nan)  # context only
    _cache["towns"] = t
    return t


def _upto(mode):
    import forecast
    return forecast.BACKTEST_YEAR if mode == "replay" else None


def _judge(T, fl, mode):
    """level 0-3, status, people_expected, return_period, probability per town for flows fl (one flow, or the
    ensemble runs' peaks, per gauge): impact.impact_forecast on the mode's thresholds."""
    import impact
    imp = impact.impact_forecast({g: v for g, v in fl.items() if np.size(v) and not np.isnan(v).all()},
                                 T[["area", "municipality", "gauge"]], _upto(mode))
    imp = imp.drop_duplicates("municipality").set_index("municipality").reindex(T.municipality)
    status = pd.Series(imp.status.values, index=T.index).replace({"no gauge": NO_POINT}).fillna(NO_POINT)
    return (pd.Series(imp.level.values, index=T.index).fillna(0).astype(int), status,
            pd.Series(imp.people_expected.values, index=T.index).fillna(0).astype(int),
            pd.Series(imp.return_period.values, index=T.index), pd.Series(imp.probability.values, index=T.index))


def _q2(T, mode):
    """The 2-year flow of each town's river point, on the mode's thresholds."""
    import forecast
    thr = forecast.thresholds(_upto(mode))
    return T.gauge.map(lambda g: thr[g]["q"][2] if g in thr else np.nan)


def _replay():
    """Hour by hour over the replay, from the highest flow reached so far (a risen river is not un-warned):
    level, status and people_expected per town, and the first hour each status is reached."""
    if "replay" in _cache:
        return _cache["replay"]
    T, h = _towns(), _hourly().cummax()
    lv, stt, pe, rp = [], [], [], []
    for _, day in h.groupby(h.index.normalize()):  # daily flows held all day: judge once per day
        a, b, c, d, *_ = _judge(T, day.iloc[0].to_dict(), "replay")
        for _ in range(len(day)):
            lv.append(a.values), stt.append(b.values), pe.append(c.values), rp.append(d.values)
    lv, stt, pe, rp = np.array(lv), np.array(stt, dtype=object), np.array(pe), np.array(rp)
    first = lambda mask: [h.index[mask[:, j].argmax()] if mask[:, j].any() else pd.NaT for j in range(len(T))]
    rank = np.vectorize(lambda s: STATUS.index(s) if s in STATUS else -1)(stt)
    w, e = STATUS.index("warn"), STATUS.index("evacuate")
    times = pd.DataFrame({"municipality": T.municipality, "t_warn": first(rank >= w), "t_evacuate": first(rank >= e),
                          "t_level3": first(lv >= 3)}).set_index("municipality")
    _cache["replay"] = dict(index=h.index, level=lv, status=stt, people_expected=pe, return_period=rp, times=times,
                            peak=h)
    return _cache["replay"]


def towns_status(t=None, mode=None) -> pd.DataFrame:
    """[municipality, area, gauge, flow, q2, q2021, return_period, probability, level 0-3, status, people,
    people_expected, since].
    level 1/2/3 at the 2-/5-/20-year flow of the town's river point, status watch/warn/evacuate (or "no river
    point"), from impact.impact_forecast: live on the ensemble runs over the next forecast.HORIZON days (probability:
    share of runs at the 5-year flow), replay on the July 2021 flow against pre-2021 thresholds (the backtest).
    q2: the 2-year flow; q2021: the modelled July 2021 peak (context). people: residents inside the 2021 flood
    extent; people_expected: residents in the EFAS zone of the forecast return period. In replay, level and status
    hold the highest value reached so far; since is when the current status was first reached."""
    k = clock()
    t, mode = _ts(t if t is not None else k["t"]), mode or k["mode"]
    _fresh()
    T = _towns().copy()
    fl = flows(t, mode)
    T["flow"] = T.gauge.map(lambda g: fl.get(g, np.nan) if isinstance(g, str) else np.nan)
    if mode == "replay":
        R = _replay()
        i = max(int(R["index"].searchsorted(t, side="right")) - 1, 0)
        T["level"], T["status"], T["people_expected"] = R["level"][i], R["status"][i], R["people_expected"][i]
        T["return_period"], T["probability"] = R["return_period"][i], (R["level"][i] >= 2).astype(float)
        tm = R["times"].reindex(T.municipality)
        T["since"] = np.where(T.status == "evacuate", tm.t_evacuate.values,
                              np.where(T.status == "warn", tm.t_warn.values, np.datetime64("NaT", "ns")))
        T["since"] = pd.to_datetime(T.since)
    else:
        runs = _live_runs(t)
        T["level"], T["status"], T["people_expected"], T["return_period"], T["probability"] = _judge(T, runs or fl, mode)
        st = _q("SELECT municipality, since FROM state").set_index("municipality").since
        T["since"] = pd.to_datetime(T.municipality.map(st))
    T["q2"] = _q2(T, mode)
    T["level"] = T.level.astype(int)
    T["people_expected"] = T.people_expected.astype(int)
    return T[["municipality", "area", "gauge", "flow", "q2", "q2021", "return_period", "probability", "level", "status",
              "people", "people_expected", "since"]].sort_values(["level", "people"], ascending=False).reset_index(drop=True)


def events(muni=None) -> pd.DataFrame:
    """Status rises: t, municipality, area, from, to (oldest first)."""
    sql = 'SELECT t, municipality, area, "from", "to" FROM events'
    df = _q(sql + (" WHERE municipality=?" if muni else "") + " ORDER BY t, id", (muni,) if muni else ())
    df["t"] = pd.to_datetime(df.t)
    return df


# ---------- scenario tick ----------

def _fmt_t(t):
    return pd.Timestamp(t).strftime("%-d %b %Y %H:%M")


def tick(t=None, mode=None):
    """Apply the scenario at time t: status rises -> events, reports, auto closures, simulated check-ins."""
    k = clock()
    t, mode = _ts(t if t is not None else k["t"]), mode or k["mode"]
    T = towns_status(t, mode)
    T = T[T.status != NO_POINT]
    queued = []
    with _db(write=True) as c:
        old = dict(c.execute("SELECT municipality, status FROM state").fetchall())
        times = _replay()["times"] if mode == "replay" else None
        for r in T.itertuples():
            before = old.get(r.municipality, "none")
            if STATUS.index(r.status) <= STATUS.index(before):
                continue
            steps = [x for x in STATUS[STATUS.index(before) + 1: STATUS.index(r.status) + 1] if x in ALERT]
            prev, since = before, t
            for s in steps:
                when = times.at[r.municipality, f"t_{s}"] if mode == "replay" else t
                when = t if pd.isna(when) else when
                c.execute('INSERT OR IGNORE INTO events(t,municipality,area,"from","to",mode) VALUES(?,?,?,?,?,?)',
                          (str(when), r.municipality, r.area, prev, s, mode))
                queued.append((r, prev, s, when))
                prev, since = s, when
            c.execute("INSERT OR REPLACE INTO state VALUES(?,?,?,?)", (r.municipality, r.status, int(r.level),
                                                                       str(since)))
    # steps reached at the same time (a daily flow can jump from none to evacuate) get one briefing, for the highest
    # step and from the status before the jump; one per step would collide on the outbox's (recipient, town, time) key
    last = {}
    for r, prev, s, when in queued:
        k = (r.municipality, str(when))
        last[k] = (r, last[k][1] if k in last else prev, s, when)
    for r, prev, s, when in last.values():
        facts = _facts(r, prev, s, when, t, mode)
        name = _name(r.municipality)
        queue_report("status", f"Mayor of {name}", r.municipality, when, facts)
        queue_report("status", f"Fire brigade, {name}", r.municipality, when, facts)
    _auto_close(T, t, mode)
    if mode == "replay":
        _simulate_checkins(T, t)


def _name(m):
    import anna
    return anna.town(m)


def _facts(r, prev, s, when, t, mode):
    """Small facts dict for one report: numbers rounded here, so the AI never has to."""
    import forecast
    raw = _towns().set_index("municipality").loc[r.municipality]
    q, pe, rp, p = r.flow, r.people_expected, r.return_period, r.probability
    if mode == "replay":
        at = towns_status(when, mode).set_index("municipality").loc[r.municipality]
        q, pe, rp, p = at.flow, at.people_expected, at.return_period, at.probability
    thr = forecast.thresholds(_upto(mode))[r.gauge]
    import anna
    modelled = r.area in anna.MODELLED
    return {"town": _name(r.municipality), "status": s, "from": "normal" if prev == "none" else prev,
            # a replay steps on daily flows, so it gives the day only
            "time": f"{drill(when):%a %-d %b %Y} (daily river flow)" if mode == "replay" else _fmt_t(when),
            "scenario": (f"replay of the 2021 forecast: the July 2021 flood shown as if it began on {DRILL_DAY0:%a %-d %b %Y}, on "
                         "modelled river flows computed afterwards (not a live forecast)"
                         if mode == "replay" else "live forecast"),
            "river_point": r.gauge, "modelled_flow_m3s": int(round(q)),
            "flow_is_a": forecast.rp_text(rp) + " flood (return period from the model's own record "
                         + thr["years"] + ")",
            "status_rule": "watch at the 2-year flood, warn at the 5-year, evacuate at the 20-year"
                           + (f"; in the forecast, when {forecast.PROB:.0%} of the ensemble runs reach it within "
                              f"{forecast.HORIZON} days" if mode == "live" else ""),
            **({"forecast_runs_at_5_year_flood_or_above": f"{p:.0%}"} if mode == "live" and pd.notna(p) else {}),
            "modelled_five_year_flow_m3s": int(round(thr["q"][5])),
            "modelled_twenty_year_flow_m3s": int(round(thr["q"][20])),
            "modelled_july_2021_peak_m3s": int(round(raw.q2021)),
            ("people_in_modelled_flood_zone" if modelled else "people_in_2021_satellite_flood_extent"): int(r.people),
            "flood_extent": ("modelled (EFAS 500-year; the satellite did not map this valley)" if modelled
                             else "observed by satellite in July 2021 (a floor)"),
            "people_in_modelled_flood_zone_for_this_flood": int(pe),
            "district": district(r.area, r.municipality)}


def _edges():
    if "edges" not in _cache:
        import geopandas as gpd
        e = gpd.read_file(DATA / "evac_edges.geojson")
        e = e[e.in_flood_2021.astype(bool)].copy()
        pt = e.geometry.representative_point()
        e = pd.DataFrame(e.drop(columns="geometry").assign(lon=pt.x, lat=pt.y))
        e["osm_id"] = e.osm_id.astype(str)
        _cache["edges"] = e
    return _cache["edges"]


def _auto_close(T, t, mode):
    hit = T[T.level >= 3]
    if hit.empty:
        return
    e = _edges()
    tm = _replay()["times"]
    with _db(write=True) as c:
        for m in hit.municipality:
            key = f"done:close:{m}"
            if c.execute("SELECT 1 FROM meta WHERE k=?", (key,)).fetchone():
                continue
            when = tm.at[m, "t_level3"] if mode == "replay" and pd.notna(tm.at[m, "t_level3"]) else t
            roads = (e[e.municipality == m].assign(named=lambda x: x.name.fillna("").str[:1].str.isupper())
                     .sort_values(["named", "people", "length_m"], ascending=False)
                     .drop_duplicates("name").head(AUTO_ROADS))
            if roads.named.any():  # unnamed ways carry their OSM type ("footway"): only when nothing else is flooded
                roads = roads[roads.named]
            for r in roads.itertuples():
                c.execute('INSERT INTO closures(osm_id,name,municipality,"by",note,lon,lat,t,auto) '
                          "VALUES(?,?,?,?,?,?,?,?,1)", (r.osm_id, r.name, m, "scenario",
                                                       "Evacuation road in the July 2021 water; river at its 20-year flood",
                                                       float(r.lon), float(r.lat), str(when)))
            c.execute("INSERT INTO meta VALUES(?,?)", (key, str(t)))


def _doors():
    """One row per home address in the 2021 water, as views/checkin.py builds them (copied, not imported)."""
    if "doors" not in _cache:
        a = pd.read_parquet(DATA / "addresses.parquet")
        a = a[a.use == 1].copy()
        a["door"] = a.label.where(a.label.astype(bool), "No address · " + a.bid)
        a.loc[a.label.astype(bool) & a.street.isna(), "door"] = "House no. " + a.housenumber + " (no street name)"
        _cache["doors"] = a.groupby(["municipality", "door"], as_index=False).size()[["municipality", "door"]]
    return _cache["doors"]


def _simulate_checkins(T, t):
    """For towns at evacuate, a growing, seeded share of doors check in safe (one in HELP_EVERY needs help)."""
    ev = T[T.status == "evacuate"]
    if ev.empty:
        return
    D = _doors()
    tm = _replay()["times"]
    with _db(write=True) as c:
        have = dict(c.execute("SELECT municipality, COUNT(*) FROM checkins WHERE sim=1 GROUP BY 1").fetchall())
        off = {k[8:] for (k,) in c.execute("SELECT k FROM meta WHERE k LIKE 'sim_off:%'")}  # cleared by hand
        total = sum(have.values())
        for m in ev.municipality:
            d = D[D.municipality == m].door.to_numpy()
            if not len(d) or total >= SIM_CAP or m in off or "*" in off:
                continue
            t0 = tm.at[m, "t_evacuate"]
            hours = (t - t0) / pd.Timedelta(hours=1) if pd.notna(t0) else 0
            n_full = int(SIM_SHARE * len(d))
            n = min(n_full, int(n_full * max(hours, 0) / SIM_HOURS))
            n = min(n, have.get(m, 0) + SIM_CAP - total)
            if n <= have.get(m, 0):
                continue
            rng = np.random.default_rng(zlib.crc32(m.encode()))
            order, where, ppl = rng.permutation(len(d)), rng.integers(0, len(WHERE), len(d)), rng.integers(1, 5, len(d))
            rows = []
            for i in range(have.get(m, 0), n):
                j = order[i]
                helpme = i % HELP_EVERY == HELP_EVERY - 1
                when = t0 + pd.Timedelta(hours=SIM_HOURS * i / max(n_full, 1))
                rows.append((str(_ts(when)), m, str(d[j]), "needs help" if helpme else "safe",
                             None if helpme else WHERE[where[j]], int(ppl[j]), 1, 1))
            c.executemany('INSERT INTO checkins("when",municipality,door,status,"where",people,drill,sim) '
                          "VALUES(?,?,?,?,?,?,?,?)", rows)
            total += len(rows)


# ---------- check-ins ----------

def checkins(muni=None) -> pd.DataFrame:
    """Check-ins (when, municipality, door, status, where, people, drill), newest last; drill rows include simulated
    ones (column sim)."""
    sql = 'SELECT id, "when", municipality, door, status, "where", people, drill, sim FROM checkins'
    df = _q(sql + (" WHERE municipality=?" if muni else "") + " ORDER BY id", (muni,) if muni else ())
    df["drill"], df["sim"] = df.drill.astype(bool), df.sim.astype(bool)
    return df


def latest(ck: pd.DataFrame) -> pd.DataFrame:
    """Each home's newest check-in (by entry order): a crew's correction replaces the resident's earlier report.
    A real report always beats a simulated one, whatever their order."""
    return ck.sort_values(["sim", "id"], ascending=[False, True]).drop_duplicates(["municipality", "door"], keep="last")


def add_checkin(municipality, door, status="safe", where=None, people=1, drill=False, when=None) -> int:
    """status "no news" undoes a home's earlier reports (a crew's correction)."""
    assert status in ("safe", "needs help", "no news")
    when = when if when is not None else clock()["t"]
    with _db(write=True) as c:
        cur = c.execute('INSERT INTO checkins("when",municipality,door,status,"where",people,drill) VALUES(?,?,?,?,?,?,?)',
                        (str(_ts(when)), municipality, door, status, where, int(people), int(bool(drill))))
        return cur.lastrowid


def clear_drill(muni=None):
    """Remove drill check-ins (simulated ones included), for one town or all; no new simulated ones arrive there
    until the next reset."""
    with _db(write=True) as c:
        c.execute("DELETE FROM checkins WHERE drill=1" + (" AND municipality=?" if muni else ""),
                  (muni,) if muni else ())
        c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (f"sim_off:{muni or '*'}", "1"))


# ---------- road closures ----------

def closures(open_only=True) -> pd.DataFrame:
    """Closed roads: id, osm_id, name, municipality, by, note, lon, lat, t, auto (scenario), open (reopened)."""
    df = _q('SELECT * FROM closures' + (" WHERE open=0" if open_only else "") + " ORDER BY t, id")
    df["auto"], df["open"] = df.auto.astype(bool), df.open.astype(bool)
    return df


def close_road(road, municipality, by="crisis room", note="", lon=None, lat=None) -> int:
    """Close a road by OSM id or by name. Position from evac_edges when not given and the road is known."""
    road = str(road)
    name, osm = (road, None)
    try:
        e = _edges()
    except Exception:
        e = pd.DataFrame(columns=["osm_id", "name", "lon", "lat"])
    hit = e[e.osm_id == road]
    if road.isdigit():
        osm, name = road, (hit.name.iloc[0] if len(hit) else None)
    else:
        hit = e[(e.name == road) & (e.municipality == municipality)] if "municipality" in e else hit.iloc[:0]
    if len(hit) and lon is None:
        lon, lat = float(hit.lon.iloc[0]), float(hit.lat.iloc[0])
    with _db(write=True) as c:
        return c.execute('INSERT INTO closures(osm_id,name,municipality,"by",note,lon,lat,t) VALUES(?,?,?,?,?,?,?,?)',
                         (osm, name, municipality, by, note, lon, lat, str(clock()["t"]))).lastrowid


def reopen(id):
    with _db(write=True) as c:
        c.execute("UPDATE closures SET open=1, reopened_t=? WHERE id=?", (str(clock()["t"]), int(id)))


# ---------- outbox ----------

def outbox(recipient=None) -> pd.DataFrame:
    """Queued briefings: id, kind, recipient, municipality, t, facts (dict), text (None while drafting),
    source ai|template|drafting|None. Oldest first."""
    df = _q("SELECT id, kind, recipient, municipality, t, facts, text, source FROM outbox"
            + (" WHERE recipient=?" if recipient else "") + " ORDER BY t, id", (recipient,) if recipient else ())
    df["facts"] = df.facts.map(json.loads)
    df["t"] = pd.to_datetime(df.t)
    return df


def _hash(kind, recipient, facts):
    return hashlib.sha1(json.dumps([kind, recipient, facts], sort_keys=True, default=str).encode()).hexdigest()


def queue_report(kind, recipient, municipality, t, facts: dict) -> int:
    """Queue one report; drafted in the background (once per identical facts: replays reuse earlier drafts)."""
    with _db(write=True) as c:
        cur = c.execute("INSERT OR IGNORE INTO outbox(kind,recipient,municipality,t,facts,created) VALUES(?,?,?,?,?,?)",
                        (kind, recipient, municipality, str(_ts(t)), json.dumps(facts, default=str), time.time()))
        rid = cur.lastrowid if cur.rowcount else None
    _start_worker()
    return rid


def report(id) -> str:
    """Text of one report, drafting it now if the background worker has not got to it yet."""
    _draft_one(int(id))
    for _ in range(100):  # the worker may be drafting it right now: wait up to 10 s
        with _db() as c:
            r = c.execute("SELECT text FROM outbox WHERE id=?", (int(id),)).fetchone()
        if not r or r[0] is not None:
            return r[0] if r else None
        time.sleep(.1)
    return None


def _draft_one(rid):
    import reports
    with _db(write=True) as c:  # claim the row so two threads never draft the same one
        r = c.execute("SELECT kind, recipient, facts FROM outbox WHERE id=? AND text IS NULL AND source IS NULL",
                      (rid,)).fetchone()
        if not r:
            return
        c.execute("UPDATE outbox SET source='drafting' WHERE id=?", (rid,))
    kind, recipient, facts = r[0], r[1], json.loads(r[2])
    h = _hash(kind, recipient, facts)
    with _db() as c:
        got = c.execute("SELECT text, source FROM drafts WHERE h=?", (h,)).fetchone()
    try:
        text, source = got or reports.draft(kind, recipient, facts)
    except Exception:
        text, source = reports.template(kind, recipient, facts), "template"
    with _db(write=True) as c:
        if source == "ai" and not got:
            c.execute("INSERT OR REPLACE INTO drafts VALUES(?,?,?)", (h, text, source))
        c.execute("UPDATE outbox SET text=?, source=? WHERE id=?", (text, source, rid))


WORKERS = 4  # parallel drafts, so the outbox keeps up with a fast replay
_workers = []
_lock = threading.Lock()


def _work():
    while True:
        with _db() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM outbox WHERE text IS NULL AND source IS NULL "
                                           "ORDER BY t, id LIMIT 20").fetchall()]
        if not ids:
            return
        for i in ids:
            try:
                _draft_one(i)
            except Exception:
                time.sleep(1)


def _start_worker():
    with _lock:
        _workers[:] = [w for w in _workers if w.is_alive()]
        if not _workers:
            _unstick()
        while len(_workers) < WORKERS:
            w = threading.Thread(target=_work, name=f"live-reports-{len(_workers)}", daemon=True)
            w.start()
            _workers.append(w)


def _unstick():
    """Rows left 'drafting' by a process that died get another go."""
    with _db(write=True) as c:
        c.execute("UPDATE outbox SET source=NULL WHERE source='drafting' AND created < ?", (time.time() - 120,))


# ---------- one-line summary for headers ----------

def summary(t=None) -> dict:
    """Counts for a header strip: towns at warn / evacuate, people in them, check-ins safe / needing help,
    roads closed, reports queued."""
    T = towns_status(t)
    ck = latest(checkins())
    return {"warn": int((T.status == "warn").sum()), "evacuate": int((T.status == "evacuate").sum()),
            # observed (satellite) and modelled (Vesdre, EFAS 500-year) are never summed
            "people_evacuate": int(T.people[(T.status == "evacuate") & ~T.area.isin(MODELLED_AREAS)].sum()),
            "people_evacuate_modelled": int(T.people[(T.status == "evacuate") & T.area.isin(MODELLED_AREAS)].sum()),
            "evacuate_under_50": int(((T.status == "evacuate") & (T.people < 50)).sum()),
            "safe": int((ck.status == "safe").sum()), "needs_help": int((ck.status == "needs help").sum()),
            "roads_closed": int(closures().lon.notna().sum()), "reports": len(outbox())}  # roads: those on the map
