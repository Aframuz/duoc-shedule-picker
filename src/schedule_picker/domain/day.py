"""Days of the week, as they appear in DUOC schedule exports."""

from __future__ import annotations

from enum import IntEnum


class Day(IntEnum):
    """A weekday, ordered Monday-first so sorting gives chronological order."""

    LUNES = 0
    MARTES = 1
    MIERCOLES = 2
    JUEVES = 3
    VIERNES = 4
    SABADO = 5
    DOMINGO = 6

    @classmethod
    def from_code(cls, code: str) -> Day:
        """Resolve a two-letter code as used in the ``Horario`` column ("Lu", "Ma", ...)."""
        try:
            return _BY_CODE[code.strip().title()]
        except KeyError:
            raise ValueError(f"unknown day code: {code!r}") from None

    @property
    def code(self) -> str:
        """The two-letter code used in the source data."""
        return _CODES[self]

    @property
    def label(self) -> str:
        """Full Spanish name, accent-free to keep fixed-width tables aligned."""
        return _LABELS[self]


_CODES: dict[Day, str] = {
    Day.LUNES: "Lu",
    Day.MARTES: "Ma",
    Day.MIERCOLES: "Mi",
    Day.JUEVES: "Ju",
    Day.VIERNES: "Vi",
    Day.SABADO: "Sa",
    Day.DOMINGO: "Do",
}

_LABELS: dict[Day, str] = {
    Day.LUNES: "Lunes",
    Day.MARTES: "Martes",
    Day.MIERCOLES: "Miercoles",
    Day.JUEVES: "Jueves",
    Day.VIERNES: "Viernes",
    Day.SABADO: "Sabado",
    Day.DOMINGO: "Domingo",
}

_BY_CODE: dict[str, Day] = {code: day for day, code in _CODES.items()}
