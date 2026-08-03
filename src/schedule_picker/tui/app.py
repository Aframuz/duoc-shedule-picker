"""The full-screen picker."""

from __future__ import annotations

from datetime import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
)

from ..domain.catalog import Catalog
from ..domain.day import Day
from ..domain.level import LevelConflict
from ..parsing import LoadReport
from ..rendering import RENDERERS, TextRenderer
from ..solving import SCORERS
from .state import PickerState

PICKABLE_DAYS = (Day.LUNES, Day.MARTES, Day.MIERCOLES, Day.JUEVES, Day.VIERNES, Day.SABADO)


class CatalogScreen(Screen):
    """Pick the courses to schedule."""

    BINDINGS = [
        Binding("space,enter", "toggle", "Marcar/desmarcar"),
        Binding("f", "focus_search", "Buscar"),
        Binding("a", "select_all", "Todos"),
        Binding("n", "select_none", "Ninguno"),
        Binding("m", "only_mandatory", "Solo obligatorios"),
        Binding("plus,equals_sign", "more_electives", "+1 optativo"),
        Binding("minus", "fewer_electives", "-1 optativo"),
        Binding("i", "show_report", "Cuantos caben"),
        Binding("c", "app.push_screen('constraints')", "Restricciones"),
        Binding("g", "generate", "Generar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Buscar por sigla o nombre...", id="search")
        yield DataTable(id="courses", cursor_type="row", zebra_stripes=True)
        yield Static(id="catalog-status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#courses", DataTable)
        table.add_columns(" ", "Sigla", "Tipo", "Secciones", "Asignatura")
        self.refresh_rows()
        table.focus()

    @property
    def state(self) -> PickerState:
        return self.app.state

    def refresh_rows(self, needle: str = "") -> None:
        table = self.query_one("#courses", DataTable)
        table.clear()
        for course in self.state.catalog.search(needle):
            if course.sigla in self.state.selected:
                mark, kind = "[b]x[/b]", "obligatorio"
            elif course.sigla in self.state.wanted:
                mark, kind = "[b]+[/b]", "optativo fijo"
            else:
                mark = " "
                kind = "optativo" if course.is_elective else f"nivel {course.level}"
            table.add_row(
                mark, course.sigla, kind, str(len(course)), course.name, key=course.sigla
            )
        self.update_status()

    def update_status(self) -> None:
        state = self.state
        bits = [f"{len(state.selected)} obligatorio(s)"]
        if state.wanted:
            bits.append(f"{len(state.wanted)} optativo(s) fijo(s)")
        bits.append(f"+{state.extra_electives} optativo(s) libres")
        self.query_one("#catalog-status", Static).update(
            " · ".join(bits) + " — [b]+/-[/b] optativos, [b]i[/b] cuantos caben, [b]g[/b] genera"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.refresh_rows(event.value)

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_toggle(self) -> None:
        table = self.query_one("#courses", DataTable)
        if table.row_count == 0:
            return
        sigla = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        if sigla:
            course = self.state.catalog.course(sigla)
            # Electives become "I want this one specifically"; anything else is
            # just added to or removed from the compulsory set.
            if course.is_elective and sigla not in self.state.selected:
                self.state.toggle_wanted(sigla)
                if len(self.state.wanted) > self.state.electives_wanted:
                    self.state.electives_wanted = len(self.state.wanted)
            else:
                self.state.toggle(sigla)
            row = table.cursor_row
            self.refresh_rows(self.query_one("#search", Input).value)
            table.move_cursor(row=min(row, table.row_count - 1))

    def action_select_all(self) -> None:
        self.state.selected = {c.sigla for c in self.state.catalog}
        self.refresh_rows(self.query_one("#search", Input).value)

    def action_select_none(self) -> None:
        self.state.selected.clear()
        self.state.wanted.clear()
        self.refresh_rows(self.query_one("#search", Input).value)

    def action_only_mandatory(self) -> None:
        """Back to the default: this level's compulsory courses, nothing else."""
        try:
            self.state.selected = {c.sigla for c in self.state.catalog.mandatory()}
        except LevelConflict as exc:
            self.notify(str(exc), severity="warning")
            return
        self.state.wanted.clear()
        self.state.electives_wanted = 0
        self.refresh_rows(self.query_one("#search", Input).value)

    def action_more_electives(self) -> None:
        if self.state.electives_wanted < len(self.state.catalog.electives()):
            self.state.electives_wanted += 1
            self.update_status()

    def action_fewer_electives(self) -> None:
        if self.state.electives_wanted > len(self.state.wanted):
            self.state.electives_wanted -= 1
            self.update_status()

    def action_show_report(self) -> None:
        self.app.push_screen("report")

    def action_generate(self) -> None:
        self.app.generate()


class ConstraintsScreen(Screen):
    """Narrow the search."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("g", "generate", "Generar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("Dias libres")
            with Horizontal(id="days"):
                for day in PICKABLE_DAYS:
                    yield Checkbox(day.label, id=f"day-{day.name}")

            yield Label("Horas")
            with Horizontal(id="hours"):
                yield Input(placeholder="Desde HH:MM", id="earliest")
                yield Input(placeholder="Hasta HH:MM", id="latest")

            yield Label("Maximo de dias (vacio = sin limite)")
            yield Input(placeholder="ej. 3", id="max-days")

            yield Label("Modalidad")
            yield Checkbox("Solo online", id="online-only")
            yield Checkbox("Solo presencial", id="onsite-only")

            yield Label("Ordenar por")
            yield Select(
                [(name, name) for name in sorted(SCORERS)],
                value="balanced",
                id="sort",
                allow_blank=False,
            )

            yield Label("Excluir docentes")
            yield ListView(id="teachers")
        yield Static(id="constraint-status")
        yield Footer()

    def on_mount(self) -> None:
        teachers = self.query_one("#teachers", ListView)
        for name in self.app.state.catalog.teachers():
            teachers.append(ListItem(Label(name), name=name))
        self._status("Espacio marca un docente para excluirlo.")

    def _status(self, message: str) -> None:
        self.query_one("#constraint-status", Static).update(message)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        state = self.app.state
        widget_id = event.checkbox.id or ""
        if widget_id.startswith("day-"):
            day = Day[widget_id.removeprefix("day-")]
            if event.value:
                state.free_days.add(day)
            else:
                state.free_days.discard(day)
        elif widget_id == "online-only":
            state.online_only = event.value
            if event.value:
                state.onsite_only = False
                self.query_one("#onsite-only", Checkbox).value = False
        elif widget_id == "onsite-only":
            state.onsite_only = event.value
            if event.value:
                state.online_only = False
                self.query_one("#online-only", Checkbox).value = False

    def on_input_changed(self, event: Input.Changed) -> None:
        state = self.app.state
        value = event.value.strip()
        try:
            if event.input.id == "earliest":
                state.earliest = _parse_time(value)
            elif event.input.id == "latest":
                state.latest = _parse_time(value)
            elif event.input.id == "max-days":
                state.max_days = int(value) if value else None
        except ValueError:
            self._status(f"No entiendo {value!r}")
            return
        self._status("")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sort" and event.value:
            self.app.state.sort = str(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        name = event.item.name
        if not name:
            return
        state = self.app.state
        if name in state.excluded_teachers:
            state.excluded_teachers.discard(name)
            event.item.query_one(Label).update(name)
        else:
            state.excluded_teachers.add(name)
            event.item.query_one(Label).update(f"[strike]{name}[/strike]")

    def action_generate(self) -> None:
        self.app.generate()


class ReportScreen(Screen):
    """How many timetables fit 0, 1, 2, ... electives."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("g", "generate", "Generar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(id="report")
        yield Static(id="report-status")
        yield Footer()

    def on_mount(self) -> None:
        state = self.app.state
        pool = state.elective_pool
        if not pool:
            self.query_one("#report", Static).update("Este archivo no tiene optativos.")
            return

        required = ", ".join(c.sigla for c in state.courses) or "(ninguno)"
        lines = [
            f"Obligatorios: {required}",
            f"Optativos disponibles: {len(pool)}",
            "",
        ]
        tallies = state.report()
        for tally in tallies:
            taken = tally.count + len(state.wanted)
            if tally.schedules:
                lines.append(
                    f"  {taken} optativo(s): {tally.schedules} horario(s) "
                    f"en {tally.combinations} combinacion(es) de ramos"
                )
            else:
                lines.append(f"  {taken} optativo(s): no cabe ninguno")

        fits = [t.count for t in tallies if t.schedules]
        lines.append("")
        if fits:
            best = max(fits) + len(state.wanted)
            lines.append(f"Maximo que cabe: {best} optativo(s)")
            self.query_one("#report-status", Static).update(
                "[b]+/-[/b] en la lista ajusta cuantos quieres · [b]g[/b] genera"
            )
        else:
            lines.append("Ni siquiera los obligatorios caben juntos.")

        self.query_one("#report", Static).update("\n".join(lines))

    def action_generate(self) -> None:
        self.app.generate()


class ResultsScreen(Screen):
    """Browse and export the timetables."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("e", "export", "Exportar"),
        Binding("r", "regenerate", "Recalcular"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="results-status")
        with Horizontal():
            with Vertical(id="options"):
                yield ListView(id="option-list")
            with VerticalScroll(id="preview-pane"):
                yield Static(id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_results()

    def refresh_results(self) -> None:
        state = self.app.state
        self.query_one("#results-status", Static).update(state.summary())

        options = self.query_one("#option-list", ListView)
        options.clear()
        for index, candidate in enumerate(state.candidates, start=1):
            bits = [f"{len(candidate.days_used)}d", f"{candidate.idle_minutes}min"]
            if candidate.electives:
                bits.append(f"{len(candidate.electives)}opt")
            if candidate.total_credits:
                bits.append(f"{candidate.total_credits}cr")
            options.append(
                ListItem(Label(f"{index:>3}. " + " · ".join(bits)), name=str(index - 1))
            )

        if state.candidates:
            options.index = 0
            self.show(0)
        else:
            self.query_one("#preview", Static).update(state.error or "")

    def show(self, index: int) -> None:
        state = self.app.state
        if not (0 <= index < len(state.candidates)):
            return
        rendered = TextRenderer(show_legend=True).render(state.candidates[index])
        self.query_one("#preview", Static).update(rendered)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and event.item.name is not None:
            self.show(int(event.item.name))

    def action_regenerate(self) -> None:
        self.app.state.solve()
        self.refresh_results()

    def action_export(self) -> None:
        state = self.app.state
        if not state.candidates:
            self.notify("No hay nada que exportar.", severity="warning")
            return

        out = Path("output")
        out.mkdir(parents=True, exist_ok=True)
        stem = state.catalog.source.stem if state.catalog.source else "horarios"

        written = []
        for factory in RENDERERS.values():
            renderer = factory()
            target = out / f"{stem}.{renderer.extension}"
            target.write_text(
                renderer.render_all(state.candidates, state.scores), encoding="utf-8"
            )
            written.append(target.name)
        self.notify(f"Exportado a output/: {', '.join(sorted(written))}")


class SchedulePickerApp(App):
    """Pick courses, set constraints, browse the timetables that fit."""

    TITLE = "schedule-picker"
    CSS = """
    Screen { layout: vertical; }
    #courses { height: 1fr; }
    #catalog-status, #results-status, #constraint-status {
        dock: bottom; padding: 0 1; color: $text-muted;
    }
    #options { width: 32; border-right: solid $panel; }
    #preview-pane { width: 1fr; padding: 0 1; }
    #preview { width: auto; }
    /* Rows of controls size to their contents; without this they collapse. */
    #days, #hours { height: auto; }
    #hours Input { width: 1fr; }
    Label { padding: 1 1 0 1; }
    Checkbox { border: none; }
    ListView { height: 1fr; }
    #teachers { height: 12; border: solid $panel; }
    """
    SCREENS = {
        "catalog": CatalogScreen,
        "constraints": ConstraintsScreen,
        "report": ReportScreen,
        "results": ResultsScreen,
    }
    BINDINGS = [Binding("q,ctrl+c", "quit", "Salir")]

    def __init__(self, catalog: Catalog, report: LoadReport | None = None) -> None:
        super().__init__()
        self.state = PickerState(catalog=catalog)
        self.report = report

    def on_mount(self) -> None:
        self.push_screen("catalog")
        if self.report and self.report.errors:
            self.notify(
                f"{len(self.report.errors)} fila(s) ilegibles fueron omitidas.",
                severity="warning",
            )

    def generate(self) -> None:
        """Solve, then show the results screen."""
        self.state.solve()
        if isinstance(self.screen, ResultsScreen):
            self.screen.refresh_results()
        else:
            self.push_screen("results")


def _parse_time(value: str) -> time | None:
    if not value:
        return None
    parts = value.split(":")
    return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
