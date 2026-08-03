from __future__ import annotations

from datetime import time

import pytest

from schedule_picker.domain import Day, TimeBlock

from ..conftest import block


def test_rejects_zero_and_negative_spans():
    with pytest.raises(ValueError):
        TimeBlock(Day.LUNES, time(19, 0), time(19, 0))
    with pytest.raises(ValueError):
        TimeBlock(Day.LUNES, time(20, 0), time(19, 0))


@pytest.mark.parametrize(
    ("a", "b", "expected", "why"),
    [
        (("19:01", "20:20"), ("19:01", "20:20"), True, "identical"),
        (("19:01", "20:20"), ("20:31", "21:50"), False, "disjoint"),
        # Real adjacency in the data: 10:01-10:40 is followed by 10:41-11:20.
        (("10:01", "10:40"), ("10:41", "11:20"), False, "touching, half-open"),
        (("19:01", "20:20"), ("20:20", "21:00"), False, "end meets start exactly"),
        # Real nesting in the data: a 40-minute block inside an 80-minute one.
        (("10:01", "11:20"), ("10:01", "10:40"), True, "nested"),
        (("19:01", "20:20"), ("19:30", "21:00"), True, "partial"),
        (("19:01", "20:20"), ("19:30", "19:45"), True, "strictly inside"),
    ],
)
def test_overlap_truth_table(a, b, expected, why):
    first = block(Day.LUNES, *a)
    second = block(Day.LUNES, *b)
    assert first.overlaps(second) is expected, why
    assert second.overlaps(first) is expected, f"{why} (symmetric)"


def test_same_times_on_different_days_never_overlap():
    assert not block(Day.LUNES, "19:01", "20:20").overlaps(block(Day.MARTES, "19:01", "20:20"))


def test_minute_mask_matches_overlap():
    a = block(Day.LUNES, "10:01", "11:20")
    b = block(Day.LUNES, "10:41", "11:20")
    c = block(Day.LUNES, "11:20", "12:00")
    assert bool(a.minute_mask & b.minute_mask) is a.overlaps(b) is True
    assert bool(a.minute_mask & c.minute_mask) is a.overlaps(c) is False


def test_duration_and_ordering():
    assert block(Day.LUNES, "19:01", "20:20").duration_minutes == 79
    early = block(Day.LUNES, "19:01", "20:20")
    late = block(Day.MARTES, "08:31", "09:50")
    assert sorted([late, early]) == [early, late], "ordered by day first"
