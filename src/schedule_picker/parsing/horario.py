"""Parsing the ``Horario`` column: ``"Ju 19:01:00 - 20:20:00"``."""

from __future__ import annotations

import re
from datetime import time

from ..domain.day import Day
from ..domain.time_block import TimeBlock

# Hours are not zero-padded in the source data ("Sa 8:31:00 - 9:50:00"), and
# seconds are always present but always zero.
_HORARIO = re.compile(
    r"^\s*(?P<day>[A-Za-z]{2})\s+"
    r"(?P<sh>\d{1,2}):(?P<sm>\d{2})(?::(?P<ss>\d{2}))?\s*-\s*"
    r"(?P<eh>\d{1,2}):(?P<em>\d{2})(?::(?P<es>\d{2}))?\s*$"
)


class HorarioError(ValueError):
    """The cell does not match the expected ``<day> <start> - <end>`` shape."""


def parse_horario(value: str) -> TimeBlock:
    """Turn one ``Horario`` cell into a :class:`TimeBlock`."""
    match = _HORARIO.match(value or "")
    if match is None:
        raise HorarioError(f"cannot parse horario: {value!r}")

    try:
        day = Day.from_code(match["day"])
    except ValueError as exc:
        raise HorarioError(str(exc)) from None

    try:
        start = time(int(match["sh"]), int(match["sm"]))
        end = time(int(match["eh"]), int(match["em"]))
    except ValueError as exc:
        raise HorarioError(f"invalid time in horario {value!r}: {exc}") from None

    try:
        return TimeBlock(day=day, start=start, end=end)
    except ValueError as exc:
        raise HorarioError(f"invalid horario {value!r}: {exc}") from None
