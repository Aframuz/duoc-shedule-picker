"""Ranking timetables.

Every scorer follows one convention: **lower is better**. That keeps composition
trivial and means ``heapq.nsmallest`` is always the right way to take the best N.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..domain.candidate import ScheduleCandidate
from ..domain.time_block import to_minutes


@runtime_checkable
class Scorer(Protocol):
    """Rates a timetable. Lower is better."""

    name: str

    def score(self, candidate: ScheduleCandidate) -> float: ...


@dataclass(frozen=True)
class FewestDays:
    """Prefer going in on as few days as possible."""

    name: str = "fewest-days"

    def score(self, candidate: ScheduleCandidate) -> float:
        return len(candidate.days_used)


@dataclass(frozen=True)
class FewestOnsiteDays:
    """Prefer as few days physically on campus as possible; online days are free."""

    name: str = "fewest-onsite-days"

    def score(self, candidate: ScheduleCandidate) -> float:
        return len(candidate.onsite_days)


@dataclass(frozen=True)
class LeastIdleTime:
    """Prefer timetables without long waits between classes."""

    name: str = "least-idle"

    def score(self, candidate: ScheduleCandidate) -> float:
        return candidate.idle_minutes


@dataclass(frozen=True)
class LatestStart:
    """Prefer starting as late as possible, averaged over the days used."""

    name: str = "latest-start"

    def score(self, candidate: ScheduleCandidate) -> float:
        starts = [to_minutes(entries[0][0].start) for entries in candidate.blocks_by_day.values()]
        return -sum(starts) / len(starts) if starts else 0.0


@dataclass(frozen=True)
class EarliestFinish:
    """Prefer finishing as early as possible, averaged over the days used."""

    name: str = "earliest-finish"

    def score(self, candidate: ScheduleCandidate) -> float:
        ends = [
            max(to_minutes(block.end) for block, _ in entries)
            for entries in candidate.blocks_by_day.values()
        ]
        return sum(ends) / len(ends) if ends else 0.0


@dataclass(frozen=True)
class MostCredits:
    """Prefer the timetable that advances the curriculum furthest."""

    name: str = "most-credits"

    def score(self, candidate: ScheduleCandidate) -> float:
        return -candidate.total_credits


@dataclass(frozen=True)
class MostElectives:
    """Prefer fitting in as many electives as possible."""

    name: str = "most-electives"

    def score(self, candidate: ScheduleCandidate) -> float:
        return -len(candidate.electives)


@dataclass(frozen=True)
class PreferTeacher:
    """Reward timetables taught by people you want, penalise the rest."""

    liked: frozenset[str]
    name: str = "prefer-teacher"

    @classmethod
    def of(cls, names: Iterable[str]) -> PreferTeacher:
        return cls(frozenset(n.strip().casefold() for n in names if n.strip()))

    def score(self, candidate: ScheduleCandidate) -> float:
        hits = sum(
            1
            for section in candidate.sections
            if section.teacher and any(n in section.teacher.casefold() for n in self.liked)
        )
        return -hits


@dataclass(frozen=True)
class Composite:
    """Weighted sum of other scorers.

    Components are on different scales (days vs minutes), so weight accordingly:
    ``Composite(((FewestDays(), 60.0), (LeastIdleTime(), 1.0)))`` trades one extra
    day against an hour of waiting.
    """

    parts: tuple[tuple[Scorer, float], ...]
    name: str = "composite"

    def score(self, candidate: ScheduleCandidate) -> float:
        return sum(weight * scorer.score(candidate) for scorer, weight in self.parts)


#: Selectable by name from the CLI and the TUI.
SCORERS: dict[str, Scorer] = {
    s.name: s
    for s in (
        FewestDays(),
        FewestOnsiteDays(),
        LeastIdleTime(),
        LatestStart(),
        EarliestFinish(),
        MostCredits(),
        MostElectives(),
    )
}

#: A reasonable default: minimise days on campus, break ties on dead time.
BALANCED = Composite(((FewestOnsiteDays(), 240.0), (LeastIdleTime(), 1.0)), name="balanced")
SCORERS[BALANCED.name] = BALANCED


def top_n(
    candidates: Iterable[ScheduleCandidate],
    scorer: Scorer,
    n: int,
) -> list[ScheduleCandidate]:
    """The ``n`` best candidates, holding only ``n`` of them at a time.

    Ties break on the section codes so results are stable across runs.
    """
    return [
        candidate
        for _, _, candidate in heapq.nsmallest(
            n,
            (
                (scorer.score(candidate), sorted(candidate.section_codes), candidate)
                for candidate in candidates
            ),
            key=lambda item: (item[0], item[1]),
        )
    ]


def ranked(
    candidates: Iterable[ScheduleCandidate],
    scorer: Scorer,
) -> Iterator[tuple[float, ScheduleCandidate]]:
    """Every candidate with its score, best first. Materialises the whole set."""
    scored = sorted(
        ((scorer.score(c), sorted(c.section_codes), c) for c in candidates),
        key=lambda item: (item[0], item[1]),
    )
    return ((score, candidate) for score, _, candidate in scored)
