"""Laying a timetable out on a grid.

Rows are derived from the timetable's own start and end times, not from a fixed
list of slots. The old implementation indexed into two hardcoded lists of
timestamps, which meant a new export with different hours (``8:01``, ``9:31``,
``16:01``) could not be drawn at all, and nested blocks such as ``10:01-11:20``
alongside ``10:01-10:40`` had nowhere to go.

Rows are half-open ``[start, end)``, matching :class:`TimeBlock`. The legacy
renderer shaded the row *labelled* with a block's end time, which is why a class
running 19:01-20:20 appeared to occupy three rows in the committed output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from ..domain.candidate import ScheduleCandidate
from ..domain.day import Day
from ..domain.section import Section

WEEKDAYS: tuple[Day, ...] = (Day.LUNES, Day.MARTES, Day.MIERCOLES, Day.JUEVES, Day.VIERNES)
WEEKEND: tuple[Day, ...] = (Day.SABADO, Day.DOMINGO)


@dataclass(frozen=True)
class GridRow:
    """One time band, and what occupies it on each day."""

    start: time
    end: time
    cells: dict[Day, Section | None]

    @property
    def label(self) -> str:
        return f"{self.start:%H:%M}-{self.end:%H:%M}"

    @property
    def is_empty(self) -> bool:
        return not any(self.cells.values())


@dataclass(frozen=True)
class Grid:
    """A timetable rendered as rows × days."""

    days: tuple[Day, ...]
    rows: tuple[GridRow, ...]

    def __bool__(self) -> bool:
        return bool(self.rows)

    @property
    def sections(self) -> list[Section]:
        """Sections appearing in this grid, ordered by sigla."""
        seen = {cell for row in self.rows for cell in row.cells.values() if cell}
        return sorted(seen, key=lambda s: s.code)


#: Boundaries closer together than this are treated as one. The exports end a
#: block one minute before the next begins (20:31-21:10, then 21:11-21:50), so
#: without snapping every such seam produces a one-minute sliver row.
SNAP_MINUTES = 2


def build_grid(
    candidate: ScheduleCandidate,
    days: tuple[Day, ...],
    *,
    drop_empty_rows: bool = True,
    snap_minutes: int = SNAP_MINUTES,
) -> Grid:
    """Lay ``candidate`` out over ``days``.

    Only the given days contribute boundaries, so drawing weekdays and the
    weekend separately keeps each table tight — Saturday classes start in the
    morning while weekday classes are all evening, and a shared grid would be
    mostly blank.

    Snapping affects presentation only. Conflict detection works on the exact
    times, so a cosmetic merge here can never make a clashing timetable look
    valid.
    """
    present = tuple(day for day in days if day in candidate.blocks_by_day)
    if not present:
        return Grid(days=(), rows=())

    moments = sorted(
        {
            moment
            for day in present
            for block, _ in candidate.blocks_by_day[day]
            for moment in (block.start, block.end)
        }
    )
    boundaries = _snap(moments, snap_minutes)

    rows: list[GridRow] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        cells: dict[Day, Section | None] = {
            day: _occupant(candidate, day, start, end) for day in present
        }
        row = GridRow(start=start, end=end, cells=cells)
        if drop_empty_rows and row.is_empty:
            continue
        rows.append(row)

    return Grid(days=present, rows=tuple(rows))


def _snap(moments: list[time], tolerance: int) -> list[time]:
    """Drop boundaries within ``tolerance`` minutes of the previous one kept."""
    kept: list[time] = []
    for moment in moments:
        if kept and _minutes(moment) - _minutes(kept[-1]) < tolerance:
            continue
        kept.append(moment)
    return kept


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _occupant(
    candidate: ScheduleCandidate,
    day: Day,
    start: time,
    end: time,
) -> Section | None:
    """The section covering the band ``[start, end)`` on ``day``.

    Decided by the band's midpoint rather than its edges: snapping can nudge a
    boundary by a minute, and a midpoint stays comfortably inside the block it
    belongs to. Within one timetable a band has at most one occupant, since
    overlapping sections are exactly what the solver rules out.
    """
    middle = (_minutes(start) + _minutes(end)) // 2
    for block, section in candidate.blocks_by_day.get(day, ()):
        if _minutes(block.start) <= middle < _minutes(block.end):
            return section
    return None


def legend(candidate: ScheduleCandidate) -> list[tuple[str, str, str]]:
    """``(label, full course name, teacher)`` per section, for a key beneath the grid.

    Needed because cells carry only ``SIGLA 003V``: the export truncates course
    names at 40 characters, so the sigla is the only reliable identifier, and it
    is not self-explanatory.
    """
    return [
        (section.label, section.course_name, section.teacher or "—")
        for section in sorted(candidate.sections, key=lambda s: s.code)
    ]
