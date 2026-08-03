"""The picker's mutable state, kept out of the widgets.

Holding the selection and constraints here means the solving logic is testable
without driving a terminal, and the screens stay presentation-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

from ..domain.candidate import ScheduleCandidate
from ..domain.catalog import Catalog
from ..domain.course import Course
from ..domain.day import Day
from ..domain.level import LevelConflict
from ..solving import (
    SCORERS,
    EarliestStart,
    ElectiveTally,
    ExcludeTeacher,
    FreeDay,
    LatestEnd,
    MaxDays,
    ModalityIs,
    Scorer,
    Unsatisfiable,
    elective_report,
    find_blocking_pair,
    iter_candidates,
    ranked,
)

#: Beyond this the list view stops being useful and the solve stops being instant.
RESULT_CAP = 500


@dataclass
class PickerState:
    """What the user has chosen so far, and what falls out of it."""

    catalog: Catalog
    #: Compulsory courses. Pre-filled from the file, but the user may change it.
    selected: set[str] = field(default_factory=set)
    #: Electives the user insists on; they count toward ``electives_wanted``.
    wanted: set[str] = field(default_factory=set)
    #: How many electives to add on top. ``0`` means mandatory courses only.
    electives_wanted: int = 0
    excluded_teachers: set[str] = field(default_factory=set)
    free_days: set[Day] = field(default_factory=set)
    earliest: time | None = None
    latest: time | None = None
    max_days: int | None = None
    online_only: bool = False
    onsite_only: bool = False
    sort: str = "balanced"

    # Filled by solve()
    candidates: list[ScheduleCandidate] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    truncated: bool = False
    error: str | None = None
    tallies: list[ElectiveTally] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Start with the compulsory courses ticked — that is the common case."""
        if self.selected:
            return
        try:
            self.selected = {course.sigla for course in self.catalog.mandatory()}
        except LevelConflict:
            # Several semesters in one file; make the user choose rather than
            # guessing which one they are in.
            self.selected = set()

    @property
    def courses(self) -> list[Course]:
        """Everything that must appear: the ticked courses plus wanted electives."""
        siglas = sorted(self.selected | self.wanted)
        return [self.catalog.courses[s] for s in siglas]

    @property
    def elective_pool(self) -> list[Course]:
        """Electives still up for grabs, i.e. not already required."""
        taken = self.selected | self.wanted
        return [c for c in self.catalog.electives() if c.sigla not in taken]

    @property
    def extra_electives(self) -> int:
        """How many more to draw from the pool, after the ones already wanted."""
        return max(0, self.electives_wanted - len(self.wanted))

    def toggle_wanted(self, sigla: str) -> None:
        self.wanted.symmetric_difference_update({sigla})

    @property
    def scorer(self) -> Scorer:
        return SCORERS[self.sort]

    def toggle(self, sigla: str) -> None:
        self.selected.symmetric_difference_update({sigla})

    def toggle_day(self, day: Day) -> None:
        self.free_days.symmetric_difference_update({day})

    def filters(self) -> list[object]:
        filters: list[object] = []
        if self.excluded_teachers:
            filters.append(ExcludeTeacher.of(self.excluded_teachers))
        filters.extend(FreeDay(day) for day in self.free_days)
        if self.earliest:
            filters.append(EarliestStart(self.earliest))
        if self.latest:
            filters.append(LatestEnd(self.latest))
        if self.max_days is not None:
            filters.append(MaxDays(self.max_days))
        if self.online_only:
            filters.append(ModalityIs(online=True))
        elif self.onsite_only:
            filters.append(ModalityIs(online=False))
        return filters

    def solve(self) -> None:
        """Search, rank, and record why the result is empty if it is."""
        self.candidates = []
        self.scores = []
        self.truncated = False
        self.error = None

        if not self.selected:
            self.error = "Elige al menos un ramo."
            return

        courses = self.courses
        extra = self.extra_electives
        try:
            found = list(
                iter_candidates(
                    courses,
                    self.filters(),
                    electives=self.elective_pool,
                    electives_min=extra,
                    electives_max=extra,
                    limit=RESULT_CAP + 1,
                )
            )
        except Unsatisfiable as exc:
            self.error = str(exc)
            return
        except ValueError as exc:
            self.error = str(exc)
            return

        if len(found) > RESULT_CAP:
            found = found[:RESULT_CAP]
            self.truncated = True

        if not found:
            self.error = self._explain(courses)
            return

        scored = list(ranked(found, self.scorer))
        self.candidates = [candidate for _, candidate in scored]
        self.scores = [score for score, _ in scored]

    def _explain(self, courses: list[Course]) -> str:
        pair = find_blocking_pair(courses)
        if pair:
            return (
                f"Sin resultados: {pair[0].sigla} y {pair[1].sigla} chocan en todas "
                "sus secciones."
            )
        extra = self.extra_electives
        if extra:
            fits = [t.count for t in self.report(max_count=extra) if t.schedules]
            if fits:
                return (
                    f"Sin resultados con {self.electives_wanted} optativo(s). "
                    f"El maximo que cabe es {max(fits) + len(self.wanted)}."
                )
        return "Sin resultados: revisa las restricciones, estan muy estrictas."

    def report(self, max_count: int | None = None) -> list[ElectiveTally]:
        """How many timetables fit 0, 1, 2, ... electives on top of the required set."""
        pool = self.elective_pool
        if not self.selected and not self.wanted:
            return []
        self.tallies = elective_report(
            self.courses, pool, self.filters(), max_count=max_count
        )
        return self.tallies

    def summary(self) -> str:
        if self.error:
            return self.error
        if not self.candidates:
            return "Elige ramos y presiona Generar."
        suffix = f" (mostrando las primeras {RESULT_CAP})" if self.truncated else ""
        plural = "horario" if len(self.candidates) == 1 else "horarios"
        extra = f" · {self.electives_wanted} optativo(s)" if self.electives_wanted else ""
        return f"{len(self.candidates)} {plural} por {self.sort}{extra}{suffix}"
