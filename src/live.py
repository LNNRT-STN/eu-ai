"""Live shared state for every role page, plus the return-period scenario engine.

One SQLite file (data/live.db, gitignored) in WAL mode, short transactions: several browser sessions read and write
at once. The crisis room switches return periods on (10-, 100-, 500-year river flood, EFAS hazard maps; one or several
to compare). The response plans for the rarest one switched on: every town with at least MIN_PEOPLE residents in that
zone goes to evacuate, its busiest evacuation roads inside the zone close, and a briefing is queued for its mayor and
its fire brigade (drafted in a background thread by reports.py and stored here). Nothing moves in time: switching the
scenario starts it clean. Check-ins from residents and crews stay.

The zones are modelled (EFAS, all rivers at that return period at once, no dikes): a planning map, not a forecast.
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("LIVE_DB", ROOT / "data" / "live.db"))  # LIVE_DB: a scratch copy for test servers
CSV = ROOT / "data" / "checkins.csv"
DATA = ROOT / "outputs" / "rp"

RPS = (10, 100, 500)  # EFAS return periods, years (outputs/rp: variants rp10 / rp100 / rp500)
MIN_PEOPLE = 10        # residents in the zone for a town to evacuate
STATUS = ["none", "watch", "warn", "evacuate"]  # = level 0-3; this scenario uses none / watch / evacuate
ALERT = ("warn", "evacuate")
NO_POINT = "no river point"
RADIUS_KM = 15
CHECKIN_COLS = ["when", "municipality", "door", "status", "where", "people", "drill"]
WHERE = ["A shelter", "Family or friends", "A spare bed offered by a resident", "Elsewhere, outside the flood zone"]
AUTO_ROADS = 3          # busiest evacuation roads inside the zone closed per town at evacuate
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
                _drop_replay(c)
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


def _drop_replay(c):
    """A database from the July 2021 replay engine: its alerts, briefings, closures and simulated check-ins belong to
    a clock that no longer exists, so they go once; check-ins people made stay."""
    if c.execute("SELECT 1 FROM meta WHERE k='engine' AND v='rp'").fetchone():
        return
    c.execute("BEGIN IMMEDIATE")
    for tb in ("events", "state", "outbox", "closures"):
        c.execute(f"DELETE FROM {tb}")
    c.execute("DELETE FROM checkins WHERE sim=1")
    c.execute("DELETE FROM meta WHERE k LIKE 'done:%' OR k LIKE 'sim_off:%'")
    c.execute("INSERT OR REPLACE INTO meta VALUES('engine', 'rp')")
    c.execute("COMMIT")


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


# ---------- scenario ----------

def _ts(x):
    return pd.Timestamp(x).floor("s")


def _now():
    return pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None).floor("s")


def rps() -> list:
    """The return periods the crisis room has switched on (sorted; empty = everything normal). Shared by every role."""
    with _db() as c:
        r = c.execute("SELECT v FROM meta WHERE k='rps'").fetchone()
    return sorted(int(x) for x in json.loads(r[0]) if int(x) in RPS) if r else []


def plan():
    """The return period the response plans for: the rarest one switched on (None when everything is normal)."""
    return max(rps(), default=None)


def variant(rp=None):
    """Data variant of a return period (outputs/rp): 'rp100'. Without one, the planned flood, else the 100-year."""
    return f"rp{rp or plan() or 100}"


def set_rps(sel):
    """Switch the scenario. A new scenario starts clean: alerts, briefings and closed roads of the last one go;
    check-ins people made stay. Then the new scenario's alerts and briefings are raised at once."""
    sel = sorted({int(x) for x in sel or [] if int(x) in RPS})
    if sel == rps():
        return
    reset()
    with _db(write=True) as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES('rps', ?)", (json.dumps(sel),))
    tick()


def clock() -> dict:
    """The scenario as the pages read it: t (now, Brussels), rps (switched on), plan (rarest), variant."""
    r = rps()
    return dict(t=_now(), rps=r, plan=max(r, default=None), variant=variant(max(r, default=None)))


def reset():
    """Clear the scenario's alerts, statuses, briefings and closed roads (check-ins people made stay)."""
    with _db(write=True) as c:
        for tb in ("events", "state", "outbox", "closures"):
            c.execute(f"DELETE FROM {tb}")
        c.execute("DELETE FROM checkins WHERE sim=1")
        c.execute("DELETE FROM meta WHERE k LIKE 'done:%' OR k = 'rps'")


def advance() -> dict:
    """Apply the scenario (idempotent) and return it. Call on every page refresh; safe from several sessions."""
    try:
        tick()
    except sqlite3.OperationalError:  # another session holds the lock: it is ticking for us
        pass
    return clock()


# ---------- towns ----------

_cache = {}
_WATCH = [DATA / "app_towns.csv", DATA / "addresses.parquet", DATA / "evac_edges.geojson", DATA / "bus_plan.csv"]


def _fresh():
    """Drop cached towns when another process rebuilds their files (the server keeps running)."""
    st = tuple(f.stat().st_mtime if f.exists() else 0 for f in _WATCH)
    if _cache.get("stamp") != st:
        _cache.clear()
        _cache["stamp"] = st


def _towns():
    """One row per town: area, lon, lat and residents in each return-period zone (people_rp10/100/500)."""
    _fresh()
    if "towns" in _cache:
        return _cache["towns"]
    import anna
    t = anna.load()[1]
    p = t.pivot_table(index="municipality", columns="variant", values="people", aggfunc="sum").reindex(
        columns=[f"rp{r}" for r in RPS]).fillna(0).astype(int).add_prefix("people_")
    base = t.sort_values("people", ascending=False).drop_duplicates("municipality").set_index("municipality")
    T = base[["area", "lon", "lat"]].join(p).reset_index()
    _cache["towns"] = T
    return T


def towns_status(t=None, mode=None) -> pd.DataFrame:
    """[municipality, area, lon, lat, people_rp10/100/500, return_period, level, status, people, people_expected,
    since]. evacuate (level 3): at least MIN_PEOPLE residents in the planned zone; watch (level 1): not in it, but in
    the zone of a rarer flood (the 500-year); otherwise none. people = residents in the planned zone (the 100-year zone
    when the scenario is normal, for context); people_expected = people (kept for older callers)."""
    p = plan()
    T = _towns().copy()
    T["people"] = T[f"people_{variant(p)}"]
    T["return_period"] = p
    if p is None:
        T["status"] = "none"
    else:
        hit, rarer = T.people >= MIN_PEOPLE, T[f"people_rp{RPS[-1]}"] >= MIN_PEOPLE
        T["status"] = np.where(hit, "evacuate", np.where(rarer, "watch", "none"))
    T["level"] = T.status.map(STATUS.index).astype(int)
    T["people_expected"] = T.people
    st = _q("SELECT municipality, since FROM state").set_index("municipality").since
    T["since"] = pd.to_datetime(T.municipality.map(st))
    return T.sort_values(["level", "people"], ascending=False).reset_index(drop=True)


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
    """Apply the scenario once: each town at evacuate gets an event and one briefing each for its mayor and its
    fire brigade; the busiest evacuation roads inside the planned zone close."""
    p = plan()
    if p is None:
        return
    sig = f"done:scenario:{json.dumps(rps())}"
    with _db() as c:
        if c.execute("SELECT 1 FROM meta WHERE k=?", (sig,)).fetchone():
            return
    t = _now()
    T = towns_status()
    ev = T[T.status == "evacuate"]
    with _db(write=True) as c:
        if c.execute("SELECT 1 FROM meta WHERE k=?", (sig,)).fetchone():
            return
        for r in ev.itertuples():
            c.execute('INSERT OR IGNORE INTO events(t,municipality,area,"from","to",mode) VALUES(?,?,?,?,?,?)',
                      (str(t), r.municipality, r.area, "none", "evacuate", f"rp{p}"))
            c.execute("INSERT OR REPLACE INTO state VALUES(?,?,?,?)", (r.municipality, r.status, int(r.level), str(t)))
        c.execute("INSERT INTO meta VALUES(?,?)", (sig, str(t)))
    _auto_close(ev, t)
    for r in ev.itertuples():  # biggest towns first: their briefings are drafted first
        facts = _facts(r, t)
        name = _name(r.municipality)
        queue_report("status", f"Fire brigade, {name}", r.municipality, t, facts)
        queue_report("status", f"Mayor of {name}", r.municipality, t, facts)


def _name(m):
    import anna
    return anna.town(m)


def _facts(r, t):
    """Small facts dict for one briefing: numbers rounded here, so the AI never has to."""
    import anna
    p, v = plan(), variant()
    go = anna.plan_shelters(v).query("municipality == @r.municipality").nlargest(3, "people")
    bus = anna.load()[1].query("variant == @v and municipality == @r.municipality")
    placed = int(round(bus.bus_covered.sum())) if len(bus) else 0
    homes = _doors(v).query("municipality == @r.municipality")
    closed = closures().query("municipality == @r.municipality and auto").name.dropna().tolist()
    others = {f"people_in_{q}_year_zone": int(getattr(r, f"people_rp{q}")) for q in RPS if q != p}
    return {"town": _name(r.municipality), "status": "evacuate", "from": "normal", "time": _fmt_t(t),
            "scenario": f"planning scenario: a {p}-year river flood (EFAS flood hazard map; a flood this size has "
                        f"a {100 / p:g} % chance in any year). A model zone, not a forecast and not an observed flood",
            "status_rule": "evacuate every town with at least 10 residents inside the zone of the planned flood",
            f"people_in_{p}_year_zone": int(r.people), **others,
            "homes_to_check": int(len(homes)),
            "people_with_a_shelter_place_within_10_km": placed,
            "people_without_a_shelter_place": max(int(r.people) - placed, 0),
            "shelters": "; ".join(f"{g.label} ({g.address or 'no street address'}): about {int(round(g.people))} people"
                                  for g in go.itertuples()) or "none in the plan",
            **({"roads_closed": ", ".join(closed)} if closed else {}),
            "flood_extent": "modelled (EFAS; no dikes or flood walls in the model, so towns behind defences are an "
                            "upper bound)",
            "district": district(r.area, r.municipality)}


def _edges():
    if "edges" not in _cache:
        import geopandas as gpd
        e = gpd.read_file(DATA / "evac_edges.geojson")
        pt = e.geometry.representative_point()
        e = pd.DataFrame(e.drop(columns="geometry").assign(lon=pt.x, lat=pt.y))
        e["osm_id"] = e.osm_id.astype(str)
        _cache["edges"] = e
    e = _cache["edges"]
    return e[(e.variant == variant()) & e.in_flood_2021.astype(bool)]


def _auto_close(ev, t):
    """Per town at evacuate, its AUTO_ROADS busiest evacuation roads that lie inside the planned zone close."""
    if ev.empty:
        return
    e = _edges()
    with _db(write=True) as c:
        for m in ev.municipality:
            key = f"done:close:{m}"
            if c.execute("SELECT 1 FROM meta WHERE k=?", (key,)).fetchone():
                continue
            roads = (e[e.municipality == m].assign(named=lambda x: x.name.fillna("").str[:1].str.isupper())
                     .sort_values(["named", "people", "length_m"], ascending=False)
                     .drop_duplicates("name").head(AUTO_ROADS))
            if roads.named.any():  # unnamed ways carry their OSM type ("footway"): only when nothing else is flooded
                roads = roads[roads.named]
            for r in roads.itertuples():
                c.execute('INSERT INTO closures(osm_id,name,municipality,"by",note,lon,lat,t,auto) '
                          "VALUES(?,?,?,?,?,?,?,?,1)", (r.osm_id, r.name, m, "scenario",
                                                       f"Evacuation road inside the {plan()}-year flood zone",
                                                       float(r.lon), float(r.lat), str(t)))
            c.execute("INSERT INTO meta VALUES(?,?)", (key, str(t)))


def _doors(v=None):
    """One row per home address in a return-period zone, as views/checkin.py builds them (copied, not imported)."""
    if "doors" not in _cache:
        a = pd.read_parquet(DATA / "addresses.parquet")
        a = a[a.use == 1].copy()
        a["door"] = a.label.where(a.label.astype(bool), "No address · " + a.bid)
        a.loc[a.label.astype(bool) & a.street.isna(), "door"] = "House no. " + a.housenumber + " (no street name)"
        _cache["doors"] = a
    a = _cache["doors"]
    a = a[a[f"in_{v or variant()}"]]
    return a.groupby(["municipality", "door"], as_index=False).size()[["municipality", "door"]]


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
    """Counts for a header strip: towns at evacuate / watch, people in them, check-ins safe / needing help,
    roads closed, reports queued."""
    T = towns_status()
    ck = latest(checkins())
    ev = T.status == "evacuate"
    return {"rps": rps(), "plan": plan(), "evacuate": int(ev.sum()), "watch": int((T.status == "watch").sum()),
            "warn": 0, "people_evacuate": int(T.people[ev].sum()), "people_evacuate_modelled": 0,
            "evacuate_under_50": int((ev & (T.people < 50)).sum()),
            "safe": int((ck.status == "safe").sum()), "needs_help": int((ck.status == "needs help").sum()),
            "roads_closed": int(closures().lon.notna().sum()), "reports": len(outbox())}  # roads: those on the map
