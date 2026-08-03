"""A course: one sigla, one name, many sections to choose between."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cached_property

from .level import Level, parse_level
from .section import Section


@dataclass(frozen=True, eq=False)
class Course:
    """A course the student may enrol in. Exactly one of its sections is picked."""

    sigla: str
    name: str
    sections: tuple[Section, ...]
    #: Credits this course is worth. Taken from the export when it carries a
    #: ``Creditos`` column, otherwise supplied by the user.
    credits: int | None = None

    def __post_init__(self) -> None:
        if not self.sections:
            raise ValueError(f"course {self.sigla} has no sections")

    @cached_property
    def level(self) -> Level:
        """The course's level.

        Sections of one course always agree in the real exports; if they ever
        disagree, the first by section code wins so the result stays stable.
        """
        return parse_level(self.sections[0].level)

    @property
    def is_elective(self) -> bool:
        return self.level.is_elective

    @property
    def is_mandatory(self) -> bool:
        return self.level.is_mandatory

    def section(self, code: str) -> Section:
        for section in self.sections:
            if section.code == code:
                return section
        raise KeyError(f"{self.sigla} has no section {code!r}")

    def filtered(self, predicate) -> Course | None:
        """A copy keeping only sections satisfying ``predicate``, or ``None`` if
        that would leave the course unschedulable."""
        kept = tuple(s for s in self.sections if predicate(s))
        if not kept:
            return None
        return replace(self, sections=kept)

    def with_credits(self, value: int | None) -> Course:
        """A copy worth ``value`` credits.

        The value is pushed onto the sections too, because a candidate holds
        sections rather than courses and still has to be able to add up what a
        timetable is worth.
        """
        return replace(
            self,
            credits=value,
            sections=tuple(replace(s, credits=value) for s in self.sections),
        )

    def __len__(self) -> int:
        return len(self.sections)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Course) and self.sigla == other.sigla

    def __hash__(self) -> int:
        return hash(self.sigla)

    def __str__(self) -> str:
        return f"{self.sigla} {self.name}"
