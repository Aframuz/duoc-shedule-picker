"""Solver behaviour on the real data: constraints, pruning, ranking."""

from __future__ import annotations

import time as timing
from datetime import time

import pytest

from schedule_picker.domain import Day
from schedule_picker.solving import (
    SCORERS,
    ExcludeSection,
    ExcludeTeacher,
    FreeDay,
    LatestEnd,
    MaxDays,
    MaxOnsiteDays,
    RequireSection,
    SolveStats,
    Unsatisfiable,
    count_candidates,
    find_blocking_pair,
    iter_candidates,
    prepare,
    top_n,
)


def biggest(catalog, n):
    """The ``n`` courses with the most sections — the interesting search space."""
    return sorted(catalog.sorted_courses, key=lambda c: (-len(c), c.sigla))[:n]


def test_6to_whole_catalog_is_infeasible_and_fast(catalogs):
    """21 courses is a 17-million-combination product; pruning ends it instantly."""
    courses = catalogs["6to"].sorted_courses
    started = timing.perf_counter()
    stats: list[SolveStats] = []
    found = list(iter_candidates(courses, stats=stats))
    elapsed = timing.perf_counter() - started

    assert found == []
    assert elapsed < 1.0, f"took {elapsed:.3f}s — pruning regressed"
    # Nowhere near the 17.2M leaves a naive product would touch.
    assert stats[0].nodes_visited < 10_000


def test_6to_subset_is_solvable(catalogs):
    courses = biggest(catalogs["6to"], 5)
    found = list(iter_candidates(courses))
    assert found, "five courses should admit some timetable"
    assert len(found) == count_candidates(courses)


def test_explains_infeasibility_by_naming_a_blocking_pair(catalogs):
    courses = catalogs["6to"].sorted_courses
    assert not list(iter_candidates(courses))
    pair = find_blocking_pair(courses)
    assert pair is not None
    first, second = pair
    # Genuinely irreconcilable: every section of one clashes with every section
    # of the other.
    assert all(a.conflicts_with(b) for a in first.sections for b in second.sections)


def test_free_day_removes_that_day_entirely(catalogs):
    courses = biggest(catalogs["6to"], 5)
    for candidate in iter_candidates(courses, [FreeDay(Day.SABADO)]):
        assert Day.SABADO not in candidate.days_used


def test_max_days_is_enforced_and_prunes(catalogs):
    courses = biggest(catalogs["6to"], 5)
    stats: list[SolveStats] = []
    found = list(iter_candidates(courses, [MaxDays(2)], stats=stats))
    for candidate in found:
        assert len(candidate.days_used) <= 2
    assert stats[0].pruned > 0, "MaxDays should cut partial assignments, not just leaves"
    # And it really is a subset of the unconstrained answer.
    unconstrained = {c.section_codes for c in iter_candidates(courses)}
    assert {c.section_codes for c in found} <= unconstrained


def test_max_onsite_days_ignores_online_sections(catalogs):
    courses = biggest(catalogs["6to"], 4)
    for candidate in iter_candidates(courses, [MaxOnsiteDays(1)]):
        assert len(candidate.onsite_days) <= 1


def test_latest_end_filters_sections(catalogs):
    courses = biggest(catalogs["6to"], 5)
    cutoff = time(21, 50)
    for candidate in iter_candidates(courses, [LatestEnd(cutoff)]):
        for meeting in candidate.meetings:
            assert meeting.end <= cutoff


def test_exclude_teacher_never_appears(catalogs):
    catalog = catalogs["6to"]
    victim = catalog.teachers()[0]
    courses = biggest(catalog, 5)
    for candidate in iter_candidates(courses, [ExcludeTeacher.of([victim])]):
        assert all(s.teacher != victim for s in candidate.sections)


def test_require_section_pins_one_course_only(catalogs):
    catalog = catalogs["4to"]
    pinned = catalog.course("DSY1104").sections[0].code
    found = list(iter_candidates(catalog.sorted_courses, [RequireSection.of([pinned])]))
    assert found
    for candidate in found:
        assert pinned in candidate.section_codes
        # Other courses still vary.
        assert len(candidate.sections) == len(catalog)


def test_exclude_section_shrinks_the_result_set(catalogs):
    catalog = catalogs["2do"]
    before = count_candidates(catalog.sorted_courses)
    dropped = next(iter(iter_candidates(catalog.sorted_courses))).sections[0].code
    after = count_candidates(catalog.sorted_courses, [ExcludeSection.of([dropped])])
    assert after < before


def test_impossible_filter_names_the_course(catalogs):
    catalog = catalogs["4to"]
    with pytest.raises(Unsatisfiable) as exc:
        list(iter_candidates(catalog.sorted_courses, [LatestEnd(time(0, 1))]))
    assert exc.value.course.sigla in str(exc.value)


def test_prepare_orders_most_constrained_first(catalogs):
    prepared = prepare(catalogs["6to"].sorted_courses)
    sizes = [len(course) for course in prepared]
    assert sizes == sorted(sizes)


def test_limit_stops_early(catalogs):
    courses = biggest(catalogs["6to"], 5)
    assert len(list(iter_candidates(courses, limit=7))) == 7


@pytest.mark.parametrize("scorer_name", sorted(SCORERS))
def test_top_n_returns_the_best_by_that_scorer(scorer_name, catalogs):
    scorer = SCORERS[scorer_name]
    courses = biggest(catalogs["6to"], 5)
    everything = list(iter_candidates(courses))
    best = top_n(everything, scorer, 5)

    assert len(best) == 5
    scores = [scorer.score(c) for c in best]
    assert scores == sorted(scores), "results must come back ordered"
    assert max(scores) <= min(scorer.score(c) for c in everything if c not in best)


def test_top_n_is_deterministic(catalogs):
    courses = biggest(catalogs["6to"], 5)
    scorer = SCORERS["fewest-days"]
    first = [c.section_codes for c in top_n(iter_candidates(courses), scorer, 10)]
    second = [c.section_codes for c in top_n(iter_candidates(courses), scorer, 10)]
    assert first == second


def test_fewest_days_actually_minimises_days(catalogs):
    courses = biggest(catalogs["6to"], 5)
    everything = list(iter_candidates(courses))
    best = top_n(everything, SCORERS["fewest-days"], 1)[0]
    assert len(best.days_used) == min(len(c.days_used) for c in everything)
