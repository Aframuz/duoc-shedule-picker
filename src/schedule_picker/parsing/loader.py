"""Reading a CSV export into a :class:`Catalog`."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.catalog import Catalog
from ..domain.course import Course
from ..domain.section import Section, sigla_of
from ..domain.time_block import TimeBlock
from .horario import parse_horario
from .schema import Schema, SchemaError, resolve_schema

__all__ = ["LoadReport", "RowError", "load_catalog", "SchemaError"]


@dataclass(frozen=True)
class RowError:
    """A row that could not be understood, kept for reporting rather than raised."""

    line: int
    reason: str
    raw: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.reason}"


@dataclass
class LoadReport:
    """What happened during a load. Surfaced by ``--validate`` and the TUI banner."""

    source: Path
    rows_read: int = 0
    meetings_kept: int = 0
    duplicates_dropped: int = 0
    errors: list[RowError] = field(default_factory=list)
    schema: Schema | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        parts = [
            f"{self.rows_read} rows",
            f"{self.meetings_kept} meetings",
        ]
        if self.duplicates_dropped:
            parts.append(f"{self.duplicates_dropped} duplicates dropped")
        if self.errors:
            parts.append(f"{len(self.errors)} bad rows")
        return ", ".join(parts)


def load_catalog(
    path: str | Path,
    *,
    strict: bool = False,
    campus: str | None = None,
) -> tuple[Catalog, LoadReport]:
    """Parse ``path`` into a catalog.

    Rows are de-duplicated on ``(section code, day, start, end)``. This is not a
    nicety: ``6to_semestre.csv`` repeats every meeting once per curriculum plan,
    turning 133 real meetings into 853 rows, and a section that conflicts with
    itself can never be scheduled.

    With ``strict``, the first unparseable row raises. Otherwise bad rows are
    collected in the report and skipped, so one malformed line does not cost the
    user the whole file.
    """
    path = Path(path)
    report = LoadReport(source=path)

    # utf-8-sig: every known export is BOM-prefixed.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SchemaError(f"{path} is empty")

        schema = resolve_schema(list(reader.fieldnames))
        report.schema = schema

        # section code -> meetings and the attributes seen for it
        meetings: dict[str, set[TimeBlock]] = {}
        attributes: dict[str, dict[str, str | None]] = {}

        for line, row in enumerate(reader, start=2):
            report.rows_read += 1
            try:
                code = schema.require(row, "section_code")
                name = schema.require(row, "course_name")
                block = parse_horario(schema.require(row, "horario"))
            except (ValueError, KeyError) as exc:
                error = RowError(line=line, reason=str(exc), raw=_render_row(row))
                if strict:
                    raise ValueError(f"{path}: {error}") from None
                report.errors.append(error)
                continue

            row_campus = schema.get(row, "campus")
            if campus and row_campus and row_campus.casefold() != campus.casefold():
                continue

            blocks = meetings.setdefault(code, set())
            if block in blocks:
                report.duplicates_dropped += 1
                continue
            blocks.add(block)
            report.meetings_kept += 1

            attributes.setdefault(
                code,
                {
                    "course_name": name,
                    "teacher": schema.get(row, "teacher"),
                    "campus": row_campus,
                    "modality": schema.get(row, "modality"),
                    "level": schema.get(row, "level"),
                    "shift": schema.get(row, "shift"),
                    "career": schema.get(row, "career"),
                    "credits": schema.get(row, "credits"),
                },
            )

    catalog = _build_catalog(meetings, attributes, path)
    return catalog, report


def _build_catalog(
    meetings: dict[str, set[TimeBlock]],
    attributes: dict[str, dict[str, str | None]],
    path: Path,
) -> Catalog:
    sections_by_sigla: dict[str, list[Section]] = {}
    for code, blocks in meetings.items():
        attrs = attributes[code]
        section = Section(
            code=code,
            course_name=attrs["course_name"] or code,
            meetings=tuple(sorted(blocks)),
            teacher=attrs["teacher"],
            campus=attrs["campus"],
            modality=attrs["modality"],
            level=attrs["level"],
            shift=attrs["shift"],
            career=attrs["career"],
            credits=_as_int(attrs["credits"]),
        )
        sections_by_sigla.setdefault(sigla_of(code), []).append(section)

    courses: dict[str, Course] = {}
    for sigla, sections in sections_by_sigla.items():
        sections.sort(key=lambda s: s.code)
        courses[sigla] = Course(
            sigla=sigla,
            # Section rows for one course carry the same name; take the first
            # deterministically rather than trusting file order.
            name=sections[0].course_name,
            sections=tuple(sections),
            credits=next((s.credits for s in sections if s.credits is not None), None),
        )

    return Catalog(courses=courses, source=path)


def _as_int(value: str | None) -> int | None:
    """Parse a numeric cell, tolerating junk rather than failing the whole load."""
    if value is None:
        return None
    try:
        return int(float(value.strip().replace(",", ".")))
    except (ValueError, AttributeError):
        return None


def _render_row(row: dict[str, str]) -> str:
    return ",".join(f"{v}" for v in row.values() if v is not None)
