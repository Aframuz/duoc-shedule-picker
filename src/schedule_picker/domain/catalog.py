"""Everything parsed out of one CSV export."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .course import Course
from .level import LevelConflict
from .section import Section


@dataclass(frozen=True)
class Catalog:
    """The courses on offer, keyed by sigla."""

    courses: dict[str, Course]
    source: Path | None = None
    meta: dict[str, str] = field(default_factory=dict)

    def __iter__(self) -> Iterator[Course]:
        return iter(self.sorted_courses)

    def __len__(self) -> int:
        return len(self.courses)

    def __contains__(self, sigla: str) -> bool:
        return sigla.upper() in self.courses

    @property
    def sorted_courses(self) -> list[Course]:
        return [self.courses[sigla] for sigla in sorted(self.courses)]

    @property
    def sections(self) -> list[Section]:
        return [s for course in self.sorted_courses for s in course.sections]

    def course(self, sigla: str) -> Course:
        try:
            return self.courses[sigla.upper()]
        except KeyError:
            raise KeyError(f"no course with sigla {sigla!r}") from None

    def select(self, siglas: Iterable[str]) -> list[Course]:
        """Resolve siglas to courses, preserving the caller's order.

        Raises ``KeyError`` naming every unknown sigla at once, rather than
        failing on the first one.
        """
        wanted = [s.strip().upper() for s in siglas if s.strip()]
        missing = [s for s in wanted if s not in self.courses]
        if missing:
            raise KeyError(f"unknown course sigla(s): {', '.join(missing)}")
        return [self.courses[s] for s in wanted]

    def search(self, text: str) -> list[Course]:
        """Case-insensitive substring match over sigla and course name."""
        needle = text.strip().casefold()
        if not needle:
            return self.sorted_courses
        return [
            course
            for course in self.sorted_courses
            if needle in course.sigla.casefold() or needle in course.name.casefold()
        ]

    # -- the mandatory / elective split ------------------------------------

    def levels(self) -> list[int]:
        """Numbered semesters present in this file, ascending."""
        return sorted(
            {
                course.level.number
                for course in self.sorted_courses
                if course.is_mandatory and course.level.number is not None
            }
        )

    def default_level(self) -> int | None:
        """The semester to assume when the user does not say.

        A file covering more than one numbered semester is ambiguous — level 6
        and level 8 courses belong to different students — so the caller is
        made to choose rather than being handed a silently wrong answer.
        """
        levels = self.levels()
        if len(levels) > 1:
            raise LevelConflict(levels)
        return levels[0] if levels else None

    def mandatory(self, level: int | None = None) -> list[Course]:
        """Compulsory courses, optionally restricted to one semester.

        With ``level`` omitted the semester is inferred, which is what makes an
        export with no elective rows behave exactly as it always has: every
        course comes back.
        """
        if level is None:
            level = self.default_level()
        return [
            course
            for course in self.sorted_courses
            if course.is_mandatory
            and (level is None or course.level.number in (None, level))
        ]

    def electives(self) -> list[Course]:
        return [course for course in self.sorted_courses if course.is_elective]

    def has_electives(self) -> bool:
        return any(course.is_elective for course in self.sorted_courses)

    def with_credits(self, credits: Mapping[str, int]) -> Catalog:
        """A copy with per-course credits applied, keyed by sigla.

        Exports do not currently carry a ``Creditos`` column, so this is how a
        user supplies the weights they care about.
        """
        unknown = [sigla for sigla in credits if sigla.upper() not in self.courses]
        if unknown:
            raise KeyError(f"unknown course sigla(s): {', '.join(sorted(unknown))}")
        updated = {
            sigla: course.with_credits(credits.get(sigla, course.credits))
            for sigla, course in self.courses.items()
        }
        return Catalog(courses=updated, source=self.source, meta=dict(self.meta))

    def teachers(self) -> list[str]:
        return sorted({s.teacher for s in self.sections if s.teacher})

    def campuses(self) -> list[str]:
        return sorted({s.campus for s in self.sections if s.campus})

    def modalities(self) -> list[str]:
        return sorted({s.modality for s in self.sections if s.modality})
