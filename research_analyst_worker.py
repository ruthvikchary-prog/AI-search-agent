"""Isolated real-CrewAI worker for the M1 Research Analyst."""

import json
import sys

from research_analyst import _run_crewai_research, _run_fallback_research


def main() -> None:
    payload = json.loads(sys.stdin.read())
    try:
        if payload.get("mode") == "fallback":
            output = _run_fallback_research(
                payload["topic"],
                payload["reason"],
                payload.get("preflight_ok", False),
            )
        else:
            output = _run_crewai_research(payload["topic"])
    except Exception as exc:
        with open(payload["result_path"], "w", encoding="utf-8") as result_file:
            json.dump({"error": f"{type(exc).__name__}: {exc}"}, result_file)
        return
    with open(payload["result_path"], "w", encoding="utf-8") as result_file:
        json.dump(output.model_dump(), result_file, ensure_ascii=False)


if __name__ == "__main__":
    main()
