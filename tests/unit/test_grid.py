from __future__ import annotations

from schedule_picker.domain import Day, ScheduleCandidate
from schedule_picker.rendering.grid import WEEKDAYS, WEEKEND, build_grid, legend

from ..conftest import block, section


def candidate(*sections) -> ScheduleCandidate:
    return ScheduleCandidate(sections=tuple(sections))


def test_rows_come_from_the_data_not_a_fixed_slot_list():
    """Times absent from the old hardcoded lists render fine."""
    c = candidate(
        section("ABC1234-001V", block(Day.SABADO, "8:01", "9:20")),
        section("XYZ9999-001V", block(Day.SABADO, "16:01", "17:20")),
    )
    grid = build_grid(c, WEEKEND)
    assert [row.label for row in grid.rows] == ["08:01-09:20", "16:01-17:20"]


def test_a_block_occupies_exactly_its_own_span():
    """19:01-20:20 is one band, not three.

    The legacy renderer shaded the row labelled with the end time as well, which
    is why its committed output showed this class filling three rows.
    """
    c = candidate(section("ABC1234-001V", block(Day.LUNES, "19:01", "20:20")))
    grid = build_grid(c, WEEKDAYS)
    assert len(grid.rows) == 1
    assert grid.rows[0].label == "19:01-20:20"
    assert grid.rows[0].cells[Day.LUNES].code == "ABC1234-001V"


def test_one_minute_seams_do_not_create_sliver_rows():
    """The export ends a block a minute before the next starts."""
    c = candidate(
        section("AAA1111-001V", block(Day.LUNES, "20:31", "21:10")),
        section("BBB2222-001V", block(Day.LUNES, "21:11", "21:50")),
    )
    grid = build_grid(c, WEEKDAYS)
    assert len(grid.rows) == 2, [r.label for r in grid.rows]
    assert grid.rows[0].cells[Day.LUNES].code == "AAA1111-001V"
    assert grid.rows[1].cells[Day.LUNES].code == "BBB2222-001V"


def test_days_without_classes_are_left_out():
    c = candidate(section("ABC1234-001V", block(Day.LUNES, "19:01", "20:20")))
    grid = build_grid(c, WEEKDAYS)
    assert grid.days == (Day.LUNES,)


def test_weekend_grid_is_separate_from_the_weekday_grid():
    c = candidate(
        section(
            "ABC1234-001V",
            block(Day.LUNES, "19:01", "20:20"),
            block(Day.SABADO, "8:31", "9:50"),
        )
    )
    weekday = build_grid(c, WEEKDAYS)
    weekend = build_grid(c, WEEKEND)
    # A shared grid would give the weekday table a blank 08:31 row.
    assert [r.label for r in weekday.rows] == ["19:01-20:20"]
    assert [r.label for r in weekend.rows] == ["08:31-09:50"]


def test_empty_grid_when_no_class_falls_on_those_days():
    c = candidate(section("ABC1234-001V", block(Day.SABADO, "8:31", "9:50")))
    assert not build_grid(c, WEEKDAYS)


def test_gap_rows_are_dropped_but_boundaries_stay_honest():
    c = candidate(
        section(
            "ABC1234-001V",
            block(Day.LUNES, "19:01", "20:20"),
            block(Day.LUNES, "21:11", "22:30"),
        )
    )
    grid = build_grid(c, WEEKDAYS)
    assert [r.label for r in grid.rows] == ["19:01-20:20", "21:11-22:30"]


def test_two_courses_share_one_band_on_different_days():
    c = candidate(
        section("AAA1111-001V", block(Day.LUNES, "19:01", "20:20")),
        section("BBB2222-001V", block(Day.MARTES, "19:01", "20:20")),
    )
    grid = build_grid(c, WEEKDAYS)
    assert len(grid.rows) == 1
    row = grid.rows[0]
    assert row.cells[Day.LUNES].code == "AAA1111-001V"
    assert row.cells[Day.MARTES].code == "BBB2222-001V"


def test_legend_carries_the_untruncated_name_and_teacher():
    c = candidate(
        section(
            "JVY0101-011V",
            block(Day.LUNES, "19:01", "20:20"),
            name="JAVA: DIS y CONST. DE SOL. NATIVAS EN NU",
            teacher="ALGUIEN",
        )
    )
    assert legend(c) == [
        ("JVY0101 011V", "JAVA: DIS y CONST. DE SOL. NATIVAS EN NU", "ALGUIEN")
    ]


def test_legend_marks_a_missing_teacher():
    c = candidate(section("ABC1234-001V", block(Day.LUNES, "19:01", "20:20")))
    assert legend(c)[0][2] == "—"
