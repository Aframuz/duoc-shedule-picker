"""Enumerating conflict-free timetables."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from ..domain.candidate import ScheduleCandidate
from ..domain.course import Course
from ..domain.day import Day
from ..domain.section import Section
from .constraints import SectionFilter, split_filters


class Unsatisfiable(ValueError):
    """A course lost every one of its sections to the section filters.

    Distinct from "no timetable fits": here the request is impossible before the
    search even begins, and naming the course tells the user what to relax.
    """

    def __init__(self, course: Course) -> None:
        super().__init__(
            f"no sections of {course.sigla} ({course.name}) satisfy the given filters"
        )
        self.course = course


@dataclass(frozen=True)
class SolveStats:
    """Search telemetry, for ``--explain`` and for proving the pruning works."""

    nodes_visited: int = 0
    conflicts_hit: int = 0
    pruned: int = 0
    rejected_at_leaf: int = 0
    yielded: int = 0


def prepare(
    courses: Iterable[Course],
    section_filters: Iterable[SectionFilter] = (),
    *,
    drop_unsatisfiable: bool = False,
) -> list[Course]:
    """Apply the unary filters and order courses for maximum pruning.

    Courses with the fewest surviving sections go first (most-constrained-first).
    That single ordering choice is what lets an impossible 21-course request over
    17 million combinations terminate in under a millisecond: the conflict
    surfaces at depth 2 or 3 instead of at the leaves.

    ``drop_unsatisfiable`` suits electives: one the filters wiped out is simply
    not on offer, whereas a compulsory course in that state means the request
    cannot be met and should say so.
    """
    filters = list(section_filters)
    prepared: list[Course] = []

    for course in courses:
        narrowed = course
        for filt in filters:
            result = narrowed.filtered(filt.keep)
            if result is None:
                if drop_unsatisfiable:
                    narrowed = None  # type: ignore[assignment]
                    break
                raise Unsatisfiable(course)
            narrowed = result
        if narrowed is not None:
            prepared.append(narrowed)

    prepared.sort(key=lambda c: (len(c.sections), c.sigla))
    return prepared


def iter_candidates(
    courses: Iterable[Course],
    filters: Iterable[object] = (),
    *,
    electives: Iterable[Course] = (),
    electives_min: int | None = None,
    electives_max: int | None = None,
    limit: int | None = None,
    stats: list[SolveStats] | None = None,
) -> Iterator[ScheduleCandidate]:
    """Yield every timetable taking one section from each required course.

    ``courses`` are compulsory: every one of them appears in every result.
    ``electives`` are optional — each may be taken or skipped, subject to
    ``electives_min`` and ``electives_max``. Set both to the same number for
    "exactly this many". With no electives passed the behaviour is unchanged.

    Lazy: candidates stream out as they are found, so a caller wanting the top
    ten need not materialise all of them. Deterministic: courses are ordered by
    domain size then sigla, sections by code, so runs are reproducible.

    ``filters`` may mix section- and candidate-scoped filters; they are routed by
    their ``scope`` marker. Pass ``stats`` a list to receive a
    :class:`SolveStats` describing the search.
    """
    section_filters, candidate_filters, prunable = split_filters(filters)

    required = prepare(courses, section_filters)
    # An elective the filters emptied is just unavailable, not a contradiction.
    optional = prepare(electives, section_filters, drop_unsatisfiable=True)

    low, high = _pick_bounds(len(optional), electives_min, electives_max)
    counters = {"nodes": 0, "conflicts": 0, "pruned": 0, "rejected": 0, "yielded": 0}

    def emit() -> Iterator[ScheduleCandidate]:
        required_domains = [course.sections for course in required]
        optional_domains = [course.sections for course in optional]
        total = len(required_domains) + len(optional_domains)

        chosen: list[Section] = []
        occupied: dict[Day, int] = {}

        def fits(section: Section) -> bool:
            return not any(
                occupied.get(day, 0) & mask for day, mask in section.day_masks.items()
            )

        def occupy(section: Section) -> None:
            for day, mask in section.day_masks.items():
                occupied[day] = occupied.get(day, 0) | mask

        def release(section: Section) -> None:
            # Undo, so siblings start from the same state. The old
            # implementation's failure to roll back is what corrupted its grid.
            for day, mask in section.day_masks.items():
                occupied[day] &= ~mask

        def blocked() -> bool:
            return bool(prunable) and any(f.prune(tuple(chosen)) for f in prunable)

        def recurse(depth: int, taken: int) -> Iterator[ScheduleCandidate]:
            if depth == total:
                if taken < low:
                    return
                candidate = ScheduleCandidate(sections=tuple(chosen))
                if all(f.keep(candidate) for f in candidate_filters):
                    counters["yielded"] += 1
                    yield candidate
                else:
                    counters["rejected"] += 1
                return

            if depth < len(required_domains):
                for section in required_domains[depth]:
                    counters["nodes"] += 1
                    if not fits(section):
                        counters["conflicts"] += 1
                        continue
                    chosen.append(section)
                    if blocked():
                        counters["pruned"] += 1
                        chosen.pop()
                        continue
                    occupy(section)
                    yield from recurse(depth + 1, taken)
                    release(section)
                    chosen.pop()
                return

            index = depth - len(required_domains)
            remaining = len(optional_domains) - index

            # Take this elective, if there is still room for one.
            if taken < high:
                for section in optional_domains[index]:
                    counters["nodes"] += 1
                    if not fits(section):
                        counters["conflicts"] += 1
                        continue
                    chosen.append(section)
                    if blocked():
                        counters["pruned"] += 1
                        chosen.pop()
                        continue
                    occupy(section)
                    yield from recurse(depth + 1, taken + 1)
                    release(section)
                    chosen.pop()

            # Or skip it — but not if the ones left cannot reach the minimum.
            if taken + (remaining - 1) >= low:
                yield from recurse(depth + 1, taken)
            else:
                counters["pruned"] += 1

        yield from recurse(0, 0)

    for produced, candidate in enumerate(emit(), start=1):
        yield candidate
        if limit is not None and produced >= limit:
            break

    if stats is not None:
        stats.append(
            SolveStats(
                nodes_visited=counters["nodes"],
                conflicts_hit=counters["conflicts"],
                pruned=counters["pruned"],
                rejected_at_leaf=counters["rejected"],
                yielded=counters["yielded"],
            )
        )


def _pick_bounds(
    available: int,
    minimum: int | None,
    maximum: int | None,
) -> tuple[int, int]:
    """Normalise the elective count bounds, and reject impossible ones."""
    low = 0 if minimum is None else minimum
    high = available if maximum is None else maximum
    if low < 0 or high < 0:
        raise ValueError("elective counts cannot be negative")
    if low > high:
        raise ValueError(f"elective minimum {low} exceeds maximum {high}")
    if low > available:
        raise ValueError(
            f"asked for {low} elective(s) but only {available} are available"
        )
    return low, min(high, available)


def count_candidates(courses: Iterable[Course], filters: Iterable[object] = (), **kwargs) -> int:
    """How many timetables exist. Streams, so it never holds them all in memory."""
    return sum(1 for _ in iter_candidates(courses, filters, **kwargs))


@dataclass(frozen=True)
class ElectiveTally:
    """How much room there is for exactly ``count`` electives."""

    count: int
    schedules: int
    combinations: int

    def __str__(self) -> str:
        word = "elective" if self.count == 1 else "electives"
        if not self.schedules:
            return f"{self.count} {word}: no timetable fits"
        return (
            f"{self.count} {word}: {self.schedules} timetable(s) "
            f"across {self.combinations} course combination(s)"
        )


def elective_report(
    required: Sequence[Course],
    electives: Sequence[Course],
    filters: Iterable[object] = (),
    *,
    max_count: int | None = None,
) -> list[ElectiveTally]:
    """Count the timetables available for 0, 1, 2, ... electives.

    Stops at the first count that admits nothing: electives only ever add
    constraints, so once ``k`` does not fit, no larger ``k`` can either. This
    answers "how many can I actually fit on top of my compulsory courses?"
    without the user guessing.
    """
    filters = list(filters)
    ceiling = len(electives) if max_count is None else min(max_count, len(electives))

    tallies: list[ElectiveTally] = []
    for count in range(ceiling + 1):
        subsets: set[frozenset[str]] = set()
        schedules = 0
        for candidate in iter_candidates(
            required,
            filters,
            electives=electives,
            electives_min=count,
            electives_max=count,
        ):
            schedules += 1
            subsets.add(
                frozenset(
                    section.sigla
                    for section in candidate.sections
                    if section.parsed_level.is_elective
                )
            )
        tallies.append(
            ElectiveTally(count=count, schedules=schedules, combinations=len(subsets))
        )
        if schedules == 0:
            break

    return tallies


def find_blocking_pair(courses: Iterable[Course]) -> tuple[Course, Course] | None:
    """Locate two courses that cannot coexist, whatever sections are picked.

    When the result set is empty this usually explains why, and is far more
    useful than reporting zero. Returns ``None`` if every pair is individually
    compatible (in which case the clash involves three or more courses).
    """
    prepared = list(courses)
    for i, first in enumerate(prepared):
        for second in prepared[i + 1 :]:
            if not any(
                not a.conflicts_with(b) for a in first.sections for b in second.sections
            ):
                return first, second
    return None
