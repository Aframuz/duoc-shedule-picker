from __future__ import annotations

from datetime import time

import pytest

from schedule_picker.domain import Day, sigla_of
from schedule_picker.parsing import HorarioError, parse_horario, resolve_schema
from schedule_picker.parsing.schema import SchemaError, normalize

# The four real headers, verbatim (first cell BOM-stripped by utf-8-sig).
HEADERS = {
    "2do": ["Sede", "Carrera", "Modalidad", "Semestre", "Ramo", "Codigo", "Horario", "Profesor"],
    "3er": ["Sede", "Carrera", "Plan", "Jornada", "Nivel", "Sigla", "Asignatura", "Sección",
            "Horario", "Docente"],
    "4to": ["Sede", "Carrera", "Plan", "Jornada", "Nivel", "Sigla", "Asignatura", "Sección",
            "Horario", "Docente", "ASIGNATURA VIRTUAL SINCRONICA"],
    "6to": ["Sede", "Carrera", "Plan", "Jornada", "Sigla Asignatura", "Nombre Asignatura",
            "Nivel", "Sección", "Horario", "Docente", "ASIGNATURA VIRTUAL SINCRONICA"],
}

EXPECTED_COLUMNS = {
    "2do": {"course_name": "Ramo", "section_code": "Codigo", "teacher": "Profesor",
            "level": "Semestre", "shift": "Modalidad"},
    "3er": {"course_name": "Asignatura", "section_code": "Sección", "teacher": "Docente",
            "level": "Nivel", "shift": "Jornada"},
    "4to": {"course_name": "Asignatura", "section_code": "Sección",
            "modality": "ASIGNATURA VIRTUAL SINCRONICA"},
    "6to": {"course_name": "Nombre Asignatura", "section_code": "Sección",
            "modality": "ASIGNATURA VIRTUAL SINCRONICA"},
}


@pytest.mark.parametrize("name", sorted(HEADERS))
def test_resolves_every_real_header(name):
    schema = resolve_schema(HEADERS[name])
    for field, column in EXPECTED_COLUMNS[name].items():
        assert schema.columns[field] == column, f"{name}: {field}"


def test_2do_modalidad_is_a_shift_not_a_delivery_modality():
    schema = resolve_schema(HEADERS["2do"])
    assert schema.columns["shift"] == "Modalidad"
    assert "modality" not in schema.columns


def test_missing_required_column_names_all_of_them():
    with pytest.raises(SchemaError) as exc:
        resolve_schema(["Sede", "Carrera"])
    message = str(exc.value)
    assert "course_name" in message and "section_code" in message and "horario" in message


def test_normalize_folds_accents_case_and_bom():
    assert normalize("﻿Sede") == "sede"
    assert normalize("Sección") == normalize("SECCION") == "seccion"
    assert normalize("  ASIGNATURA   VIRTUAL  ") == "asignatura virtual"


@pytest.mark.parametrize(
    ("raw", "day", "start", "end"),
    [
        ("Ju 19:01:00 - 20:20:00", Day.JUEVES, time(19, 1), time(20, 20)),
        ("Sa 8:31:00 - 9:50:00", Day.SABADO, time(8, 31), time(9, 50)),  # unpadded hour
        ("Lu 21:11:00 - 22:30:00", Day.LUNES, time(21, 11), time(22, 30)),
        ("  Mi 19:01 - 20:20  ", Day.MIERCOLES, time(19, 1), time(20, 20)),  # no seconds
    ],
)
def test_parse_horario(raw, day, start, end):
    parsed = parse_horario(raw)
    assert (parsed.day, parsed.start, parsed.end) == (day, start, end)


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "Xx 19:01:00 - 20:20:00", "Lu 19:01:00", "Lu 25:00:00 - 26:00:00",
     "Lu 20:20:00 - 19:01:00", "nonsense"],
)
def test_parse_horario_rejects_junk(raw):
    with pytest.raises(HorarioError):
        parse_horario(raw)


@pytest.mark.parametrize(
    ("code", "expected"),
    [("OCY1104-003V", "OCY1104"), ("BDY1101-013V", "BDY1101"), ("NOHYPHEN", "NOHYPHEN")],
)
def test_sigla_derived_from_section_code(code, expected):
    assert sigla_of(code) == expected
