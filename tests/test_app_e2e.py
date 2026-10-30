"""End to end, headless: the opening page's flow (flood, town, an address, on to the desk), every role's pages and
their next-step cards, and the way back to the start. Streamlit's AppTest runs the real dashboard.py in-process."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import live  # noqa: E402
import reports  # noqa: E402

APP = str(SRC / "dashboard.py")


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


def run(at):
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def by_key(widgets, key):
    return next(w for w in widgets if w.key == key)


def keys(at):
    return {w.key for w in at.button}


def opening():
    return run(AppTest.from_file(APP, default_timeout=180))


def test_opening_flow_to_the_desk():
    at = opening()
    by_key(at.segmented_control, "lf_flood").set_value(100)
    run(at)
    town = by_key(at.selectbox, "lf_town")
    assert town.options[0] == "Whole map · every town" and len(town.options) > 5
    assert any(df.key == "lf_top" for df in at.dataframe)  # the most affected towns, as a sortable table

    town.set_value(town.options[1])  # the most affected town, by its label
    run(at)
    assert any(df.key.startswith("lf_tbl") for df in at.dataframe)  # every home, as a sortable table
    assert by_key(at.segmented_control, "lf_tier") is not None
    by_key(at.segmented_control, "lf_tier").set_value(1)
    run(at)

    at.session_state.lf_addr = 0  # an address picked in the table or on the map
    run(at)
    assert "Show every home" in {b.label for b in at.button}
    next(b for b in at.button if b.label == "Show every home").click()
    run(at)
    assert at.session_state.lf_addr is None

    assert {"tileb-lf_next-0", "tileb-lf_next-1", "tileb-lf_next-2"} <= keys(at)
    by_key(at.button, "tileb-lf_next-0").click()  # Start: the town plan
    run(at)
    assert at.session_state.role == "manager"


def test_whole_map():
    at = opening()
    by_key(at.segmented_control, "lf_flood").set_value(500)
    run(at)
    by_key(at.selectbox, "lf_town").set_value("Whole map · every town")
    run(at)
    assert any(df.key == "lf_all" for df in at.dataframe)


def test_flood_change_keeps_a_town_in_the_new_zone():
    at = opening()
    by_key(at.segmented_control, "lf_flood").set_value(500)
    run(at)
    town = by_key(at.selectbox, "lf_town")
    town.set_value(town.options[1])
    run(at)
    by_key(at.segmented_control, "lf_flood").set_value(10)
    run(at)  # the town may not be in the 10-year zone: the picker resets rather than failing


@pytest.mark.parametrize("role,page", [
    ("manager", "views/crisis.py"), ("manager", "views/evacuate.py"), ("manager", "views/checkin.py"),
    ("manager", "views/then_now.py"), ("manager", "views/limits.py"),
    ("brigade", "views/checkin.py"), ("brigade", "views/evacuate.py"), ("resident", "views/resident.py")])
def test_role_pages_render_with_their_next_steps(role, page):
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state.role = role
    run(at)
    at.switch_page(page)
    run(at)
    restart = [b for b in at.button if b.key and b.key.startswith("restart-")]
    if page in ("views/crisis.py", "views/evacuate.py", "views/checkin.py"):
        assert restart, "the desk's flow pages end in next steps and a way back"
        restart[0].click()
        run(at)
        assert at.session_state.get("role") is None  # back on the opening page
