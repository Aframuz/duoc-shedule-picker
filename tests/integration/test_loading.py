"""Loading the four real exports."""

from __future__ import annotations

import pytest

from schedule_picker.parsing import load_catalog

from ..conftest import DATASETS

# Measured from the source files. Meeting counts are post-deduplication.
EXPECTED = {
    "2do": {"rows": 42, "meetings": 42, "courses": 6, "sections": 21, "duplicates": 0},
    "3er": {"rows": 23, "meetings": 23, "courses": 3, "sections": 8, "duplicates": 0},
    "4to": {"rows": 22, "meetings": 22, "courses": 5, "sections": 10, "duplicates": 0},
    # 853 rows collapse to 133 meetings: every meeting repeats once per plan.
    "6to": {"rows": 853, "meetings": 133, "courses": 21, "sections": 63, "duplicates": 720},
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_load_shapes(name):
    catalog, report = load_catalog(DATASETS[name])
    expected = EXPECTED[name]
    assert report.rows_read == expected["rows"]
    assert report.meetings_kept == expected["meetings"]
    assert report.duplicates_dropped == expected["duplicates"]
    assert len(catalog) == expected["courses"]
    assert len(catalog.sections) == expected["sections"]
    assert report.ok, [str(e) for e in report.errors]


def test_no_section_conflicts_with_itself(catalogs):
    """A section that overlaps itself could never be scheduled; none do."""
    for name, catalog in catalogs.items():
        for section in catalog.sections:
            meetings = section.meetings
            for i, a in enumerate(meetings):
                for b in meetings[i + 1 :]:
                    assert not a.overlaps(b), f"{name}: {section.code} overlaps itself"


def test_6to_is_electives_across_one_campus(catalogs):
    catalog = catalogs["6to"]
    assert catalog.campuses() == ["ANTONIO VARAS"]
    # 47 distinct values in the column, one of which is blank and is dropped.
    assert len(catalog.teachers()) == 46
    # Section counts per course drive the solver's ordering heuristic.
    counts = sorted(len(course) for course in catalog)
    assert counts[0] == 1 and counts[-1] == 8


def test_course_names_are_stable_per_sigla(catalogs):
    for name, catalog in catalogs.items():
        for course in catalog:
            names = {s.course_name for s in course.sections}
            assert len(names) == 1, f"{name}: {course.sigla} has names {names}"
