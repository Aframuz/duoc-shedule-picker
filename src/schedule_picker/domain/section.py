"""A bookable section of a course."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from functools import cached_property

from .day import Day
from .level import Level, parse_level
from .time_block import TimeBlock


def sigla_of(section_code: str) -> str:
    """Derive the course code from a section code: ``OCY1104-003V`` -> ``OCY1104``.

    Every section code in every known export follows this shape, which is why
    the parser does not need a dedicated sigla column (``2do_semestre.csv``
    has none).
    """
    return section_code.split("-", 1)[0].strip()


# eq=False keeps the hand-written identity below; no slots, because
# cached_property needs a per-instance __dict__ (it writes through it, which is
# also why it stays compatible with frozen=True).
@dataclass(frozen=True, eq=False)
class Section:
    """One section, identified by its code, with all of its weekly meetings.

    Equality and hashing are by ``code`` alone: the code is unique within an
    export, and this keeps candidate de-duplication cheap.
    """

    code: str
    course_name: str
    meetings: tuple[TimeBlock, ...]
    teacher: str | None = None
    campus: str | None = None
    modality: str | None = None
    level: str | None = None
    shift: str | None = None
    career: str | None = None
    #: From a ``Creditos`` column when the export has one; usually absent.
    credits: int | None = None

    @property
    def sigla(self) -> str:
        return sigla_of(self.code)

    @property
    def suffix(self) -> str:
        """The part that distinguishes sections of the same course: ``003V``."""
        _, _, suffix = self.code.partition("-")
        return suffix or self.code

    @property
    def label(self) -> str:
        """Compact cell label for timetables. Course names are truncated at 40
        characters by the source export, so the sigla is the reliable key."""
        return f"{self.sigla} {self.suffix}"

    @cached_property
    def day_masks(self) -> dict[Day, int]:
        """Occupied minutes per day, as bitmasks. Built once, used by the solver."""
        masks: dict[Day, int] = {}
        for meeting in self.meetings:
            masks[meeting.day] = masks.get(meeting.day, 0) | meeting.minute_mask
        return masks

    @cached_property
    def days(self) -> frozenset[Day]:
        return frozenset(meeting.day for meeting in self.meetings)

    @cached_property
    def earliest_start(self) -> time:
        return min(meeting.start for meeting in self.meetings)

    @cached_property
    def latest_end(self) -> time:
        return max(meeting.end for meeting in self.meetings)

    @cached_property
    def parsed_level(self) -> Level:
        return parse_level(self.level)

    @property
    def is_online(self) -> bool:
        return bool(self.modality and "ONLINE" in self.modality.upper())

    def conflicts_with(self, other: Section) -> bool:
        other_masks = other.day_masks
        return any(mask & other_masks.get(day, 0) for day, mask in self.day_masks.items())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Section) and self.code == other.code

    def __hash__(self) -> int:
        return hash(self.code)

    def __str__(self) -> str:
        return self.code
