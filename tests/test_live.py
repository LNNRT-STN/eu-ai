import sys
import time
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import live  # noqa: E402
import reports  # noqa: E402

STATUS = {"none": -1, "watch": 0, "warn": 1, "evacuate": 2}


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "DB", tmp_path / "live.db")
    monkeypatch.setattr(live, "CSV", tmp_path / "checkins.csv")
    monkeypatch.setattr(reports, "_key", lambda: None)  # never call the API from tests
    monkeypatch.setattr(reports, "_client", None)
    live.reset()
    yield
    for w in list(live._workers):
        w.join(10)


def test_clock_advance():
    k = live.clock()
    assert k["mode"] == "replay" and k["t"] == live.START and not k["playing"]
    live.set_speed(3600)  # 3600 replay hours per real second
    live.play()
    time.sleep(0.05)
    t = live.advance()["t"]
    assert t > live.START
    live.pause()
    t1 = live.clock()["t"]
    time.sleep(0.05)
    assert live.advance()["t"] == t1  # paused: no movement
    live.set_speed(10 ** 6)
    live.play()
    time.sleep(0.05)
    k = live.advance()
    assert k["t"] == live.END and not k["playing"]  # stops at the end of the replay
    live.reset()
    assert live.clock()["t"] == live.START


def _rises(muni):
    seen = []
    for t in pd.date_range(live.START, live.END, freq="2h"):
        s = live.towns_status(t, "replay").set_index("municipality").loc[muni]
        seen.append((STATUS[s.status], int(s.level)))
    return seen


@pytest.mark.parametrize("muni", ["Pepinster (BE)", "Bad Neuenahr-Ahrweiler, Stadt (DE)"])
def test_status_rises_monotonically(muni):
    T = live._towns().set_index("municipality")
    if muni not in T.index or not isinstance(T.at[muni, "gauge"], str):
        pytest.skip(f"no river point for {muni} yet")
    seen = _rises(muni)
    assert seen == sorted(seen), "status must never fall during the replay"
    assert seen[0][0] <= 0 and seen[-1][0] == 2, "from normal or watch to evacuate"


def test_events_and_reports_queued_once():
    for t in pd.date_range(live.START, "2021-07-14 12:00", freq="6h"):
        live.tick(t, "replay")
    live.tick(pd.Timestamp("2021-07-14 12:00"), "replay")  # a second tick at the same time adds nothing
    ev = live.events("Pepinster (BE)")
    assert list(ev.to) == ["warn", "evacuate"]
    ob = live.outbox()
    pep = ob[ob.municipality == "Pepinster (BE)"]
    # one briefing per recipient and time: warn and evacuate on the same day give one, for evacuate
    assert len(pep) == 2 * pep.t.nunique() and pep.facts.map(lambda f: f["status"]).iloc[-1] == "evacuate"
    assert set(pep.recipient) == {"Mayor of Pepinster", "Fire brigade, Pepinster"}
    assert pep.facts.iloc[0]["district"] == "Province of Liège (governor)"


def test_district_overrides_area():
    assert live.district("liege", "Maastricht (NL)") == "Safety region Zuid-Limburg"
    assert live.district("erftstadt", "Weilerswist (DE)") == "Kreis Euskirchen"
    assert live.district("ahr", "Schuld (DE)") == "Kreis Ahrweiler"


def test_checkin_round_trip():
    i = live.add_checkin("Pepinster (BE)", "Rue de Pepinster 1", "safe", "A shelter", 3)
    ck = live.checkins("Pepinster (BE)")
    row = ck[ck.id == i].iloc[0]
    assert (row.door, row.status, row["where"], row.people, row.drill) == ("Rue de Pepinster 1", "safe", "A shelter",
                                                                           3, False)
    assert list(ck.columns[1:8]) == live.CHECKIN_COLS


def test_simulated_checkins_seeded_and_capped():
    t = pd.Timestamp("2021-07-15 12:00")
    live.tick(t, "replay")
    a = live.checkins()
    live.reset()
    live.tick(t, "replay")
    b = live.checkins()
    assert len(a) and a.sim.all() and len(a) <= live.SIM_CAP
    assert a.door.tolist() == b.door.tolist()  # reproducible
    assert (a.status == "needs help").any()


def test_close_and_reopen():
    i = live.close_road("Rue de Pepinster", "Pepinster (BE)", by="crisis room", note="bridge damaged")
    c = live.closures()
    assert i in c.id.values and c.set_index("id").at[i, "lon"] is not None
    live.reopen(i)
    assert i not in live.closures().id.values
    assert live.closures(open_only=False).set_index("id").at[i, "open"]


def test_auto_closures_at_level3():
    live.tick(pd.Timestamp("2021-07-14 13:00"), "replay")
    c = live.closures()
    assert c.auto.all() and len(c) and "Pepinster (BE)" in c.municipality.values


def test_report_fallback_without_key():
    text, source = reports.draft("status", "Mayor of Pepinster", {"town": "Pepinster", "status": "evacuate",
                                                                  "time": "13 Jul 2021 18:00", "modelled_flow_m3s": 146})
    assert source == "template" and "146" in text and "check before sending" in text
    i = live.queue_report("status", "Mayor of Pepinster", "Pepinster (BE)", pd.Timestamp("2021-07-13 18:00"),
                          {"town": "Pepinster", "status": "evacuate"})
    assert "Pepinster" in live.report(i)
    assert live.outbox().set_index("id").at[i, "source"] == "template"


def test_crew_correction_replaces_report():
    m = "Pepinster (BE)"
    live.add_checkin(m, "Rue de Pepinster 1", "needs help", "", 2)
    assert live.summary()["needs_help"] == 1
    live.add_checkin(m, "Rue de Pepinster 1", "safe", "Checked by a crew", 2)
    s = live.summary()
    assert (s["safe"], s["needs_help"]) == (1, 0)  # one home, counted once: its newest report
    live.add_checkin(m, "Rue de Pepinster 1", "no news")
    s = live.summary()
    assert (s["safe"], s["needs_help"]) == (0, 0)


def test_real_report_beats_simulated():
    m = "Bad Neuenahr-Ahrweiler, Stadt (DE)"
    D = live._doors()
    door = D[D.municipality == m].door.iloc[0]
    live.add_checkin(m, door, "needs help", "", 1, when=pd.Timestamp("2021-07-12 07:00"))
    live.tick(pd.Timestamp("2021-07-16 12:00"), "replay")
    last = live.latest(live.checkins(m)).set_index("door")
    assert last.at[door, "status"] == "needs help"


def test_clear_simulated_stays_cleared():
    m = "Bad Neuenahr-Ahrweiler, Stadt (DE)"
    live.tick(pd.Timestamp("2021-07-15 12:00"), "replay")
    assert len(live.checkins(m))
    live.clear_drill(m)
    live.tick(pd.Timestamp("2021-07-16 12:00"), "replay")
    assert not live.checkins(m).sim.any()
    live.reset()
    live.tick(pd.Timestamp("2021-07-15 12:00"), "replay")
    assert live.checkins(m).sim.any()  # reset turns the simulation back on


def test_seek_back_keeps_earlier_hand_closures():
    live.reset()
    live.seek("2021-07-13 06:00")
    a = live.close_road("Rue de Pepinster", "Pepinster (BE)")
    live.seek("2021-07-15 06:00")
    b = live.close_road("Rue de Pepinster", "Pepinster (BE)")
    live.seek("2021-07-14 06:00")
    ids = set(live.closures().id)
    assert a in ids and b not in ids


def test_mode_switch_clears_scenario():
    live.seek("2021-07-15 12:00")
    assert len(live.events())
    live.set_mode("live")
    live.set_mode("replay")
    assert live.events().empty and not live.checkins().sim.any()
