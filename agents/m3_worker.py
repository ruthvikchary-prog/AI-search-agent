"""Isolated worker for the single M3 CrewAI writing task."""

import json
import sys

from agents.report_writer import _run_crewai_writer_local
from models.schemas import ResearchSource


def main() -> None:
    payload = json.loads(sys.stdin.read())
    sources = [ResearchSource(**source) for source in payload.get("sources", [])]
    report, status = _run_crewai_writer_local(
        payload.get("topic", "Academic Research"),
        sources,
        payload.get("feedback"),
    )
    print(json.dumps({
        "report": report.model_dump(mode="json") if report else None,
        "status": status,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
