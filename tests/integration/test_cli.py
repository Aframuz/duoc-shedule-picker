"""The command line, driven end to end."""

from __future__ import annotations

import json

import pytest

from schedule_picker.cli import main

from ..conftest import DATASETS


def run(capsys, *argv) -> tuple[int, str, str]:
    code = main([str(a) for a in argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_validate_reports_the_resolved_columns(capsys):
    code, out, _ = run(capsys, DATASETS["6to"], "--validate")
    assert code == 0
    assert "853 rows, 133 meetings, 720 duplicates dropped" in out
    assert "course_name   <- Nombre Asignatura" in out
    assert "section_code  <- Sección" in out


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_validate_accepts_every_bundled_export(name, capsys):
    code, _, _ = run(capsys, DATASETS[name], "--validate")
    assert code == 0


def test_list_courses(capsys):
    code, out, _ = run(capsys, DATASETS["6to"], "--list-courses")
    assert code == 0
    assert "21 courses, 63 sections" in out
    assert "OCY1101   8 sections" in out
    assert "BCY0010   1 section " in out


def test_headless_reproduces_the_legacy_counts(capsys):
    for name, expected in (("2do", 30), ("3er", 5), ("4to", 3)):
        code, _, err = run(capsys, DATASETS[name], "--headless", "--all-courses", "--top", "0")
        assert code == 0
        assert f"{expected} timetable(s) found" in err


def test_headless_writes_every_requested_format(tmp_path, capsys):
    code, _, err = run(
        capsys, DATASETS["4to"], "--headless", "--all-courses",
        "--format", "text,html,csv,json", "--out", tmp_path,
    )
    assert code == 0
    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == ["4to_semestre.csv", "4to_semestre.html",
                       "4to_semestre.json", "4to_semestre.txt"]
    assert "wrote" in err
    payload = json.loads((tmp_path / "4to_semestre.json").read_text(encoding="utf-8"))
    assert payload["total"] == 3


def test_top_limits_the_output(tmp_path, capsys):
    code, _, err = run(
        capsys, DATASETS["2do"], "--headless", "--all-courses",
        "--top", "4", "--format", "json", "--out", tmp_path,
    )
    assert code == 0
    assert "30 timetable(s) found; showing 4" in err
    payload = json.loads((tmp_path / "2do_semestre.json").read_text(encoding="utf-8"))
    assert payload["total"] == 4


def test_constraints_narrow_the_result(tmp_path, capsys):
    def count(*extra):
        run(capsys, DATASETS["6to"], "--headless", "-c", "OCY1101", "-c", "OCY1105",
            "-c", "OCY1104", "-c", "OCY1102", "-c", "DLY0100",
            "--top", "0", "--format", "json", "--out", tmp_path, *extra)
        return json.loads((tmp_path / "6to_semestre.json").read_text(encoding="utf-8"))["total"]

    everything = count()
    constrained = count("--max-days", "3")
    assert 0 < constrained < everything


def test_free_day_is_respected(tmp_path, capsys):
    code, _, _ = run(
        capsys, DATASETS["6to"], "--headless", "-c", "OCY1101", "-c", "DLY0100",
        "--free-day", "Sa", "--top", "0", "--format", "json", "--out", tmp_path,
    )
    assert code == 0
    payload = json.loads((tmp_path / "6to_semestre.json").read_text(encoding="utf-8"))
    assert payload["total"] > 0
    for entry in payload["horarios"]:
        assert "Sabado" not in entry["dias"]


def test_empty_result_names_the_blocking_pair(capsys):
    code, _, err = run(capsys, DATASETS["6to"], "--headless", "--all-courses")
    assert code == 1
    assert "No timetable fits" in err
    assert "clash in every combination" in err


def test_impossible_constraint_names_the_course(capsys):
    code, _, err = run(
        capsys, DATASETS["4to"], "--headless", "--all-courses", "--latest", "00:01"
    )
    assert code == 1
    assert "no sections of" in err


def test_unknown_sigla_is_reported_without_repr_quotes(capsys):
    code, _, err = run(capsys, DATASETS["6to"], "--headless", "-c", "NOPE")
    assert code == 2
    assert "unknown course sigla(s): NOPE" in err
    assert "'unknown" not in err


def test_missing_file(capsys):
    code, _, err = run(capsys, "does/not/exist.csv", "--validate")
    assert code == 2
    assert "no such file" in err


def test_unknown_format(capsys):
    with pytest.raises(SystemExit) as exc:
        run(capsys, DATASETS["4to"], "--headless", "--all-courses", "--format", "pdf")
    assert exc.value.code == 2


def test_no_selection_defaults_to_the_mandatory_courses(capsys):
    """For a file with no electives that is every course, so the old counts hold."""
    for name, expected in (("2do", 30), ("3er", 5), ("4to", 3)):
        code, _, err = run(capsys, DATASETS[name], "--headless", "--top", "0")
        assert code == 0
        assert f"{expected} timetable(s) found" in err


def test_6to_defaults_to_mandatory_only(capsys):
    code, _, err = run(capsys, DATASETS["6to"], "--headless", "--top", "0")
    assert code == 0
    assert "1 timetable(s) found" in err


def test_online_and_onsite_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit):
        run(capsys, DATASETS["6to"], "--headless", "--all-courses",
            "--online-only", "--onsite-only")


def test_bad_day_and_bad_time_are_rejected(capsys):
    code, _, err = run(capsys, DATASETS["4to"], "--headless", "--all-courses",
                       "--free-day", "Funday")
    assert code == 2 and "unknown day" in err

    code, _, err = run(capsys, DATASETS["4to"], "--headless", "--all-courses",
                       "--latest", "half past nine")
    assert code == 2 and "expects HH:MM" in err


@pytest.mark.parametrize("sort", ["fewest-days", "least-idle", "balanced", "latest-start"])
def test_every_sort_option_runs(sort, tmp_path, capsys):
    code, _, _ = run(
        capsys, DATASETS["2do"], "--headless", "--all-courses",
        "--sort", sort, "--format", "json", "--out", tmp_path,
    )
    assert code == 0


# --------------------------------------------------------------------------
# Electives
# --------------------------------------------------------------------------


def total(tmp_path, capsys, *argv) -> int:
    run(capsys, DATASETS["6to"], "--headless", "--top", "0",
        "--format", "json", "--out", tmp_path, *argv)
    return json.loads((tmp_path / "6to_semestre.json").read_text(encoding="utf-8"))["total"]


def test_elective_report_counts_and_stops_at_zero(capsys):
    code, out, _ = run(capsys, DATASETS["6to"], "--headless", "--elective-report")
    assert code == 0
    assert "Mandatory: DAY1102, IDY1102, IDY1103" in out
    assert "0 electives: 1 timetable(s) across 1 course combination(s)" in out
    assert "1 elective: 31 timetable(s) across 16 course combination(s)" in out
    assert "2 electives: 196 timetable(s) across 99 course combination(s)" in out
    assert "3 electives: no timetable fits" in out
    assert "Most electives that fit: 2" in out
    # Stops rather than grinding through 4..18.
    assert "4 electives" not in out


def test_elective_report_needs_electives(capsys):
    code, _, err = run(capsys, DATASETS["4to"], "--headless", "--elective-report")
    assert code == 1
    assert "no electives" in err


@pytest.mark.parametrize(("count", "expected"), [(0, 1), (1, 31), (2, 196)])
def test_exact_elective_counts(count, expected, tmp_path, capsys):
    assert total(tmp_path, capsys, "--electives", str(count)) == expected


def test_too_many_electives_says_how_many_fit(capsys):
    code, _, err = run(capsys, DATASETS["6to"], "--headless", "--electives", "3")
    assert code == 1
    assert "The most that fit is 2" in err


def test_with_course_pins_an_elective_and_counts_toward_the_total(tmp_path, capsys):
    """The headline case: mandatory + OCY1104 + one more, whatever fits."""
    run(capsys, DATASETS["6to"], "--headless", "--top", "0", "--format", "json",
        "--out", tmp_path, "--electives", "2", "--with-course", "OCY1104")
    payload = json.loads((tmp_path / "6to_semestre.json").read_text(encoding="utf-8"))
    assert payload["total"] == 37
    for entry in payload["horarios"]:
        assert "OCY1104" in entry["optativos"]
        assert len(entry["optativos"]) == 2


def test_with_course_alone_takes_just_that_one(tmp_path, capsys):
    """Naming one elective and asking for one total means no extra is drawn.

    Three of OCY1104's six sections clear the mandatory block.
    """
    assert total(tmp_path, capsys, "--with-course", "OCY1104", "--electives", "1") == 3


def test_electives_fewer_than_the_named_courses_is_rejected(capsys):
    code, _, err = run(capsys, DATASETS["6to"], "--headless",
                       "--electives", "1", "--with-course", "OCY1104",
                       "--with-course", "MLY0100")
    assert code == 2
    assert "fewer than the 2 course(s)" in err


def test_electives_range(tmp_path, capsys):
    at_most_two = total(tmp_path, capsys, "--electives-max", "2")
    assert at_most_two == 1 + 31 + 196
    at_least_one = total(tmp_path, capsys, "--electives-min", "1", "--electives-max", "2")
    assert at_least_one == 31 + 196


def test_electives_and_range_flags_are_mutually_exclusive(capsys):
    code, _, err = run(capsys, DATASETS["6to"], "--headless",
                       "--electives", "1", "--electives-max", "2")
    assert code == 2
    assert "cannot be combined" in err


def test_credits_and_min_credits(tmp_path, capsys):
    payload_total = total(
        tmp_path, capsys, "--electives", "1",
        "--credits", "OCY1104=8", "--credits", "MLY0100=4", "--min-credits", "8",
    )
    assert payload_total > 0
    payload = json.loads((tmp_path / "6to_semestre.json").read_text(encoding="utf-8"))
    for entry in payload["horarios"]:
        assert entry["creditos"] >= 8
        assert "OCY1104" in entry["optativos"]


def test_credits_reject_bad_syntax_and_unknown_courses(capsys):
    code, _, err = run(capsys, DATASETS["6to"], "--headless", "--credits", "OCY1104")
    assert code == 2 and "expects SIGLA=N" in err

    code, _, err = run(capsys, DATASETS["6to"], "--headless", "--credits", "NOPE=3")
    assert code == 2 and "unknown course sigla(s): NOPE" in err


def test_list_courses_separates_mandatory_from_electives(capsys):
    code, out, _ = run(capsys, DATASETS["6to"], "--list-courses")
    assert code == 0
    assert "Mandatory (level 6) — taken by default:" in out
    assert "Electives — choose among these (18):" in out
    assert out.index("DAY1102") < out.index("Electives")


def test_list_courses_on_a_file_without_electives(capsys):
    code, out, _ = run(capsys, DATASETS["4to"], "--list-courses")
    assert code == 0
    assert "Mandatory (level 4)" in out
    assert "Electives" not in out


def test_all_courses_still_requires_everything(capsys):
    """The old flag keeps its old meaning: every course compulsory."""
    code, _, err = run(capsys, DATASETS["6to"], "--headless", "--all-courses")
    assert code == 1
    assert "clash in every combination" in err
