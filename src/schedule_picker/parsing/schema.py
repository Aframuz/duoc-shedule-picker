"""Mapping the varying CSV headers onto one set of field names.

Every DUOC export so far uses a different header. Rather than a config file per
semester, each logical field lists the column names that have been seen for it,
most specific first. Resolving a header is then a lookup.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Ordered aliases per logical field. Order matters where a file carries more
# than one candidate column.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "course_name": ("Nombre Asignatura", "Asignatura", "Ramo"),
    "section_code": ("Seccion", "Codigo"),
    "horario": ("Horario",),
    "teacher": ("Docente", "Profesor"),
    "campus": ("Sede",),
    "career": ("Carrera",),
    "plan": ("Plan",),
    "level": ("Nivel", "Semestre"),
    # 2do's "Modalidad" holds a shift ("Vespertino"), not a delivery modality.
    "shift": ("Jornada", "Modalidad"),
    "modality": ("Asignatura Virtual Sincronica",),
    # Not present in any export yet. Listed so that when one appears it is
    # picked up without a code change; until then credits come from the user.
    "credits": ("Creditos", "Credito", "SCT", "Creditos SCT", "Credits"),
}

REQUIRED_FIELDS = ("course_name", "section_code", "horario")


def normalize(column: str) -> str:
    """Fold a header cell to a comparable form: no accents, no case, no padding.

    Handles the BOM-prefixed first column and the ``ASIGNATURA VIRTUAL
    SINCRONICA`` / ``Sección`` accent-and-case variations in one step.
    """
    stripped = column.replace("﻿", "").strip()
    decomposed = unicodedata.normalize("NFKD", stripped)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.split()).casefold()


class SchemaError(ValueError):
    """The header lacks a column the parser cannot do without."""


@dataclass(frozen=True)
class Schema:
    """Which actual column supplies each logical field."""

    columns: dict[str, str]

    def get(self, row: dict[str, str], field: str) -> str | None:
        """Read a logical field out of a raw CSV row, or ``None`` if absent/blank."""
        column = self.columns.get(field)
        if column is None:
            return None
        value = (row.get(column) or "").strip()
        return value or None

    def require(self, row: dict[str, str], field: str) -> str:
        value = self.get(row, field)
        if value is None:
            raise ValueError(f"missing value for {field!r}")
        return value

    @property
    def known_fields(self) -> list[str]:
        return sorted(self.columns)


def resolve_schema(header: list[str]) -> Schema:
    """Match a CSV header against the alias table.

    Raises ``SchemaError`` listing everything missing, so an unfamiliar export
    reports all its problems at once.
    """
    by_normalized = {normalize(column): column for column in header if column}

    columns: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            actual = by_normalized.get(normalize(alias))
            if actual is not None:
                columns[field] = actual
                break

    missing = [field for field in REQUIRED_FIELDS if field not in columns]
    if missing:
        expected = "; ".join(f"{f} (one of: {', '.join(FIELD_ALIASES[f])})" for f in missing)
        raise SchemaError(
            f"CSV header is missing required column(s): {expected}. Found: {', '.join(header)}"
        )

    return Schema(columns)
