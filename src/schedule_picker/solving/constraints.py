"""Filters that narrow the search.

Two kinds, because they apply at different moments:

* :class:`SectionFilter` judges one section on its own. Applied once up front,
  shrinking each course's domain before the search starts.
* :class:`CandidateFilter` judges a whole timetable. Applied at the leaf — but
  those whose verdict can only get worse as sections are added also implement
  ``prune``, letting the solver abandon a partial assignment early.

This replaces the commented-out ``filter_by_section`` calls that used to be
edited by hand in ``main_old.py``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import time
from typing import Protocol, runtime_checkable

from ..domain.candidate import ScheduleCandidate
from ..domain.day import Day
from ..domain.section import Section
from ..domain.time_block import to_minutes


@runtime_checkable
class SectionFilter(Protocol):
    """Accepts or rejects a single section."""

    scope: str = "section"

    def keep(self, section: Section) -> bool: ...


@runtime_checkable
class CandidateFilter(Protocol):
    """Accepts or rejects a complete timetable."""

    scope: str = "candidate"

    def keep(self, candidate: ScheduleCandidate) -> bool: ...


@runtime_checkable
class Prunable(Protocol):
    """A candidate filter that can also reject a partial assignment.

    Only implement this when rejection is monotone: if a partial set of sections
    already fails, no addition can rescue it. Days used and latest finish time
    both behave that way; "at least N online courses" does not.
    """

    def prune(self, sections: tuple[Section, ...]) -> bool: ...


# --------------------------------------------------------------------------
# Section filters
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ExcludeTeacher:
    """Drop sections taught by any of these people (case-insensitive substring)."""

    scope = "section"

    names: frozenset[str]

    @classmethod
    def of(cls, names: Iterable[str]) -> ExcludeTeacher:
        return cls(frozenset(n.strip().casefold() for n in names if n.strip()))

    def keep(self, section: Section) -> bool:
        if not section.teacher:
            return True
        teacher = section.teacher.casefold()
        return not any(name in teacher for name in self.names)


@dataclass(frozen=True)
class ExcludeSection:
    """Drop specific section codes, e.g. one you already know is full."""

    scope = "section"

    codes: frozenset[str]

    @classmethod
    def of(cls, codes: Iterable[str]) -> ExcludeSection:
        return cls(frozenset(c.strip().upper() for c in codes if c.strip()))

    def keep(self, section: Section) -> bool:
        return section.code.upper() not in self.codes


@dataclass(frozen=True)
class RequireSection:
    """Pin a course to specific sections; other courses are unaffected."""

    scope = "section"

    codes: frozenset[str]

    @classmethod
    def of(cls, codes: Iterable[str]) -> RequireSection:
        return cls(frozenset(c.strip().upper() for c in codes if c.strip()))

    def keep(self, section: Section) -> bool:
        pinned = {code.split("-", 1)[0] for code in self.codes}
        if section.sigla.upper() not in pinned:
            return True
        return section.code.upper() in self.codes


@dataclass(frozen=True)
class CampusIs:
    """Keep only sections at one campus. Sections with no campus recorded pass."""

    scope = "section"

    campus: str

    def keep(self, section: Section) -> bool:
        return not section.campus or section.campus.casefold() == self.campus.casefold()


@dataclass(frozen=True)
class ModalityIs:
    """Keep only online, or only in-person, sections."""

    scope = "section"

    online: bool

    def keep(self, section: Section) -> bool:
        return section.is_online is self.online


@dataclass(frozen=True)
class EarliestStart:
    """No class may begin before this time."""

    scope = "section"

    moment: time

    def keep(self, section: Section) -> bool:
        return section.earliest_start >= self.moment


@dataclass(frozen=True)
class LatestEnd:
    """No class may run past this time."""

    scope = "section"

    moment: time

    def keep(self, section: Section) -> bool:
        return section.latest_end <= self.moment


@dataclass(frozen=True)
class FreeDay:
    """Keep this day clear.

    A section filter rather than a candidate filter: a section that meets on the
    forbidden day can never appear in an acceptable timetable, so it is cheaper
    to remove it from the domain outright.
    """

    scope = "section"

    day: Day

    def keep(self, section: Section) -> bool:
        return self.day not in section.days


# --------------------------------------------------------------------------
# Candidate filters
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MaxDays:
    """At most this many days with any class at all."""

    scope = "candidate"

    limit: int

    def keep(self, candidate: ScheduleCandidate) -> bool:
        return len(candidate.days_used) <= self.limit

    def prune(self, sections: tuple[Section, ...]) -> bool:
        """Days only accumulate, so exceeding the limit is already terminal."""
        days: set[Day] = set()
        for section in sections:
            days |= section.days
            if len(days) > self.limit:
                return True
        return False


@dataclass(frozen=True)
class MaxOnsiteDays:
    """At most this many days requiring physical attendance."""

    scope = "candidate"

    limit: int

    def keep(self, candidate: ScheduleCandidate) -> bool:
        return len(candidate.onsite_days) <= self.limit

    def prune(self, sections: tuple[Section, ...]) -> bool:
        days: set[Day] = set()
        for section in sections:
            if not section.is_online:
                days |= section.days
                if len(days) > self.limit:
                    return True
        return False


@dataclass(frozen=True)
class MaxIdleMinutes:
    """Cap the total dead time spent waiting between classes."""

    scope = "candidate"

    limit: int

    def keep(self, candidate: ScheduleCandidate) -> bool:
        return candidate.idle_minutes <= self.limit


@dataclass(frozen=True)
class MaxGapMinutes:
    """Cap the longest single gap between consecutive classes on one day."""

    scope = "candidate"

    limit: int

    def keep(self, candidate: ScheduleCandidate) -> bool:
        for entries in candidate.blocks_by_day.values():
            cursor = to_minutes(entries[0][0].end)
            for block, _ in entries[1:]:
                start = to_minutes(block.start)
                if start - cursor > self.limit:
                    return False
                cursor = max(cursor, to_minutes(block.end))
        return True


@dataclass(frozen=True)
class MinCredits:
    """Require the timetable to be worth at least this many credits.

    Courses with no credits recorded count as zero, so this only does something
    useful once credits have been supplied.
    """

    scope = "candidate"

    minimum: int

    def keep(self, candidate: ScheduleCandidate) -> bool:
        return candidate.total_credits >= self.minimum


def split_filters(
    filters: Iterable[object],
) -> tuple[list[SectionFilter], list[CandidateFilter], list[Prunable]]:
    """Sort a mixed bag of filters into the buckets the solver expects.

    Dispatch is on the class-level ``scope`` marker, so a filter defined outside
    this module works the same as the built-in ones.
    """
    section_filters: list[SectionFilter] = []
    candidate_filters: list[CandidateFilter] = []
    prunable: list[Prunable] = []

    for item in filters:
        scope = getattr(item, "scope", None)
        if scope == "section":
            section_filters.append(item)  # type: ignore[arg-type]
        elif scope == "candidate":
            candidate_filters.append(item)  # type: ignore[arg-type]
        else:
            raise TypeError(
                f"{type(item).__name__} must define scope = 'section' or 'candidate'"
            )
        if hasattr(item, "prune"):
            prunable.append(item)  # type: ignore[arg-type]

    return section_filters, candidate_filters, prunable
