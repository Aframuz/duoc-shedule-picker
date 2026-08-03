"""Curriculum level, and the mandatory/elective split that follows from it.

The ``Nivel`` column carries two different kinds of value. A number is the
semester the course belongs to, and those courses are compulsory for a student
in that semester. The text ``Optativos`` marks an elective, which the student
chooses among.

Older exports have only numeric levels (``Semestre`` 2, ``Nivel`` 3, ``Nivel``
4), so everything in them is mandatory — which is exactly the behaviour those
files had before electives existed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Kind(Enum):
    """Whether a course must be taken or may be chosen."""

    MANDATORY = "mandatory"
    ELECTIVE = "elective"


@dataclass(frozen=True, slots=True)
class Level:
    """A parsed ``Nivel`` value."""

    kind: Kind
    number: int | None = None
    raw: str | None = None

    @property
    def is_elective(self) -> bool:
        return self.kind is Kind.ELECTIVE

    @property
    def is_mandatory(self) -> bool:
        return self.kind is Kind.MANDATORY

    def __str__(self) -> str:
        if self.is_elective:
            return self.raw or "Optativos"
        return str(self.number) if self.number is not None else "—"


#: What a course with no ``Nivel`` column at all gets. Mandatory, unnumbered:
#: an export that does not distinguish levels is treated as one coherent set.
UNSPECIFIED = Level(kind=Kind.MANDATORY, number=None, raw=None)


def parse_level(raw: str | None) -> Level:
    """Classify a raw ``Nivel`` / ``Semestre`` cell.

    A bare number means "semester N, compulsory". Anything else that is present
    (in practice ``Optativos``) means elective. Absent means unspecified, and
    unspecified is mandatory.
    """
    if raw is None:
        return UNSPECIFIED
    text = raw.strip()
    if not text:
        return UNSPECIFIED
    if text.isdigit():
        return Level(kind=Kind.MANDATORY, number=int(text), raw=text)
    return Level(kind=Kind.ELECTIVE, raw=text)


class LevelConflict(ValueError):
    """Courses from two different semesters were requested together.

    Level 6 and level 8 belong to different points in the curriculum; a student
    is in one of them, so mixing their compulsory courses is not a timetable
    the university would let anyone enrol in.
    """

    def __init__(self, levels: list[int]) -> None:
        listed = ", ".join(str(level) for level in sorted(levels))
        super().__init__(
            f"this file covers several semesters ({listed}); "
            f"choose one with --level"
        )
        self.levels = sorted(levels)
