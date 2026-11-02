"""
agents/research_analyst.py - Module 1: Research Analyst Agent
=============================================================================
Owner: Karthik (23QM1A66B7)
Course: Professional Elective - IV (Agentic AI) | Batch 6
Institution: KG Reddy College of Engineering & Technology

Role:
  - Information collection, web discovery & sub-topic decomposition.
  - Academic web search (Serper / DuckDuckGo / arXiv repository).
  - Facts, statistics, and domain trends extraction.
  - Outputs structured research data and formal search metrics.

Standalone Usage:
    python agents/research_analyst.py "Agentic AI"

Output:
    outputs/m1_research.json
=============================================================================
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Union, Dict, Any

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from research_analyst import (
    Source,
    Finding,
    ResearchOutput,
    run_research_analyst,
    compute_metrics
)

from config import Config

OUTPUTS_DIR = Config.OUTPUTS_DIR
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
M1_OUTPUT_FILE = OUTPUTS_DIR / "m1_research.json"


def run(input_data: Union[str, Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main entry point for Module 1 - Research Analyst Agent.
    
    Args:
        input_data: String topic or dictionary with {"topic": "..."}.
                   If None, defaults to topic from existing M1 output or default topic.
    Returns:
        dict: Complete research dossier including sources, findings, metrics, and owner metadata.
    """
    start_time = time.time()
    
    # Resolve topic
    topic = ""
    if isinstance(input_data, str) and input_data.strip():
        topic = input_data.strip()
    elif isinstance(input_data, dict):
        topic = input_data.get("topic", "").strip()

    if not topic:
        raise ValueError("A research topic is required.")

    print(f"\n[M1 START] Research Analyst Agent (Karthik) starting for topic: '{topic}'")
    print(f"  -> Initiating academic search across Serper / DuckDuckGo / arXiv...")
    print("  -> Search request started.")

    # Execute research analyst workflow
    research_output: ResearchOutput = run_research_analyst(topic)
    analyst_metrics = compute_metrics(research_output)

    elapsed_time = round(time.time() - start_time, 2)

    # Compile structured hand-off payload
    result = {
        "owner": "Karthik (23QM1A66B7)",
        "module": "Module 1 - Research Analyst Agent",
        "topic": topic,
        "subtopics": research_output.subtopics,
        "sources": [s.model_dump() for s in research_output.sources],
        "findings": [f.model_dump() for f in research_output.findings],
        "execution_mode": research_output.execution_mode,
        "fallback_reason": research_output.fallback_reason,
        "provider": research_output.provider,
        "model": research_output.model,
        "llm_preflight": research_output.preflight_ok,
        "preflight_ok": research_output.preflight_ok,
        "metrics": analyst_metrics,
        "time_taken_seconds": elapsed_time,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Save to outputs/m1_research.json
    with open(M1_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[M1 DONE - {elapsed_time}s] Discovered {len(research_output.sources)} sources across {len(research_output.subtopics)} subtopics.")
    print(f"  -> Execution mode: {research_output.execution_mode}")
    print(f"  -> Search Relevance: {analyst_metrics.get('search_relevance_percent', 0)}%")
    print(f"  -> Information Coverage: {analyst_metrics.get('information_coverage_percent', 0)}%")
    print(f"  -> Output saved to: {M1_OUTPUT_FILE}\n")

    return result


if __name__ == "__main__":
    cli_topic = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else None
    run(cli_topic)
