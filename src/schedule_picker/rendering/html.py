"""A self-contained HTML page of timetables.

One file, no external assets — it has to survive being emailed to a classmate.
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..domain.candidate import ScheduleCandidate
from .grid import WEEKDAYS, WEEKEND, Grid, build_grid, legend

_STYLE = """
:root {
  --bg: #ffffff; --fg: #16181d; --muted: #5c6370;
  --line: #d8dce3; --head: #f4f6f9; --card: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14161a; --fg: #e6e8ec; --muted: #9aa1ac;
    --line: #2c3138; --head: #1c1f25; --card: #191c21;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1rem 4rem;
  background: var(--bg); color: var(--fg);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 60rem; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
.sub { color: var(--muted); margin: 0 0 2rem; }
.option {
  background: var(--card); border: 1px solid var(--line);
  border-radius: 10px; padding: 1.25rem; margin-bottom: 1.5rem;
}
.option > h2 { font-size: 1.05rem; margin: 0 0 .15rem; }
.meta { color: var(--muted); font-size: .85rem; margin: 0 0 1rem; }
.scroll { overflow-x: auto; margin-bottom: 1rem; }
table { border-collapse: collapse; width: 100%; min-width: 34rem; }
th, td {
  border: 1px solid var(--line); padding: .4rem .5rem;
  text-align: center; font-size: .82rem; vertical-align: middle;
}
th { background: var(--head); font-weight: 600; }
td.time, th.time { text-align: left; white-space: nowrap; color: var(--muted);
  font-variant-numeric: tabular-nums; font-size: .78rem; }
td.busy { font-weight: 600; color: #10131a; }
table.legend td, table.legend th { text-align: left; }
table.legend { min-width: 0; }
.chip {
  display: inline-block; width: .7rem; height: .7rem;
  border-radius: 3px; margin-right: .5rem; vertical-align: -1px;
}
.empty { color: var(--muted); font-style: italic; }
@media print {
  body { background: #fff; color: #000; padding: 0; }
  .option { break-inside: avoid; border-color: #999; }
}
"""


def _colour(sigla: str) -> str:
    """A stable pastel per course, derived from its sigla.

    Deterministic so the same course keeps its colour across runs and files.
    """
    hue = (sum(ord(c) * (i + 7) for i, c in enumerate(sigla)) * 47) % 360
    return f"hsl({hue} 70% 78%)"


@dataclass(frozen=True)
class HtmlRenderer:
    """Renders a set of timetables as one standalone HTML document."""

    extension = "html"

    title: str = "Horarios posibles"
    subtitle: str = ""

    def render_all(
        self,
        candidates: Sequence[ScheduleCandidate] | Iterable[ScheduleCandidate],
        scores: Sequence[float] | None = None,
    ) -> str:
        options = list(candidates)
        body = [
            f"<h1>{html.escape(self.title)}</h1>",
            f'<p class="sub">{html.escape(self.subtitle or _default_subtitle(options))}</p>',
        ]

        if not options:
            body.append('<p class="empty">No hay horarios que cumplan las condiciones.</p>')

        for index, candidate in enumerate(options, start=1):
            score = scores[index - 1] if scores is not None and index <= len(scores) else None
            body.append(_option(candidate, index, score))

        return _document(self.title, "\n".join(body))

    def render(self, candidate: ScheduleCandidate, title: str = "") -> str:
        return self.render_all([candidate])


def _default_subtitle(options: list[ScheduleCandidate]) -> str:
    if not options:
        return "Sin resultados"
    plural = "opcion" if len(options) == 1 else "opciones"
    return f"{len(options)} {plural}"


def _document(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n<main>\n{body}\n</main>\n</body>\n</html>\n"
    )


def _option(candidate: ScheduleCandidate, index: int, score: float | None) -> str:
    heading = f"Opcion {index}"
    meta = [
        f"{len(candidate.days_used)} dias",
        f"{candidate.idle_minutes} min libres entre clases",
    ]
    if candidate.electives:
        meta.append(f"{len(candidate.electives)} optativo(s)")
    if candidate.total_credits:
        meta.append(f"{candidate.total_credits} creditos")
    if score is not None:
        meta.append(f"puntaje {score:g}")

    tables = []
    for days in (WEEKDAYS, WEEKEND):
        grid = build_grid(candidate, days)
        if grid:
            tables.append(f'<div class="scroll">{_table(grid)}</div>')

    return (
        '<section class="option">\n'
        f"<h2>{heading}</h2>\n"
        f'<p class="meta">{html.escape(" · ".join(meta))}</p>\n'
        + "\n".join(tables)
        + f"\n{_legend(candidate)}\n</section>"
    )


def _table(grid: Grid) -> str:
    head = "".join(f"<th>{html.escape(day.label)}</th>" for day in grid.days)
    rows = []
    for row in grid.rows:
        cells = []
        for day in grid.days:
            section = row.cells[day]
            if section is None:
                cells.append("<td></td>")
            else:
                style = f"background:{_colour(section.sigla)}"
                cells.append(
                    f'<td class="busy" style="{style}">{html.escape(section.label)}</td>'
                )
        rows.append(
            f'<tr><td class="time">{html.escape(row.label)}</td>{"".join(cells)}</tr>'
        )
    return (
        "<table>\n<thead><tr>"
        f'<th class="time">Horario</th>{head}</tr></thead>\n'
        f'<tbody>{"".join(rows)}</tbody>\n</table>'
    )


def _legend(candidate: ScheduleCandidate) -> str:
    rows = []
    for label, name, teacher in legend(candidate):
        sigla = label.split(" ", 1)[0]
        chip = f'<span class="chip" style="background:{_colour(sigla)}"></span>'
        rows.append(
            f"<tr><td>{chip}{html.escape(label)}</td>"
            f"<td>{html.escape(name)}</td><td>{html.escape(teacher)}</td></tr>"
        )
    return (
        '<table class="legend">\n<thead><tr><th>Codigo</th><th>Asignatura</th>'
        "<th>Docente</th></tr></thead>\n"
        f'<tbody>{"".join(rows)}</tbody>\n</table>'
    )
