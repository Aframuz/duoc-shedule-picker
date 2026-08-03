# schedule-picker

Generates every conflict-free timetable from a DUOC course-section CSV export,
so you can compare real options instead of juggling sections by hand.

Give it the CSV, tick the courses you want, and it enumerates each combination
of sections that fits in a week — then ranks them by whatever you care about
(fewest days on campus, least dead time between classes, latest start).

## Install

Classmates without Python: grab the binary for your platform from the Releases
page. It has the known exports built in, so `schedule-picker 6to_semestre.csv`
works from anywhere.

From source:

```bash
uv venv
uv pip install -e ".[dev]"
```

## Use

```bash
# full-screen picker (default)
schedule-picker data/6to_semestre.csv

# what's in the file?
schedule-picker data/6to_semestre.csv --list-courses
schedule-picker data/6to_semestre.csv --validate

# scripted
schedule-picker data/6to_semestre.csv --headless \
    --electives 2 --with-course OCY1104 \
    --exclude-teacher "NOMBRE APELLIDO" \
    --free-day Vi --max-days 3 \
    --sort fewest-days --top 10 \
    --out output/ --format text,html,json
```

In the picker: `f` search, `space` tick a course, `+`/`-` how many electives,
`i` how many fit, `m` back to mandatory only, `c` constraints, `g` generate,
`e` export all four formats to `output/`.

## Mandatory and elective courses

The `Nivel` column says which is which: a number is the semester the course
belongs to and the course is compulsory; `Optativos` marks an elective. **The
mandatory courses for your semester are selected for you** — you only choose
among the electives. Files with no elective rows (2nd, 3rd, 4th semester) are
all-mandatory, so they behave exactly as they always did.

Different numbers mean different semesters and are not schedulable together. A
file covering several asks you to pick one with `--level`.

**How many electives actually fit?**

```console
$ schedule-picker data/6to_semestre.csv --headless --elective-report
Mandatory: DAY1102, IDY1102, IDY1103
Electives available: 18

  0 electives: 1 timetable(s) across 1 course combination(s)
  1 elective: 31 timetable(s) across 16 course combination(s)
  2 electives: 196 timetable(s) across 99 course combination(s)
  3 electives: no timetable fits

Most electives that fit: 2
```

It stops at the first count that fits nothing — electives only ever add
constraints, so no larger number can succeed.

**"I want OCY1104 specifically, plus one more, whatever fits."**

```bash
schedule-picker data/6to_semestre.csv --headless \
    --electives 2 --with-course OCY1104 --credits OCY1104=8 --sort most-credits
```

`--with-course` names an elective you insist on; it counts toward the
`--electives` total, so this asks for that one plus one free choice. Use
`--electives-min` / `--electives-max` for a range instead of an exact number.

**Credits.** No export carries a `Creditos` column yet, but the parser will pick
one up if it appears. Until then supply them yourself with `--credits SIGLA=N`
(repeatable) and use `--min-credits` to require a total or `--sort most-credits`
to prefer the heaviest timetable.

Constraints available in both modes: exclude a teacher or a section, pin a
section, keep a day free, earliest start, latest end, cap the number of days
(or the number of days physically on campus), cap idle time or the longest
single gap, online-only or in-person-only, restrict to one campus.

Rankings: `fewest-days`, `fewest-onsite-days`, `least-idle`, `latest-start`,
`earliest-finish`, `most-credits`, `most-electives`, and `balanced` (the
default — minimise days on campus, break ties on dead time).

## Supported exports

Any of the DUOC section exports. Headers vary between semesters, so columns are
matched by alias rather than position — `Asignatura` / `Nombre Asignatura` /
`Ramo` all resolve to the course name, `Sección` / `Codigo` to the section code.
Only the course name, section code and `Horario` are required; teacher, campus,
level and modality are used when present. `--validate` prints exactly which
column supplied which field.

Two things the format demands and the code handles:

- **Duplicate rows.** `6to_semestre.csv` repeats every meeting once per
  curriculum plan — 853 rows for 133 real meetings. They are de-duplicated on
  load; left in, a section would conflict with itself and never schedule.
- **Arbitrary times.** Meeting times are read as real intervals, not looked up
  in a table of known slots, so a new export with unfamiliar hours just works.
  The timetable grid is built from each result's own start and end times.

Files bundled in `data/` cover the 2nd, 3rd, 4th and 6th semesters.

## Development

```bash
uv run pytest              # 165 tests
uv run ruff check src tests
UPDATE_GOLDEN=1 uv run pytest   # after an intentional rendering change
```

Layout: `domain/` (days, meetings, sections, courses, candidates),
`parsing/` (schema detection, `Horario` grammar, loader), `solving/`
(backtracking search, constraints, scoring), `rendering/` (grid, text, HTML,
CSV, JSON), `tui/` (the picker), `cli.py`.

The integration suite pins the known-good result counts for the bundled
exports — 2do → 30 timetables, 3er → 5, 4to → 3. The first and third come from
the original implementation's committed output; all three are independently
confirmed by exhaustive brute force in `tests/integration/test_regression.py`.
If a change moves those numbers, the change is wrong.

## Build a binary

```bash
uv run pyinstaller packaging/schedule-picker.spec --noconfirm
```

Produces `dist/schedule-picker/`. Set `SCHEDULE_PICKER_ONEFILE=1` for a single
executable — good on Linux, but on Windows a onefile `.exe` reliably trips
antivirus heuristics, so the default there is a folder to zip. Windows builds
cannot be cross-compiled; `.github/workflows/release.yml` builds both platforms
on tag push.

## Licence

MIT.
