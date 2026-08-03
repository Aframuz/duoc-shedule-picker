"""The picker, driven headlessly through Textual's test pilot."""

from __future__ import annotations

from datetime import time

import pytest

from schedule_picker.domain import Day
from schedule_picker.parsing import load_catalog
from schedule_picker.tui.app import CatalogScreen, ResultsScreen, SchedulePickerApp
from schedule_picker.tui.state import RESULT_CAP, PickerState

from ..conftest import DATASETS

# asyncio_mode = "auto" in pyproject runs the async tests; the sync ones below
# exercise PickerState directly, with no terminal involved.


@pytest.fixture
def app(catalogs):
    catalog, report = load_catalog(DATASETS["6to"])
    return SchedulePickerApp(catalog=catalog, report=report)


# --------------------------------------------------------------------------
# State — the logic, without a terminal
# --------------------------------------------------------------------------


def test_state_preselects_the_mandatory_courses(catalogs):
    """The common case is "my compulsory courses, plus maybe an elective"."""
    state = PickerState(catalog=catalogs["6to"])
    assert state.selected == {"DAY1102", "IDY1102", "IDY1103"}
    assert state.wanted == set()
    assert state.electives_wanted == 0


@pytest.mark.parametrize("name", ["2do", "3er", "4to"])
def test_state_preselects_everything_when_there_are_no_electives(name, catalogs):
    state = PickerState(catalog=catalogs[name])
    assert state.selected == {c.sigla for c in catalogs[name]}


def test_state_requires_a_selection(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.selected.clear()
    state.solve()
    assert state.candidates == []
    assert "al menos un ramo" in state.error


def test_state_solves_a_selection(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.selected = {"OCY1101", "OCY1102", "DLY0100"}
    state.electives_wanted = 0
    state.solve()
    assert state.candidates
    assert state.error is None
    assert len(state.scores) == len(state.candidates)
    assert state.scores == sorted(state.scores), "ranked best first"


def test_state_explains_an_impossible_pair(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.selected = {"BCY0010", "BCY0011"}
    state.solve()
    assert not state.candidates
    assert "chocan" in state.error


def test_state_reports_an_over_tight_constraint(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.selected = {"OCY1101", "OCY1102"}
    state.latest = time(0, 1)
    state.solve()
    assert not state.candidates
    assert "no sections of" in state.error


def test_state_caps_the_result_list(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.selected = {"OCY1101", "OCY1104", "OCY1105", "DLY0100", "MLY0100"}
    state.solve()
    assert len(state.candidates) <= RESULT_CAP
    if state.truncated:
        assert f"primeras {RESULT_CAP}" in state.summary()


def test_state_free_day_flows_into_the_filters(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.selected = {"OCY1101", "DLY0100"}
    state.toggle_day(Day.SABADO)
    state.solve()
    assert state.candidates
    for candidate in state.candidates:
        assert Day.SABADO not in candidate.days_used


def test_state_toggle_is_idempotent_in_pairs(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.selected.clear()
    state.toggle("OCY1101")
    assert state.selected == {"OCY1101"}
    state.toggle("OCY1101")
    assert state.selected == set()


def test_state_elective_report_matches_the_solver(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    tallies = state.report()
    assert [(t.count, t.schedules) for t in tallies] == [
        (0, 1), (1, 31), (2, 196), (3, 0)
    ]


def test_state_takes_extra_electives(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.electives_wanted = 2
    state.solve()
    assert state.error is None
    assert len(state.candidates) == 196
    for candidate in state.candidates:
        assert len(candidate.electives) == 2


def test_state_honours_a_wanted_elective(catalogs):
    """"I want OCY1104 and one more, whatever fits"."""
    state = PickerState(catalog=catalogs["6to"])
    state.toggle_wanted("OCY1104")
    state.electives_wanted = 2
    state.solve()
    assert state.error is None
    assert len(state.candidates) == 37
    for candidate in state.candidates:
        assert "OCY1104" in {s.sigla for s in candidate.electives}
        assert len(candidate.electives) == 2


def test_state_reports_when_too_many_electives_are_asked_for(catalogs):
    state = PickerState(catalog=catalogs["6to"])
    state.electives_wanted = 3
    state.solve()
    assert not state.candidates
    assert "El maximo que cabe es 2" in state.error


def test_state_credits_flow_into_candidates(catalogs):
    state = PickerState(catalog=catalogs["6to"].with_credits({"OCY1104": 8}))
    state.toggle_wanted("OCY1104")
    state.electives_wanted = 1
    state.solve()
    assert state.candidates
    assert all(c.total_credits == 8 for c in state.candidates)


# --------------------------------------------------------------------------
# The app itself
# --------------------------------------------------------------------------


async def test_starts_on_the_catalog_screen(app):
    async with app.run_test() as pilot:
        assert isinstance(pilot.app.screen, CatalogScreen)
        table = pilot.app.screen.query_one("#courses")
        assert table.row_count == 21


async def test_search_filters_the_table(app):
    async with app.run_test() as pilot:
        search = pilot.app.screen.query_one("#search")
        search.value = "CIBERSEGURIDAD"
        await pilot.pause()
        table = pilot.app.screen.query_one("#courses")
        assert 0 < table.row_count < 21


async def test_select_all_then_none(app):
    async with app.run_test() as pilot:
        await pilot.press("a")
        assert len(pilot.app.state.selected) == 21
        await pilot.press("n")
        assert pilot.app.state.selected == set()


async def test_toggling_an_elective_row_marks_it_wanted(app):
    """The first row is BCY0010, an elective — ticking it means "I want this one"."""
    async with app.run_test() as pilot:
        screen = pilot.app.screen
        screen.query_one("#courses").focus()
        await pilot.pause()
        await pilot.press("space")
        assert pilot.app.state.wanted == {"BCY0010"}
        assert pilot.app.state.electives_wanted == 1


async def test_elective_count_keys(app):
    async with app.run_test() as pilot:
        await pilot.press("plus")
        await pilot.press("plus")
        assert pilot.app.state.electives_wanted == 2
        await pilot.press("minus")
        assert pilot.app.state.electives_wanted == 1


async def test_only_mandatory_resets_the_selection(app):
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.press("m")
        assert pilot.app.state.selected == {"DAY1102", "IDY1102", "IDY1103"}
        assert pilot.app.state.wanted == set()
        assert pilot.app.state.electives_wanted == 0


async def test_report_screen_lists_the_tallies(app):
    async with app.run_test() as pilot:
        await pilot.press("i")
        await pilot.pause()
        text = str(pilot.app.screen.query_one("#report").content)
        assert "Maximo que cabe: 2 optativo(s)" in text
        assert "1 optativo(s): 31 horario(s)" in text


async def test_generate_shows_results(app):
    async with app.run_test() as pilot:
        pilot.app.state.selected = {"OCY1101", "OCY1102", "DLY0100"}
        pilot.app.generate()
        await pilot.pause()
        assert isinstance(pilot.app.screen, ResultsScreen)
        assert pilot.app.state.candidates
        preview = pilot.app.screen.query_one("#preview").content
        assert "Horario" in str(preview)


async def test_results_screen_reports_an_empty_search(app):
    async with app.run_test() as pilot:
        pilot.app.state.selected = {"BCY0010", "BCY0011"}
        pilot.app.generate()
        await pilot.pause()
        assert isinstance(pilot.app.screen, ResultsScreen)
        assert "chocan" in str(pilot.app.screen.query_one("#preview").content)


async def test_export_writes_every_format(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async with app.run_test() as pilot:
        pilot.app.state.selected = {"OCY1101", "DLY0100"}
        pilot.app.generate()
        await pilot.pause()
        pilot.app.screen.action_export()
        await pilot.pause()

    written = sorted(p.name for p in (tmp_path / "output").iterdir())
    assert written == [
        "6to_semestre.csv", "6to_semestre.html", "6to_semestre.json", "6to_semestre.txt"
    ]


async def test_constraints_screen_binds_to_state(app):
    async with app.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()
        screen = pilot.app.screen

        screen.query_one("#day-SABADO").value = True
        await pilot.pause()
        assert Day.SABADO in pilot.app.state.free_days

        screen.query_one("#max-days").value = "3"
        await pilot.pause()
        assert pilot.app.state.max_days == 3

        screen.query_one("#online-only").value = True
        await pilot.pause()
        assert pilot.app.state.online_only is True


async def test_online_and_onsite_checkboxes_are_exclusive(app):
    async with app.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()
        screen = pilot.app.screen

        screen.query_one("#online-only").value = True
        await pilot.pause()
        screen.query_one("#onsite-only").value = True
        await pilot.pause()

        assert pilot.app.state.onsite_only is True
        assert pilot.app.state.online_only is False
        assert screen.query_one("#online-only").value is False


async def test_bad_time_input_does_not_crash(app):
    async with app.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()
        screen = pilot.app.screen
        screen.query_one("#earliest").value = "no"
        await pilot.pause()
        assert pilot.app.state.earliest is None
        assert "No entiendo" in str(screen.query_one("#constraint-status").content)
