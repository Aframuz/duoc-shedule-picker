"""Plain-text timetables, for the terminal and for ``.txt`` output."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from texttable import Texttable

from ..domain.candidate import ScheduleCandidate
from .grid import WEEKDAYS, WEEKEND, Grid, build_grid, legend

WIDTH = 80


@dataclass(frozen=True)
class TextRenderer:
    """Renders timetables as ASCII tables.

    Weekdays and the weekend get separate tables: weekday classes are all in the
    evening while Saturday runs from the morning, so one shared grid would be
    mostly empty rows.
    """

    extension = "txt"

    show_legend: bool = True
    width: int = WIDTH

    def render(self, candidate: ScheduleCandidate, title: str = "") -> str:
        parts: list[str] = []
        if title:
            parts.append(self._banner(title))
        summary = _summary(candidate)
        if summary:
            parts.append(summary)

        for days in (WEEKDAYS, WEEKEND):
            grid = build_grid(candidate, days)
            if grid:
                parts.append(_table(grid))

        if self.show_legend:
            parts.append(_legend_table(candidate))

        return "\n".join(parts)

    def render_all(
        self,
        candidates: Sequence[ScheduleCandidate] | Iterable[ScheduleCandidate],
        scores: Sequence[float] | None = None,
    ) -> str:
        chunks: list[str] = []
        for index, candidate in enumerate(candidates, start=1):
            title = f"OPCION {index}"
            if scores is not None and index <= len(scores):
                title = f"{title}  (puntaje {scores[index - 1]:g})"
            chunks.append(self.render(candidate, title))
        if not chunks:
            return "No hay horarios que cumplan las condiciones.\n"
        return "\n\n".join(chunks) + "\n"

    def _banner(self, title: str) -> str:
        rule = "*" * self.width
        return f"{rule}\n{title.center(self.width)}\n{rule}"


def _summary(candidate: ScheduleCandidate) -> str:
    """A one-line recap of what the timetable costs and is worth."""
    bits = [
        f"{len(candidate.days_used)} dias",
        f"{candidate.idle_minutes} min libres",
    ]
    if candidate.electives:
        bits.append(f"{len(candidate.electives)} optativo(s)")
    if candidate.total_credits:
        bits.append(f"{candidate.total_credits} creditos")
    return " | ".join(bits)


def _table(grid: Grid) -> str:
    table = Texttable(max_width=0)
    table.set_deco(Texttable.HEADER | Texttable.VLINES)
    table.set_cols_align(["l"] + ["c"] * len(grid.days))
    table.header(["Horario", *(day.label for day in grid.days)])

    for row in grid.rows:
        cells = [row.cells[day].label if row.cells[day] else "" for day in grid.days]
        table.add_row([row.label, *cells])

    return table.draw()


def _legend_table(candidate: ScheduleCandidate) -> str:
    table = Texttable(max_width=0)
    table.set_deco(Texttable.HEADER | Texttable.VLINES)
    table.set_cols_align(["l", "l", "l"])
    table.header(["Codigo", "Asignatura", "Docente"])
    for label, name, teacher in legend(candidate):
        table.add_row([label, name, teacher])
    return table.draw()
