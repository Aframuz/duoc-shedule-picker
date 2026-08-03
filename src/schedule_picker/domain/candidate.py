"""A complete, conflict-free choice of one section per selected course."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from functools import cached_property

from .day import Day
from .section import Section
from .time_block import TimeBlock, to_minutes


@dataclass(frozen=True, eq=False)
class ScheduleCandidate:
    """One viable timetable.

    Identity is the set of section codes, so two candidates built in different
    orders are the same candidate. That replaces the old quadratic
    ``if week not in weeks`` scan with a set membership test.
    """

    sections: tuple[Section, ...]

    @cached_property
    def meetings(self) -> tuple[TimeBlock, ...]:
        return tuple(sorted(m for section in self.sections for m in section.meetings))

    @cached_property
    def blocks_by_day(self) -> dict[Day, list[tuple[TimeBlock, Section]]]:
        """Meetings grouped by day and sorted by start time, each tagged with its section."""
        grouped: dict[Day, list[tuple[TimeBlock, Section]]] = {}
        for section in self.sections:
            for meeting in section.meetings:
                grouped.setdefault(meeting.day, []).append((meeting, section))
        for entries in grouped.values():
            entries.sort(key=lambda pair: (pair[0].start, pair[0].end))
        return dict(sorted(grouped.items()))

    @cached_property
    def days_used(self) -> frozenset[Day]:
        return frozenset(self.blocks_by_day)

    @cached_property
    def onsite_days(self) -> frozenset[Day]:
        """Days requiring physical attendance, i.e. ignoring fully online sections."""
        return frozenset(
            day
            for day, entries in self.blocks_by_day.items()
            if any(not section.is_online for _, section in entries)
        )

    def first_start(self, day: Day) -> time | None:
        entries = self.blocks_by_day.get(day)
        return entries[0][0].start if entries else None

    def last_end(self, day: Day) -> time | None:
        entries = self.blocks_by_day.get(day)
        return max(block.end for block, _ in entries) if entries else None

    @cached_property
    def total_class_minutes(self) -> int:
        return sum(meeting.duration_minutes for meeting in self.meetings)

    @cached_property
    def idle_minutes(self) -> int:
        """Minutes spent waiting between classes on the same day.

        Nested and overlapping blocks cannot occur within a candidate (that is
        what makes it a candidate), so a running high-water mark is enough.
        """
        total = 0
        for entries in self.blocks_by_day.values():
            cursor = to_minutes(entries[0][0].end)
            for block, _ in entries[1:]:
                start = to_minutes(block.start)
                if start > cursor:
                    total += start - cursor
                cursor = max(cursor, to_minutes(block.end))
        return total

    @cached_property
    def span_minutes(self) -> int:
        """Total time on the hook, from first class to last, across all days."""
        return sum(
            to_minutes(max(b.end for b, _ in entries)) - to_minutes(entries[0][0].start)
            for entries in self.blocks_by_day.values()
        )

    @cached_property
    def total_credits(self) -> int:
        """Credits this timetable is worth; sections with none count as zero."""
        return sum(section.credits or 0 for section in self.sections)

    @cached_property
    def electives(self) -> tuple[Section, ...]:
        return tuple(s for s in self.sections if s.parsed_level.is_elective)

    @cached_property
    def section_codes(self) -> frozenset[str]:
        return frozenset(section.code for section in self.sections)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ScheduleCandidate) and self.section_codes == other.section_codes

    def __hash__(self) -> int:
        return hash(self.section_codes)

    def __str__(self) -> str:
        return ", ".join(sorted(section.code for section in self.sections))
