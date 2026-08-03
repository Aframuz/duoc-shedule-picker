"""Core model: days, meetings, sections, courses, catalogs and candidates."""

from .candidate import ScheduleCandidate
from .catalog import Catalog
from .course import Course
from .day import Day
from .level import Kind, Level, LevelConflict, parse_level
from .section import Section, sigla_of
from .time_block import TimeBlock

__all__ = [
    "Catalog",
    "Course",
    "Day",
    "Kind",
    "Level",
    "LevelConflict",
    "ScheduleCandidate",
    "Section",
    "TimeBlock",
    "parse_level",
    "sigla_of",
]
