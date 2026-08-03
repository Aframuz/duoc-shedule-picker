"""Turning timetables into something a person (or a spreadsheet) can read."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from ..domain.candidate import ScheduleCandidate
from .data import CsvRenderer, JsonRenderer
from .grid import Grid, GridRow, build_grid, legend
from .html import HtmlRenderer
from .text import TextRenderer


@runtime_checkable
class Renderer(Protocol):
    """Renders timetables. ``extension`` names the file suffix to write."""

    extension: str

    def render_all(
        self,
        candidates: Sequence[ScheduleCandidate] | Iterable[ScheduleCandidate],
        scores: Sequence[float] | None = None,
    ) -> str: ...


#: Selectable by name from ``--format`` and the TUI's export buttons.
RENDERERS: dict[str, type] = {
    "text": TextRenderer,
    "html": HtmlRenderer,
    "csv": CsvRenderer,
    "json": JsonRenderer,
}

__all__ = [
    "RENDERERS",
    "CsvRenderer",
    "Grid",
    "GridRow",
    "HtmlRenderer",
    "JsonRenderer",
    "Renderer",
    "TextRenderer",
    "build_grid",
    "legend",
]
