"""Command line entry point.

With no ``--headless`` flag this launches the full-screen picker; with it, the
same machinery runs unattended so results can be scripted or diffed.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import time
from pathlib import Path

from . import __version__
from .domain.catalog import Catalog
from .domain.course import Course
from .domain.day import Day
from .domain.level import LevelConflict
from .parsing import LoadReport, SchemaError, load_catalog
from .rendering import RENDERERS
from .solving import (
    SCORERS,
    EarliestStart,
    ExcludeSection,
    ExcludeTeacher,
    FreeDay,
    LatestEnd,
    MaxDays,
    MaxGapMinutes,
    MaxIdleMinutes,
    MaxOnsiteDays,
    MinCredits,
    ModalityIs,
    RequireSection,
    Unsatisfiable,
    elective_report,
    find_blocking_pair,
    iter_candidates,
    ranked,
)

DEFAULT_TOP = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schedule-picker",
        description="Generate conflict-free timetables from a DUOC course-section CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  schedule-picker data/6to_semestre.csv\n"
            "  schedule-picker data/6to_semestre.csv --list-courses\n"
            "  schedule-picker data/4to_semestre.csv --headless --all-courses\n"
            "  schedule-picker data/6to_semestre.csv --headless \\\n"
            "      -c OCY1104 -c MLY0100 --free-day Sa --top 5 --format text,html\n"
        ),
    )
    parser.add_argument("csv", type=Path, nargs="?", help="the course-section export to read")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    modes = parser.add_argument_group("modes")
    modes.add_argument("--headless", action="store_true", help="skip the TUI and print results")
    modes.add_argument("--list-courses", action="store_true", help="list courses and exit")
    modes.add_argument("--validate", action="store_true", help="report parse problems and exit")

    selection = parser.add_argument_group("course selection")
    selection.add_argument(
        "-c", "--course", action="append", default=[], metavar="SIGLA",
        help="a course to include; repeatable. Default: this level's mandatory courses",
    )
    selection.add_argument(
        "--all-courses", action="store_true",
        help="require every course in the file, electives included",
    )
    selection.add_argument(
        "--level", type=int, metavar="N",
        help="which semester's mandatory courses to take (only needed if the file has several)",
    )

    electives = parser.add_argument_group("electives")
    electives.add_argument(
        "-e", "--electives", type=int, metavar="N",
        help="take exactly N electives on top of the mandatory courses",
    )
    electives.add_argument("--electives-min", type=int, metavar="N")
    electives.add_argument("--electives-max", type=int, metavar="N")
    electives.add_argument(
        "--with-course", action="append", default=[], metavar="SIGLA",
        help="an elective you definitely want; repeatable. Counts toward the total",
    )
    electives.add_argument(
        "--elective-report", action="store_true",
        help="show how many timetables fit 0, 1, 2, ... electives, then exit",
    )
    electives.add_argument(
        "--credits", action="append", default=[], metavar="SIGLA=N",
        help="what a course is worth, when the file does not say; repeatable",
    )
    electives.add_argument("--min-credits", type=int, metavar="N")

    limits = parser.add_argument_group("constraints")
    limits.add_argument("--exclude-teacher", action="append", default=[], metavar="NAME")
    limits.add_argument("--exclude-section", action="append", default=[], metavar="CODE")
    limits.add_argument(
        "--require-section", action="append", default=[], metavar="CODE",
        help="pin a course to this section",
    )
    limits.add_argument(
        "--free-day", action="append", default=[], metavar="DAY",
        help="keep a day clear (Lu, Ma, Mi, Ju, Vi, Sa)",
    )
    limits.add_argument("--earliest", metavar="HH:MM", help="no class may start before this")
    limits.add_argument("--latest", metavar="HH:MM", help="no class may end after this")
    limits.add_argument("--max-days", type=int, metavar="N")
    limits.add_argument("--max-onsite-days", type=int, metavar="N")
    limits.add_argument("--max-idle", type=int, metavar="MIN", help="total dead time cap")
    limits.add_argument("--max-gap", type=int, metavar="MIN", help="longest single gap cap")
    limits.add_argument(
        "--online-only", action="store_true", help="only ONLINE SINCRONA sections",
    )
    limits.add_argument("--onsite-only", action="store_true", help="only in-person sections")
    limits.add_argument("--campus", metavar="NAME", help="restrict to one campus")

    output = parser.add_argument_group("output")
    output.add_argument(
        "--sort", default="balanced", choices=sorted(SCORERS), help="ranking (default: balanced)",
    )
    output.add_argument(
        "--top", type=int, default=DEFAULT_TOP, metavar="N",
        help=f"how many to keep, 0 for all (default: {DEFAULT_TOP})",
    )
    output.add_argument(
        "--format", default="text", metavar="LIST",
        help="comma-separated: text, html, csv, json (default: text)",
    )
    output.add_argument(
        "--out", type=Path, metavar="DIR", help="write files here instead of stdout",
    )
    output.add_argument("--strict", action="store_true", help="fail on any unparseable row")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.csv is None:
        bundled = _bundled_datasets()
        parser.error(
            "a CSV file is required"
            + (f" (bundled: {', '.join(p.name for p in bundled)})" if bundled else "")
        )
    args.csv = _resolve_csv(args.csv)
    if not args.csv.exists():
        print(f"error: no such file: {args.csv}", file=sys.stderr)
        return 2
    if args.online_only and args.onsite_only:
        parser.error("--online-only and --onsite-only are mutually exclusive")

    try:
        catalog, report = load_catalog(args.csv, strict=args.strict, campus=args.campus)
        catalog = _apply_credits(catalog, args.credits)
    except (SchemaError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"error: {exc.args[0]}", file=sys.stderr)
        return 2

    if args.validate:
        return _validate(report)
    if args.list_courses:
        return _list_courses(catalog, report)
    if not args.headless:
        return _launch_tui(args, catalog, report)

    return _run_headless(args, catalog, report, parser)


# --------------------------------------------------------------------------


def _bundled_dir() -> Path | None:
    """Where the frozen build keeps the exports shipped with it, if anywhere."""
    root = getattr(sys, "_MEIPASS", None)
    if root is None:
        return None
    directory = Path(root) / "data"
    return directory if directory.is_dir() else None


def _bundled_datasets() -> list[Path]:
    directory = _bundled_dir()
    return sorted(directory.glob("*.csv")) if directory else []


def _resolve_csv(value: Path) -> Path:
    """Fall back to a bundled export when the given path does not exist.

    Lets someone with only the binary run ``schedule-picker 6to_semestre.csv``
    from any directory, rather than having to locate the file first.
    """
    if value.exists():
        return value
    directory = _bundled_dir()
    if directory is None:
        return value
    for candidate in (directory / value.name, directory / f"{value.name}.csv"):
        if candidate.exists():
            return candidate
    return value


def _validate(report: LoadReport) -> int:
    print(f"{report.source}: {report.summary()}")
    if report.schema:
        for field in report.schema.known_fields:
            print(f"  {field:<13} <- {report.schema.columns[field]}")
    for error in report.errors:
        print(f"  ! {error}", file=sys.stderr)
    return 1 if report.errors else 0


def _list_courses(catalog: Catalog, report: LoadReport) -> int:
    print(f"{report.source}: {len(catalog)} courses, {len(catalog.sections)} sections")
    width = max((len(c.sigla) for c in catalog), default=7)

    def show(course) -> None:
        plural = "section" if len(course) == 1 else "sections"
        worth = f"  [{course.credits} cr]" if course.credits is not None else ""
        print(f"  {course.sigla:<{width}}  {len(course):>2} {plural:<8}  {course.name}{worth}")

    try:
        levels = catalog.levels()
    except LevelConflict:
        levels = []

    for level in levels or [None]:
        mandatory = catalog.mandatory(level)
        if not mandatory:
            continue
        heading = f"Mandatory (level {level})" if level is not None else "Mandatory"
        print(f"\n{heading} — taken by default:")
        for course in mandatory:
            show(course)

    electives = catalog.electives()
    if electives:
        print(f"\nElectives — choose among these ({len(electives)}):")
        for course in electives:
            show(course)
    return 0


def _launch_tui(args: argparse.Namespace, catalog: Catalog, report: LoadReport) -> int:
    try:
        from .tui.app import SchedulePickerApp
    except ImportError:  # pragma: no cover - only when textual is absent
        print(
            "error: the interactive picker needs textual installed.\n"
            "       re-run with --headless, or: pip install textual",
            file=sys.stderr,
        )
        return 2
    SchedulePickerApp(catalog=catalog, report=report).run()
    return 0


def _run_headless(
    args: argparse.Namespace,
    catalog: Catalog,
    report: LoadReport,
    parser: argparse.ArgumentParser,
) -> int:
    try:
        required, electives = _resolve_selection(args, catalog)
        low, high = _elective_bounds(args, len(electives))
        filters = _build_filters(args)
    except LevelConflict as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (KeyError, ValueError) as exc:
        # str() on a KeyError reprs its argument, adding stray quotes.
        print(f"error: {exc.args[0] if isinstance(exc, KeyError) else exc}", file=sys.stderr)
        return 2

    if report.errors:
        print(f"warning: skipped {len(report.errors)} unparseable row(s)", file=sys.stderr)

    if args.elective_report:
        return _print_elective_report(required, electives, filters)

    try:
        candidates = list(
            iter_candidates(
                required,
                filters,
                electives=electives,
                electives_min=low,
                electives_max=high,
            )
        )
    except Unsatisfiable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not candidates:
        _explain_empty(required, electives, low)
        return 1

    scorer = SCORERS[args.sort]
    scored = list(ranked(candidates, scorer))
    if args.top > 0:
        scored = scored[: args.top]
    scores = [score for score, _ in scored]
    best = [candidate for _, candidate in scored]

    print(
        f"{len(candidates)} timetable(s) found; showing {len(best)} by {scorer.name}",
        file=sys.stderr,
    )
    _emit(args, best, scores)
    return 0


def _resolve_selection(
    args: argparse.Namespace,
    catalog: Catalog,
) -> tuple[list[Course], list[Course]]:
    """Work out what must be taken and what may be.

    Default is the level's mandatory courses, which for a file with no elective
    rows is every course in it — so the older exports behave exactly as before
    without anyone passing a flag.
    """
    if args.all_courses:
        return catalog.sorted_courses, []

    if args.course:
        required = catalog.select(args.course)
    else:
        required = catalog.mandatory(args.level)
        if not required and not args.with_course:
            raise ValueError(
                "this file has no mandatory courses; pick some with --course "
                "or --with-course"
            )

    # A wanted elective is simply promoted to required; it still counts toward
    # the elective total, which is what "I want X plus one more" means.
    wanted = catalog.select(args.with_course) if args.with_course else []
    chosen = {course.sigla for course in required}
    required = list(required) + [c for c in wanted if c.sigla not in chosen]

    taken = {course.sigla for course in required}
    electives = [c for c in catalog.electives() if c.sigla not in taken]
    return required, electives


def _elective_bounds(args: argparse.Namespace, available: int) -> tuple[int | None, int | None]:
    """Turn the elective flags into min/max, accounting for promoted courses.

    ``--with-course`` moves an elective into the required set, so a request for
    two electives one of which is named needs only one more from the pool.
    """
    if args.electives is not None and (
        args.electives_min is not None or args.electives_max is not None
    ):
        raise ValueError("--electives cannot be combined with --electives-min/--electives-max")

    promoted = len(args.with_course)

    if args.electives is not None:
        remaining = args.electives - promoted
        if remaining < 0:
            raise ValueError(
                f"--electives {args.electives} is fewer than the "
                f"{promoted} course(s) named with --with-course"
            )
        return remaining, remaining

    low = None if args.electives_min is None else max(0, args.electives_min - promoted)
    high = None if args.electives_max is None else args.electives_max - promoted
    if high is not None and high < 0:
        raise ValueError(
            f"--electives-max {args.electives_max} is fewer than the "
            f"{promoted} course(s) named with --with-course"
        )
    # Nothing asked for means nothing extra: the mandatory set alone.
    if low is None and high is None:
        return 0, 0
    del available
    return low, high


def _apply_credits(catalog: Catalog, pairs: list[str]) -> Catalog:
    credits: dict[str, int] = {}
    for pair in pairs:
        sigla, sep, value = pair.partition("=")
        if not sep or not value.strip().lstrip("-").isdigit():
            raise ValueError(f"--credits expects SIGLA=N, got {pair!r}")
        credits[sigla.strip().upper()] = int(value)
    return catalog.with_credits(credits) if credits else catalog


def _print_elective_report(
    required: list[Course],
    electives: list[Course],
    filters: list[object],
) -> int:
    if not electives:
        print("This file has no electives.", file=sys.stderr)
        return 1

    required_names = ", ".join(course.sigla for course in required) or "(none)"
    print(f"Mandatory: {required_names}")
    print(f"Electives available: {len(electives)}\n")

    tallies = elective_report(required, electives, filters)
    for tally in tallies:
        print(f"  {tally}")

    best = max((t.count for t in tallies if t.schedules), default=None)
    print()
    if best is None:
        print("Not even the mandatory courses fit together.")
        return 1
    print(f"Most electives that fit: {best}")
    return 0


def _build_filters(args: argparse.Namespace) -> list[object]:
    filters: list[object] = []

    if args.exclude_teacher:
        filters.append(ExcludeTeacher.of(args.exclude_teacher))
    if args.exclude_section:
        filters.append(ExcludeSection.of(args.exclude_section))
    if args.require_section:
        filters.append(RequireSection.of(args.require_section))
    for value in args.free_day:
        filters.append(FreeDay(_parse_day(value)))
    if args.earliest:
        filters.append(EarliestStart(_parse_time(args.earliest, "--earliest")))
    if args.latest:
        filters.append(LatestEnd(_parse_time(args.latest, "--latest")))
    if args.max_days is not None:
        filters.append(MaxDays(args.max_days))
    if args.max_onsite_days is not None:
        filters.append(MaxOnsiteDays(args.max_onsite_days))
    if args.max_idle is not None:
        filters.append(MaxIdleMinutes(args.max_idle))
    if args.max_gap is not None:
        filters.append(MaxGapMinutes(args.max_gap))
    if args.online_only:
        filters.append(ModalityIs(online=True))
    if args.onsite_only:
        filters.append(ModalityIs(online=False))
    if args.min_credits is not None:
        filters.append(MinCredits(args.min_credits))

    return filters


def _parse_day(value: str) -> Day:
    try:
        return Day.from_code(value)
    except ValueError:
        pass
    for day in Day:
        if day.label.casefold() == value.strip().casefold():
            return day
    raise ValueError(f"unknown day {value!r}; use one of: {', '.join(d.code for d in Day)}")


def _parse_time(value: str, flag: str) -> time:
    parts = value.strip().split(":")
    try:
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except (ValueError, IndexError):
        raise ValueError(f"{flag} expects HH:MM, got {value!r}") from None


def _explain_empty(required, electives, low) -> None:
    print("No timetable fits those courses.", file=sys.stderr)

    pair = find_blocking_pair(required)
    if pair:
        first, second = pair
        print(
            f"  {first.sigla} ({first.name}) and {second.sigla} ({second.name}) clash "
            "in every combination of their sections.",
            file=sys.stderr,
        )
        return

    # The compulsory set is fine on its own, so the electives asked for are what
    # does not fit. Say how many would.
    if electives and low:
        tallies = elective_report(required, electives, max_count=low)
        fitting = [t.count for t in tallies if t.schedules]
        if fitting:
            print(
                f"  The mandatory courses fit, but not with {low} elective(s). "
                f"The most that fit is {max(fitting)} — try --electives {max(fitting)}.",
                file=sys.stderr,
            )
            return

    print(
        "  No single pair is to blame — the clash involves three or more "
        "courses, or your constraints are too tight.",
        file=sys.stderr,
    )


def _emit(args: argparse.Namespace, candidates, scores) -> None:
    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    unknown = [f for f in formats if f not in RENDERERS]
    if unknown:
        print(f"error: unknown format(s): {', '.join(unknown)}", file=sys.stderr)
        raise SystemExit(2)

    for name in formats:
        renderer = RENDERERS[name]()
        text = renderer.render_all(candidates, scores)
        if args.out is None:
            if len(formats) > 1:
                print(f"----- {name} -----")
            print(text, end="" if text.endswith("\n") else "\n")
        else:
            args.out.mkdir(parents=True, exist_ok=True)
            target = args.out / f"{args.csv.stem}.{renderer.extension}"
            target.write_text(text, encoding="utf-8")
            print(f"wrote {target}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
