import sys
import time
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import live  # noqa: E402
import reports  # noqa: E402



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


def test_normal_by_default():
    k = live.clock()
    assert k["rps"] == [] and k["plan"] is None and k["variant"] == "rp100"
    T = live.towns_status()
    assert (T.status == "none").all() and live.events().empty and live.outbox().empty


def test_plan_follows_the_rarest_flood_switched_on():
    live.set_rps([10, 100])
    assert live.rps() == [10, 100] and live.plan() == 100 and live.variant() == "rp100"
    live.set_rps([500, 10, 7])  # unknown return periods are ignored
    assert live.rps() == [10, 500] and live.plan() == 500


def test_zones_are_nested():
    T = live.towns_status()
    assert (T.people_rp10 <= T.people_rp100).all() and (T.people_rp100 <= T.people_rp500).all()
    out = {}
    for rp in live.RPS:
        live.set_rps([rp])
        T = live.towns_status()
        out[rp] = set(T.municipality[T.status == "evacuate"])
        assert (T.people[T.status == "evacuate"] >= live.MIN_PEOPLE).all()
    assert out[10] <= out[100] <= out[500]
    assert T.people_rp10.sum() < T.people_rp100.sum() < T.people_rp500.sum()  # rarer floods add people


def test_watch_is_only_reached_by_the_500_year_flood():
    live.set_rps([10])
    w = live.towns_status().query("status == 'watch'")
    assert (w.people < live.MIN_PEOPLE).all() and (w.people_rp500 >= live.MIN_PEOPLE).all()
    live.set_rps([500])
    assert not (live.towns_status().status == "watch").any()


def test_events_and_reports_queued_once():
    live.set_rps([100])
    n_ev, n_ob = len(live.events()), len(live.outbox())
    T = live.towns_status()
    assert n_ev == (T.status == "evacuate").sum() and n_ob == 2 * n_ev  # one mayor + one fire brigade each
    live.tick()
    live.advance()
    assert (len(live.events()), len(live.outbox())) == (n_ev, n_ob)
    f = live.outbox().facts.iloc[0]
    assert "100-year" in f["scenario"] and "people_in_100_year_zone" in f and "people_in_500_year_zone" in f


def test_switching_scenario_starts_clean_but_keeps_checkins():
    live.add_checkin("Pepinster (BE)", "Rue de Pepinster 1", "safe", "A shelter", 2)
    live.close_road("Rue de Pepinster", "Pepinster (BE)")
    live.set_rps([100])
    assert live.closures().auto.any()
    live.set_rps([10])
    assert set(live.events().municipality) == set(live.towns_status().query("status == 'evacuate'").municipality)
    assert not (~live.closures().auto).any()  # the hand closure of the last scenario is gone
    live.set_rps([])
    assert live.events().empty and live.outbox().empty and live.closures().empty
    assert len(live.checkins("Pepinster (BE)")) == 1


def test_auto_closures_lie_in_the_zone():
    live.set_rps([100])
    c = live.closures()
    assert len(c) and c.auto.all() and c.note.str.contains("100-year").all()
    ev = set(live.towns_status().query("status == 'evacuate'").municipality)
    assert set(c.municipality) <= ev


def test_report_fallback_without_key():
    live.set_rps([100])
    r = live.outbox().iloc[0]
    text, source = reports.draft("status", r.recipient, r.facts)
    assert source == "template" and str(next(v for k, v in r.facts.items() if k == "people_in_100_year_zone")) in text
    assert "check before sending" in text
    assert r.facts["town"] in live.report(r.id)


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


def test_close_and_reopen():
    i = live.close_road("Rue de Pepinster", "Pepinster (BE)", by="crisis room", note="bridge damaged")
    c = live.closures()
    assert i in c.id.values and c.set_index("id").at[i, "lon"] is not None
    live.reopen(i)
    assert i not in live.closures().id.values
    assert live.closures(open_only=False).set_index("id").at[i, "open"]


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
