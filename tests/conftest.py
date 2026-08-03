from __future__ import annotations

from datetime import time
from pathlib import Path

import pytest

from schedule_picker.domain import Day, Section, TimeBlock
from schedule_picker.parsing import load_catalog

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# The real exports, kept as integration fixtures. Each header differs.
DATASETS = {
    "2do": DATA_DIR / "2do_semestre.csv",
    "3er": DATA_DIR / "3er_semestre.csv",
    "4to": DATA_DIR / "4to_semestre.csv",
    "6to": DATA_DIR / "6to_semestre.csv",
}


@pytest.fixture(params=sorted(DATASETS), ids=sorted(DATASETS))
def dataset_path(request) -> Path:
    return DATASETS[request.param]


@pytest.fixture(scope="session")
def catalogs() -> dict[str, object]:
    return {name: load_catalog(path)[0] for name, path in DATASETS.items()}


def block(day: Day, start: str, end: str) -> TimeBlock:
    """``block(Day.LUNES, "19:01", "20:20")`` — terse construction for tests."""

    def parse(value: str) -> time:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))

    return TimeBlock(day=day, start=parse(start), end=parse(end))


def section(code: str, *blocks: TimeBlock, name: str = "TEST", **kwargs) -> Section:
    return Section(code=code, course_name=name, meetings=tuple(blocks), **kwargs)
