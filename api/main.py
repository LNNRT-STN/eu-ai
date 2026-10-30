"""JSON API for the React frontend (web/). Same numbers as the Streamlit dashboard: it reuses src/live.py (the shared
scenario, check-ins, briefings drafted by Claude) and src/anna.py (outputs/rp loaders), and ports the page arithmetic
of views/start.py (homes in evacuation order), views/evacuate.py (town plan) and views/crisis.py (the board).
Run: .venv/bin/uvicorn api.main:app --reload  (Vite proxies /api to it). The Claude key never leaves this process."""
import json
import logging
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import anna  # noqa: E402
import live  # noqa: E402

for _n in [n for n in logging.root.manager.loggerDict if n.startswith("streamlit")]:
    logging.getLogger(_n).setLevel(logging.ERROR)  # anna's st.cache_data runs bare here: no runtime warnings

DATA = anna.DATA
CARE = {"hospital", "care home"}
ROAD = anna.ROAD


def _safe(o):
    """NaN and inf → null, numpy scalars → Python: pandas rows carry both."""
    if isinstance(o, dict):
        return {str(k): _safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_safe(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


class SafeJSON(JSONResponse):
    def render(self, content):
        return json.dumps(_safe(content), ensure_ascii=False, separators=(",", ":")).encode()


app = FastAPI(title="Flood desk API", default_response_class=SafeJSON)
app.add_middleware(GZipMiddleware, minimum_size=2000)


def about(n):
    """Residents are an order of magnitude: round them as the dashboard does."""
    n = float(n or 0)
    return int(round(n, -2) if n >= 1000 else round(n, -1) if n >= 100 else round(n))


def clean(df):
    """Rows as JSON-safe records (NaN → null)."""
    return json.loads(df.to_json(orient="records"))


def km(lon0, lat0, lon, lat):
    p0, p, dl = np.radians(lat0), np.radians(lat), np.radians(np.asarray(lon) - lon0)
    return 6371 * np.arccos(np.clip(np.sin(p0) * np.sin(p) + np.cos(p0) * np.cos(p) * np.cos(dl), -1, 1))


def town_row(key, v):
    """key = 'area|municipality'; the town's app_towns row for variant v."""
    area, _, muni = key.partition("|")
    T = anna.load()[1]
    t = T[(T.variant == v) & (T.area == area) & (T.municipality == muni)]
    if t.empty:
        raise HTTPException(404, f"{muni} has no residents in the {v[2:]}-year zone")
    return t.iloc[0]


# ================================================================== the shared scenario

class Scenario(BaseModel):
    rps: list[int]


@app.get("/api/scenario")
def scenario():
    c = live.advance()
    return {"rps": c["rps"], "plan": c["plan"], "variant": c["variant"]}


@app.post("/api/scenario")
def set_scenario(s: Scenario):
    live.set_rps(s.rps)
    return scenario()


# ================================================================== map layers

@app.get("/api/flood/{v}")
def flood(v: str):
    """Every study area's zone for one return period, one FeatureCollection."""
    if v not in anna.VARIANT:
        raise HTTPException(404)
    return _flood(v)


@lru_cache
def _flood(v):
    fl = anna.load()[4]
    return {"type": "FeatureCollection", "features": [
        {**f, "properties": {"area": a}} for a in anna.AREA for f in fl[(a, v)]["features"]]}


@app.get("/api/towns")
def towns(v: str = "rp100"):
    """Towns with at least MIN_PEOPLE residents in the zone, most first: the town picker."""
    T = anna.load()[1]
    T = T[(T.variant == v) & (T.people >= live.MIN_PEOPLE)].sort_values("people", ascending=False)
    return [{"key": f"{r.area}|{r.municipality}", "name": r["name"], "label": r.label, "area": r.area,
             "region": anna.AREA[r.area], "country": r.municipality[-3:-1], "people": about(r.people),
             "buildings": int(r.buildings), "lon": r.lon, "lat": r.lat} for _, r in T.iterrows()]


# ================================================================== the region (crisis room board)

def homes_now(v):
    """Every home in the zone with its newest report: needs help | no news | safe."""
    D = live._doors(v)
    ck = live.latest(live.checkins())
    s = ck.set_index(["municipality", "door"]).status if len(ck) else None
    D["s"] = D.join(s.rename("s"), on=["municipality", "door"]).s.fillna("no news") if s is not None else "no news"
    return D


@app.get("/api/region")
def region():
    c = live.advance()
    v, p, sel = c["variant"], c["plan"], c["rps"]
    s = live.towns_status()
    H = homes_now(v)
    n = H.groupby(["municipality", "s"]).size().unstack(fill_value=0).reindex(
        columns=["needs help", "no news", "safe"], fill_value=0)
    s = s.join(n, on="municipality").fillna({"needs help": 0, "no news": 0, "safe": 0})
    s["homes"] = s["needs help"] + s["no news"] + s.safe
    s["todo"] = s["needs help"] + s["no news"]
    ev, wt = s[s.status == "evacuate"], s[s.status == "watch"]
    head = anna.load()[0]
    if p is None:
        verdict = {"tone": "normal", "head": "Normal. No flood scenario is switched on.",
                   "detail": "Switch on a 10-, 100- or 500-year flood to see who sits in the water, where they go and "
                             "which doors to knock on. Until then the map shows the 100-year zone, for planning."}
    else:
        lo = min(sel)
        verdict = {"tone": "evacuate",
                   "head": f"Evacuate {len(ev)} town{'s' if len(ev) != 1 else ''}: about {about(ev.people.sum()):,} "
                           f"people in the {p}-year zone, {int(ev.todo.sum()):,} homes still to clear.",
                   "detail": " ".join(x for x in (
                       f"About {about(ev.people.sum() - ev[f'people_rp{lo}'].sum()):,} more people than in the "
                       f"{lo}-year flood, in the same valleys." if lo < p else "",
                       f"{int(ev['needs help'].sum()):,} homes asked for help: crews go there first."
                       if ev["needs help"].sum() else "",
                       f"A 500-year flood would add {len(wt)} towns and about "
                       f"{about(s.people_rp500.sum() - ev.people.sum()):,} people." if p < 500 and len(wt) else "") if x)}
    T = anna.load()[1]
    in_zone = set(T[(T.variant == v) & (T.people >= live.MIN_PEOPLE)].area + "|" + T.municipality)
    rows = s.dropna(subset=["lon"])
    sh = anna.load()[3]
    compare = [{"rp": rp, "towns": int(((T.variant == f"rp{rp}") & (T.people >= live.MIN_PEOPLE)).sum()),
                "people": head[f"rp{rp}"]["modelled"]["people"], "buildings": head[f"rp{rp}"]["modelled"]["buildings"],
                "walk": head[f"rp{rp}"]["modelled"]["sheltered"], "noPlace": head[f"rp{rp}"]["modelled"]["bus_no_shelter"],
                "care": head[f"rp{rp}"]["sites"]["vulnerable"], "sheltersLost": int(sh[f"in_rp{rp}"].astype(bool).sum())}
               for rp in live.RPS]
    ck = live.checkins()
    feed = ck[~ck.sim].tail(6).iloc[::-1]
    return {
        "scenario": {"rps": sel, "plan": p, "variant": v}, "verdict": verdict, "compare": compare,
        "towns": [{"key": f"{r['area']}|{r['municipality']}", "name": anna.town(r["municipality"]),
                   "region": anna.AREA.get(r["area"], r["area"]), "status": r["status"], "people": about(r["people"]),
                   "byRp": {rp: about(r[f"people_rp{rp}"]) for rp in live.RPS}, "homes": int(r["homes"]),
                   "todo": int(r["todo"]), "help": int(r["needs help"]), "safe": int(r["safe"]), "lon": r["lon"],
                   "lat": r["lat"], "hasPlan": f"{r['area']}|{r['municipality']}" in in_zone}
                  for r in rows.to_dict("records")],
        "feed": [{"id": int(r.id), "door": r.door, "town": anna.town(r.municipality), "status": r.status,
                  "people": int(r.people or 0), "where": (r.where or "").split(",")[0], "when": str(r.when)}
                 for r in feed.itertuples()],
    }


@app.get("/api/briefings")
def briefings():
    ob = live.outbox().iloc[::-1]
    return [{"id": int(r.id), "kind": r.kind, "recipient": r.recipient, "town": anna.town(r.municipality),
             "t": str(r.t), "ready": isinstance(r.text, str), "source": r.source} for r in ob.itertuples()]


@app.get("/api/briefings/{rid}")
def briefing(rid: int):
    ob = live.outbox().set_index("id")
    if rid not in ob.index:
        raise HTTPException(404)
    return {"id": rid, "text": live.report(rid), "source": live.outbox().set_index("id").source.get(rid)}


# ================================================================== one town: the plan

@app.get("/api/town")
def town(key: str, v: str = "rp100"):
    """views/evacuate.py, as data: who leaves, where they go, who goes first, getting out."""
    t = town_row(key, v)
    rp = int(v[2:])
    crit = anna.load()[2]
    recv, bus = anna.load_moves()
    b = bus[bus.variant == v]
    plan = b[(b.municipality == t.municipality) & (b.area == t.area)].copy()
    plan["km"] = km(t.lon, t.lat, plan.s_lon, plan.s_lat).round(1)
    others = b[b.municipality != t.municipality].groupby(["s_lon", "s_lat"]).municipality.nunique()
    plan["shared"] = [int(others.get((x, y), 0)) for x, y in zip(plan.s_lon, plan.s_lat)]
    plan = plan[plan.people >= .5].sort_values(["people", "km"], ascending=[False, True]).reset_index(drop=True)
    ad = anna.plan_shelters(v).query("municipality == @t.municipality").set_index("shelter").address
    walk = min(t.covered, t.people)
    ride = max(t.bus_covered - t.covered, 0) if pd.notna(t.bus_covered) else 0
    left = max(t.people - walk - ride, 0)

    wet = crit[f"in_{v}_flood"].astype(bool) & crit.share_of_site_flooded.ge(.05)
    care = crit[(crit.municipality == t.municipality) & (crit.area == t.area) & wet]
    care = care.assign(rp=[next(int(k[2:]) for k in anna.VARIANT if r[f"in_{k}_flood"]) for _, r in care.iterrows()])
    near = recv.sort_values("km").drop_duplicates("from_name").set_index("from_name")
    weak = care[care.type.isin(CARE)]
    schools = care[care.type == "school"]

    E = pd.read_csv(DATA / "evac_towns.csv")
    ev = E[(E.municipality == t.municipality) & (E.area == t.area) & (E.variant == v)]
    out = None
    if len(ev):
        e = ev.iloc[0]
        out = {"exitMin": round(e.exit_p90_min_4kmh), "exitMedMin": round(e.exit_med_min_4kmh),
               "exitSlowMin": round(e.exit_p90_min_3kmh), "routeMin": round(e.route_p90_min),
               "routeMedMin": round(e.route_med_min), "reroute": float(e.reroute_share),
               "bridges": int(e.flood_bridges_used), "busiestRoad": e.busiest_road,
               "busiestPeople": about(e.busiest_road_people), "busiestMode": e.busiest_road_mode}

    pl = lambda n, one, many: f"{n} {one if n == 1 else many}"
    todo = ([f"start moving its {pl(len(weak), 'hospital or care home', 'hospitals and care homes')}"] if len(weak) else []) \
        + ([f"book buses for about {about(ride):,} residents who cannot walk to a shelter"] if ride >= 5 else []) \
        + ([f"ask the next municipality to take about {about(left):,} more"] if left >= 5 else [])
    if not todo and len(plan):
        todo = [f"open shelter 1, {plan.shelter.iloc[0]}"]
    district = live.district(t.area, t.municipality)
    # message: two biggest shelters within 1.5 km for walkers (else the nearest), the biggest farther one for the bus
    walkers = (plan[plan.km <= 1.5].head(2) if (plan.km <= 1.5).any() else plan.nsmallest(2, "km")).shelter.tolist()
    far = plan[plan.km > 1.5].sort_values("people", ascending=False).shelter.head(1).tolist() or plan.shelter.tail(1).tolist()

    tw = anna.load()[1]
    tw = tw[(tw.municipality == t.municipality) & (tw.area == t.area)].set_index("variant")
    bus_all = bus[(bus.municipality == t.municipality) & (bus.area == t.area)]
    here = crit[(crit.municipality == t.municipality) & (crit.area == t.area) & crit.type.isin(CARE)]
    across = []
    for k in anna.VARIANT:
        ppl = int(tw.people.get(k, 0))
        across.append({"rp": int(k[2:]), "people": about(ppl),
                       "care": int((here[f"in_{k}_flood"].astype(bool) & here.share_of_site_flooded.ge(.05)).sum()),
                       "noPlace": about(max(ppl - bus_all[bus_all.variant == k].people.sum(), 0)) if ppl else 0})

    return {
        "key": key, "name": t["name"], "label": t.label, "region": anna.AREA[t.area], "country": t.municipality[-3:-1],
        "modelledValley": t.area in anna.MODELLED, "lon": t.lon, "lat": t.lat, "rp": rp,
        "people": about(t.people), "buildings": int(t.buildings),
        "walk": about(walk), "ride": about(ride), "left": about(left), "district": district,
        "firstAction": f"Call the mayor and {district}" + (": " + "; ".join(todo) if todo else "") + ".",
        "rerouteWarning": bool(out and out["reroute"] >= .5),
        "shelters": [{"n": i + 1, "name": r.shelter, "cat": r["cat"], "km": float(r.km), "people": about(r.people),
                      "places": int(r.places), "shared": int(r.shared), "lon": r.s_lon, "lat": r.s_lat,
                      "address": ad.get(r.shelter, "") if isinstance(ad.get(r.shelter, ""), str) else ""}
                     for i, r in plan.iterrows()],
        "care": [{"name": r["name"], "type": r.type, "fromRp": int(r.rp), "lon": r.lon, "lat": r.lat,
                  "goTo": near.to_name.get(r["name"]), "goKm": None if r["name"] not in near.index else
                  float(near.km[r["name"]])} for _, r in weak.iterrows()],
        "schools": [{"name": r["name"], "fromRp": int(r.rp)} for _, r in schools.iterrows()],
        "out": out, "across": across,
        "message": {"walkers": walkers, "bus": far[0] if far else None},
    }


@app.get("/api/town/homes")
def town_homes(key: str, v: str = "rp100"):
    """views/start.py ranked(): care sites, then every home of the zone, in the order to evacuate, with its shelter."""
    t = town_row(key, v)
    rp = int(v[2:])
    crit = anna.load()[2]
    cs = crit[(crit.area == t.area) & (crit.municipality == t.municipality) & crit.type.isin(CARE)
              & crit[f"in_{v}_flood"].astype(bool) & crit.share_of_site_flooded.ge(.05)]
    recv = anna.load_moves()[0].sort_values("km").drop_duplicates("from_name").set_index("from_name")
    care = pd.DataFrame({"tier": 1, "address": cs.name.values, "lon": cs.lon.values, "lat": cs.lat.values,
                         "why": [f"{k.capitalize()}: cannot leave alone" for k in cs.type],
                         "go": [recv.to_name.get(n, "No dry site of the same kind in reach") for n in cs.name],
                         "goAddress": "Outside the 500-year zone", "goKm": [recv.km.get(n) for n in cs.name],
                         "goLon": [recv.lon.get(n) for n in cs.name], "goLat": [recv.lat.get(n) for n in cs.name],
                         "street": "", "care": True})
    h = _homes(t.area, t.municipality, v)
    h = anna.destinations(t.municipality, h, v)
    first = h["first"].where(~h.low, 10).clip(upper=rp)
    h["tier"] = [1 if lo and s else 2 if lo or s else 3 for lo, s in zip(h.low, h.single)]
    h["why"] = [f"Wet from a {f}-year flood" + (" · no upper floor" if s else "") for f, s in zip(first, h.single)]
    h = h.rename(columns={"door": "address", "go_address": "goAddress", "go_km": "goKm", "go_lon": "goLon",
                          "go_lat": "goLat"}).assign(care=False)
    if "go" not in h or not h.go.astype(bool).any():
        h["go"], h["goAddress"] = "No dry shelter within 10 km: ask the next town", ""
    cols = ["tier", "care", "address", "street", "why", "go", "goAddress", "goKm", "lon", "lat", "goLon", "goLat"]
    L = pd.concat([care, h.reindex(columns=cols)], ignore_index=True)[cols]
    L = L.sort_values(["tier", "care", "street", "address"], ascending=[True, False, True, True],
                      na_position="last").reset_index(drop=True)
    L[["lon", "lat", "goLon", "goLat"]] = L[["lon", "lat", "goLon", "goLat"]].round(5)
    L["goKm"] = L.goKm.astype(float).round(1)
    return clean(L.drop(columns="street"))


@lru_cache(maxsize=64)
def _homes(area, muni, v):
    """One row per home address of a town in zone v (views/start.py homes())."""
    a = _addresses()
    a = a[(a.area == area) & (a.municipality == muni) & (a.use == 1) & a[f"in_{v}"]]
    a = a.assign(door=a.label.where(a.label.fillna("").astype(bool),
                                    [f"No street address ({y:.5f}, {x:.5f})" for x, y in zip(a.lon, a.lat)]),
                 single=(a.storeys == 1) & (a.height_m != 2.5))  # 2.5 m is OBAT's fill-in height: unknown
    return (a.groupby("door", as_index=False)
            .agg(street=("street", "first"), lon=("lon", "mean"), lat=("lat", "mean"), single=("single", "any"),
                 low=("in_rp10", "any"), first=("in_rp100", lambda x: 100 if x.any() else 500)))


@lru_cache
def _addresses():
    return pd.read_parquet(DATA / "addresses.parquet")


@app.get("/api/town/map")
def town_map(key: str, v: str = "rp100"):
    """The town's flood zone and its evacuation roads (blue dry, orange inside the zone, red closed)."""
    t = town_row(key, v)
    shut = set(live.closures().osm_id.dropna().astype(str))
    roads = [{"type": "Feature", "geometry": f["geometry"],
              "properties": {"people": about(f["properties"]["people"] or 0),
                             "name": f["properties"]["name"] if str(f["properties"]["name"])[:1].isupper() else "",
                             "state": "closed" if str(f["properties"]["osm_id"]) in shut else
                             "wet" if f["properties"]["in_flood_2021"] else "dry"}}
             for f in _edges(v) if f["properties"]["municipality"] == t.municipality]
    return {"zone": anna.load()[4][(t.area, v)], "roads": {"type": "FeatureCollection", "features": roads}}


@lru_cache
def _edges_all():
    return json.loads((DATA / "evac_edges.geojson").read_text())["features"]


def _edges(v):
    return [f for f in _edges_all() if f["properties"]["variant"] == v]


# ================================================================== data & limits

@app.get("/api/limits")
def limits():
    head, *_, qc = anna.load()
    d21 = json.loads((anna.D2021 / "qc_and_validation.json").read_text())
    summ = anna.load(anna.D2021)[5]
    obs = summ[(summ.variant == "worst") & ~summ.area.isin(anna.MODELLED)].set_index("area")
    first = summ[summ.variant == "main"].set_index("area")
    dq = pd.read_csv(anna.D2021 / "dq_report.csv", encoding="utf-8-sig")
    return {
        "floods": [{"rp": rp, "buildings": head[f"rp{rp}"]["modelled"]["buildings"],
                    "people": about(head[f"rp{rp}"]["modelled"]["people"]),
                    "km2": head[f"rp{rp}"]["modelled"]["flood_km2"],
                    "busCovered": about(head[f"rp{rp}"]["modelled"]["bus_covered"]),
                    "noWalk": about(head[f"rp{rp}"]["modelled"]["no_shelter"])} for rp in live.RPS],
        "vesdreTwice": qc["qc"]["vesdre"]["exposed_already_counted_in_earlier_area"],
        "checks": {"ahr": int(obs.loc["ahr"].buildings), "ahrFirst": int(first.loc["ahr"].buildings),
                   "wallonia": int(obs.loc[["liege", "rochefort"]].buildings.sum()),
                   "venlo": int(obs.loc["venlo"].people_2020), "official": anna.OFFICIAL},
        "validation": [{"area": anna.AREA.get(a, a), "rp10": x["RP10"]["recall"], "rp100": x["RP100"]["recall"],
                        "rp500": x["RP500"]["recall"], "observed": x["RP100"]["observed_flooded"],
                        "inZone": x["RP100"]["efas_flooded"]} for a, x in d21["efas_validation"].items()],
        "dq": {"total": len(dq), "warn": clean(dq[dq.status == "WARN"][["area", "indicator", "value", "warn_above",
                                                                       "likely_cause", "who_can_fix"]])},
    }
