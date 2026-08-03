"""The correctness oracle.

The original implementation committed its results to ``output/schedules_*.txt``.
Counting the ``SEMANA`` banners in those files gives 30 timetables for the 2nd
semester and 3 for the 4th. Those numbers are reproduced here by independent
interval arithmetic, and pin the solver: if a change moves them, the change
is wrong.
"""

from __future__ import annotations

import itertools

import pytest

from schedule_picker.solving import count_candidates, iter_candidates

# 2do and 4to come from the committed legacy output; 3er was verified by brute
# force (the legacy run for it was never committed).
LEGACY_COUNTS = {"2do": 30, "3er": 5, "4to": 3}


@pytest.mark.parametrize("name", sorted(LEGACY_COUNTS))
def test_matches_legacy_output(name, catalogs):
    catalog = catalogs[name]
    assert count_candidates(catalog.sorted_courses) == LEGACY_COUNTS[name]


@pytest.mark.parametrize("name", sorted(LEGACY_COUNTS))
def test_matches_exhaustive_brute_force(name, catalogs):
    """The pruning search finds exactly what the naive product finds.

    Guards against pruning that is too aggressive as much as too weak.
    """
    catalog = catalogs[name]
    courses = catalog.sorted_courses

    def fits(combo) -> bool:
        meetings = [m for section in combo for m in section.meetings]
        return not any(
            a.overlaps(b) for a, b in itertools.combinations(meetings, 2)
        )

    expected = {
        frozenset(s.code for s in combo)
        for combo in itertools.product(*(c.sections for c in courses))
        if fits(combo)
    }
    actual = {c.section_codes for c in iter_candidates(courses)}
    assert actual == expected


def test_every_candidate_is_actually_conflict_free(catalogs):
    """Property: nothing that overlaps ever escapes the solver."""
    for name, catalog in catalogs.items():
        courses = catalog.sorted_courses
        if name == "6to":
            # Whole-catalog 6to is infeasible; take a solvable slice.
            courses = sorted(courses, key=lambda c: -len(c))[:5]
        for candidate in itertools.islice(iter_candidates(courses), 200):
            meetings = candidate.meetings
            for a, b in itertools.combinations(meetings, 2):
                assert not a.overlaps(b), f"{name}: {candidate} has a clash"


def test_one_section_per_course(catalogs):
    catalog = catalogs["2do"]
    courses = catalog.sorted_courses
    for candidate in iter_candidates(courses):
        assert len(candidate.sections) == len(courses)
        assert len({s.sigla for s in candidate.sections}) == len(courses)


def test_candidates_are_unique(catalogs):
    """Identity is the section-code set, so duplicates cannot occur."""
    catalog = catalogs["2do"]
    produced = list(iter_candidates(catalog.sorted_courses))
    assert len(set(produced)) == len(produced) == 30
