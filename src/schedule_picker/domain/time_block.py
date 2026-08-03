"""A single meeting: one day, one half-open time interval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from .day import Day

MINUTES_PER_DAY = 24 * 60


def to_minutes(value: time) -> int:
    """Minutes since midnight."""
    return value.hour * 60 + value.minute


@dataclass(frozen=True, order=True, slots=True)
class TimeBlock:
    """One class meeting.

    Intervals are half-open: ``[start, end)``. Two blocks that merely touch
    (10:01-10:40 followed by 10:41-11:20) do not conflict, while nested blocks
    (10:01-11:20 against 10:01-10:40) do. Both cases occur in the real data.
    """

    day: Day
    start: time
    end: time

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError(f"time block must start before it ends: {self.start} - {self.end}")

    def overlaps(self, other: TimeBlock) -> bool:
        """Whether the two blocks fall on the same day and share any minute."""
        return self.day is other.day and self.start < other.end and other.start < self.end

    @property
    def duration_minutes(self) -> int:
        return to_minutes(self.end) - to_minutes(self.start)

    @property
    def minute_mask(self) -> int:
        """Bitmask of occupied minutes, one bit per minute since midnight.

        Conflict detection between two blocks on the same day is then a single
        ``&``, which is what keeps the solver's inner loop cheap.
        """
        span = self.duration_minutes
        return ((1 << span) - 1) << to_minutes(self.start)

    def __str__(self) -> str:
        return f"{self.day.code} {self.start:%H:%M}-{self.end:%H:%M}"
