"""Machine-readable output: CSV for spreadsheets, JSON for everything else."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..domain.candidate import ScheduleCandidate

CSV_COLUMNS = (
    "opcion",
    "puntaje",
    "sigla",
    "seccion",
    "asignatura",
    "nivel",
    "creditos",
    "docente",
    "sede",
    "modalidad",
    "dia",
    "inicio",
    "fin",
)


@dataclass(frozen=True)
class CsvRenderer:
    """One row per meeting, so the result opens cleanly in a spreadsheet."""

    extension = "csv"

    def render_all(
        self,
        candidates: Sequence[ScheduleCandidate] | Iterable[ScheduleCandidate],
        scores: Sequence[float] | None = None,
    ) -> str:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)

        for index, candidate in enumerate(candidates, start=1):
            score = scores[index - 1] if scores is not None and index <= len(scores) else ""
            for section in sorted(candidate.sections, key=lambda s: s.code):
                for meeting in section.meetings:
                    writer.writerow(
                        [
                            index,
                            score,
                            section.sigla,
                            section.code,
                            section.course_name,
                            str(section.parsed_level),
                            section.credits if section.credits is not None else "",
                            section.teacher or "",
                            section.campus or "",
                            section.modality or "",
                            meeting.day.label,
                            f"{meeting.start:%H:%M}",
                            f"{meeting.end:%H:%M}",
                        ]
                    )
        return buffer.getvalue()

    def render(self, candidate: ScheduleCandidate, title: str = "") -> str:
        return self.render_all([candidate])


@dataclass(frozen=True)
class JsonRenderer:
    """Full structured dump, including the derived metrics used for ranking."""

    extension = "json"

    indent: int = 2

    def render_all(
        self,
        candidates: Sequence[ScheduleCandidate] | Iterable[ScheduleCandidate],
        scores: Sequence[float] | None = None,
    ) -> str:
        payload = []
        for index, candidate in enumerate(candidates, start=1):
            entry = {
                "opcion": index,
                "dias": [day.label for day in sorted(candidate.days_used)],
                "dias_presenciales": [day.label for day in sorted(candidate.onsite_days)],
                "minutos_clase": candidate.total_class_minutes,
                "minutos_libres": candidate.idle_minutes,
                "creditos": candidate.total_credits,
                "optativos": [s.sigla for s in candidate.electives],
                "secciones": [
                    {
                        "sigla": section.sigla,
                        "seccion": section.code,
                        "asignatura": section.course_name,
                        "nivel": str(section.parsed_level),
                        "creditos": section.credits,
                        "docente": section.teacher,
                        "sede": section.campus,
                        "modalidad": section.modality,
                        "bloques": [
                            {
                                "dia": meeting.day.label,
                                "inicio": f"{meeting.start:%H:%M}",
                                "fin": f"{meeting.end:%H:%M}",
                            }
                            for meeting in section.meetings
                        ],
                    }
                    for section in sorted(candidate.sections, key=lambda s: s.code)
                ],
            }
            if scores is not None and index <= len(scores):
                entry["puntaje"] = scores[index - 1]
            payload.append(entry)

        return json.dumps(
            {"total": len(payload), "horarios": payload},
            ensure_ascii=False,
            indent=self.indent,
        ) + "\n"

    def render(self, candidate: ScheduleCandidate, title: str = "") -> str:
        return self.render_all([candidate])
