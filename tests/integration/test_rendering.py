"""Renderer output against the real data, including golden files."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import pytest

from schedule_picker.rendering import CsvRenderer, HtmlRenderer, JsonRenderer, TextRenderer
from schedule_picker.solving import iter_candidates

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"


@pytest.fixture
def fourth_semester(catalogs):
    """The 4th semester's three timetables, in solver order."""
    return list(iter_candidates(catalogs["4to"].sorted_courses))


def check_golden(name: str, actual: str) -> None:
    """Compare against a committed golden, refreshing it when asked.

    ``UPDATE_GOLDEN=1 pytest`` rewrites them after an intentional change.
    """
    path = GOLDEN_DIR / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
    assert path.exists(), f"missing golden {path}; run UPDATE_GOLDEN=1 pytest"
    assert actual == path.read_text(encoding="utf-8"), f"{name} changed"


def test_text_golden(fourth_semester):
    check_golden("4to.txt", TextRenderer().render_all(fourth_semester))


def test_html_golden(fourth_semester):
    check_golden("4to.html", HtmlRenderer().render_all(fourth_semester))


def test_csv_golden(fourth_semester):
    check_golden("4to.csv", CsvRenderer().render_all(fourth_semester))


def test_json_golden(fourth_semester):
    check_golden("4to.json", JsonRenderer().render_all(fourth_semester))


def test_text_names_every_section(fourth_semester):
    output = TextRenderer().render_all(fourth_semester)
    for candidate in fourth_semester:
        for section in candidate.sections:
            assert section.label in output
            assert section.course_name in output


def test_html_is_self_contained(fourth_semester):
    """A strict rule: it has to survive being emailed."""
    output = HtmlRenderer().render_all(fourth_semester)
    for forbidden in ("<script", "http://", "https://", "src=", "@import"):
        assert forbidden not in output, forbidden
    assert "<style>" in output and output.startswith("<!doctype html>")


def test_html_escapes_content():
    """Course names come from an untrusted file; markup in them must not survive."""
    from schedule_picker.domain import Day, ScheduleCandidate

    hostile = ScheduleCandidate(sections=(_hostile_section(Day.LUNES),))
    output = HtmlRenderer().render_all([hostile])
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert output.count("<html") == 1


def _hostile_section(day):
    from datetime import time

    from schedule_picker.domain import Section, TimeBlock

    return Section(
        code="XSS0001-001V",
        course_name="<script>alert(1)</script>",
        meetings=(TimeBlock(day, time(19, 1), time(20, 20)),),
        teacher='" onload="x',
    )


def test_html_colours_are_stable_per_course(fourth_semester):
    first = HtmlRenderer().render_all(fourth_semester)
    second = HtmlRenderer().render_all(fourth_semester)
    assert first == second


def test_csv_round_trips(fourth_semester):
    rows = list(csv.DictReader(io.StringIO(CsvRenderer().render_all(fourth_semester))))
    expected = sum(len(s.meetings) for c in fourth_semester for s in c.sections)
    assert len(rows) == expected
    assert {int(r["opcion"]) for r in rows} == {1, 2, 3}
    assert all(r["sigla"] and r["seccion"] and r["dia"] for r in rows)


def test_json_round_trips(fourth_semester):
    payload = json.loads(JsonRenderer().render_all(fourth_semester))
    assert payload["total"] == 3
    for entry, candidate in zip(payload["horarios"], fourth_semester, strict=True):
        assert {s["seccion"] for s in entry["secciones"]} == set(candidate.section_codes)
        assert entry["minutos_clase"] == candidate.total_class_minutes


def test_scores_are_included_when_given(fourth_semester):
    scores = [1.0, 2.0, 3.0]
    payload = json.loads(JsonRenderer().render_all(fourth_semester, scores))
    assert [e["puntaje"] for e in payload["horarios"]] == scores
    assert "puntaje 1" in TextRenderer().render_all(fourth_semester, scores)


def test_empty_result_is_reported_not_blank():
    for renderer in (TextRenderer(), HtmlRenderer()):
        output = renderer.render_all([])
        assert "No hay horarios" in output


@pytest.mark.parametrize("name", ["2do", "3er", "4to"])
def test_every_dataset_renders_in_every_format(name, catalogs):
    candidates = list(iter_candidates(catalogs[name].sorted_courses))
    for renderer in (TextRenderer(), HtmlRenderer(), CsvRenderer(), JsonRenderer()):
        output = renderer.render_all(candidates)
        assert output.strip(), f"{name} produced nothing via {type(renderer).__name__}"
