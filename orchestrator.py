"""Multi-Agent Academic Research Assistant Orchestrator.

Sequentially coordinates the 5-stage pipeline:
  1. [M1] Research Analyst (Karthik - 23QM1A66B7) -> outputs/m1_research.json
  2. [M2] Source Reviewer (Rahul - 23QM1A66A2)     -> outputs/m2_review.json
  3. [M3] Report Writer (Ruthvik - 23QM1A6698 & Kunal - 23QM1A6677) -> outputs/m3_report.json
  4. [EVALUATION] 8-Dimension Quality Gate          -> outputs/evaluation.json
  5. [FINAL] Final Synthesis & Publication Agent    -> outputs/final_report.json & outputs/final_report.pdf

If any agent fails, execution halts immediately with diagnostic error reporting.
"""

import sys
import time
import json
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import agent entry points
from agents.research_analyst import run as run_m1
from agents.source_reviewer import run as run_m2
from agents.report_writer import run as run_m3
from agents.evaluation import run as run_evaluation
from agents.final_agent import run as run_final


def run_orchestrator(topic: str = "Agentic AI: Autonomous Intelligence for Complex Goals") -> Dict[str, Any]:
    """Execute the full multi-agent pipeline in strict sequential order."""
    outputs_dir = ROOT_DIR / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 78)
    print(" 🚀 MULTI-AGENT ACADEMIC RESEARCH ASSISTANT — MASTER ORCHESTRATOR")
    print("=" * 78)
    print(f" Research Topic : {topic}")
    print(f" Target Outputs  : {outputs_dir}")
    print("=" * 78 + "\n")

    overall_start_time = time.perf_counter()
    pipeline_results: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # STAGE 1: [M1] Research Analyst Agent (Karthik - 23QM1A66B7)
    # -------------------------------------------------------------------------
    stage_name = "M1: Research Analyst"
    print(f"[M1 START] Research Analyst Agent (Karthik - 23QM1A66B7)...")
    m1_start = time.perf_counter()
    try:
        m1_result = run_m1({"topic": topic})
        m1_duration = round(time.perf_counter() - m1_start, 2)
        pipeline_results["m1"] = m1_result
        print(f"[M1 DONE - {m1_duration:.2f}s] Gathered {len(m1_result.get('sources', []))} candidate sources -> outputs/m1_research.json\n")
    except Exception as e:
        m1_duration = round(time.perf_counter() - m1_start, 2)
        print(f"\n[!] [M1 FAILED - {m1_duration:.2f}s] Error in {stage_name}: {e}")
        traceback.print_exc()
        print("\n[!] Pipeline stopped due to fatal error in Module 1.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STAGE 2: [M2] Source Reviewer Agent (Rahul - 23QM1A66A2)
    # -------------------------------------------------------------------------
    stage_name = "M2: Source Reviewer"
    print(f"[M2 START] Source Reviewer Agent (Rahul - 23QM1A66A2)...")
    m2_start = time.perf_counter()
    try:
        m2_result = run_m2(m1_result)
        m2_duration = round(time.perf_counter() - m2_start, 2)
        pipeline_results["m2"] = m2_result
        verified_count = m2_result.get("verified_sources_count", len(m2_result.get("verified_sources", [])))
        print(f"[M2 DONE - {m2_duration:.2f}s] Verified {verified_count} sources (Faithfulness & Tiering verified) -> outputs/m2_review.json\n")
    except Exception as e:
        m2_duration = round(time.perf_counter() - m2_start, 2)
        print(f"\n[!] [M2 FAILED - {m2_duration:.2f}s] Error in {stage_name}: {e}")
        traceback.print_exc()
        print("\n[!] Pipeline stopped due to fatal error in Module 2.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STAGE 3: [M3] Academic Report Writer (Ruthvik - 23QM1A6698 & Kunal - 23QM1A6677)
    # -------------------------------------------------------------------------
    stage_name = "M3: Academic Report Writer"
    print(f"[M3 START] Academic Report Writer (Ruthvik - 23QM1A6698 & Kunal - 23QM1A6677)...")
    m3_start = time.perf_counter()
    try:
        m3_result = run_m3(m2_result)
        m3_duration = round(time.perf_counter() - m3_start, 2)
        pipeline_results["m3"] = m3_result
        word_count = m3_result.get("word_count", 0)
        sections_count = len(m3_result.get("sections", []))
        print(f"[M3 DONE - {m3_duration:.2f}s] Synthesized {sections_count} sections ({word_count} words) with IEEE citations -> outputs/m3_report.json\n")
    except Exception as e:
        m3_duration = round(time.perf_counter() - m3_start, 2)
        print(f"\n[!] [M3 FAILED - {m3_duration:.2f}s] Error in {stage_name}: {e}")
        traceback.print_exc()
        print("\n[!] Pipeline stopped due to fatal error in Module 3.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STAGE 4: [EVALUATION] 8-Dimension Quality Gate
    # -------------------------------------------------------------------------
    stage_name = "Evaluation Quality Gate"
    print(f"[EVALUATION START] 8-Dimension Academic Quality Gate...")
    eval_start = time.perf_counter()
    try:
        eval_payload = {
            "report": m3_result,
            "sources": m2_result.get("verified_sources", [])
        }
        eval_result = run_evaluation(eval_payload)
        eval_duration = round(time.perf_counter() - eval_start, 2)
        pipeline_results["evaluation"] = eval_result
        score = eval_result.get("overall_score", 0.0)
        grade = eval_result.get("grade", "N/A")
        status_str = "PASSED" if eval_result.get("passed", False) else "WARNING/FAILED"
        print(f"[EVALUATION DONE - {eval_duration:.2f}s] Score: {score}/100.0 (Grade: {grade}) [{status_str}] -> outputs/evaluation.json\n")
    except Exception as e:
        eval_duration = round(time.perf_counter() - eval_start, 2)
        print(f"\n[!] [EVALUATION FAILED - {eval_duration:.2f}s] Error in {stage_name}: {e}")
        traceback.print_exc()
        print("\n[!] Pipeline stopped due to fatal error in Evaluation Gate.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STAGE 5: [FINAL] Final Synthesis & Publication Agent
    # -------------------------------------------------------------------------
    stage_name = "Final Synthesis & PDF Publication"
    print(f"[FINAL START] Final Synthesis & Publication Agent...")
    final_start = time.perf_counter()
    try:
        final_payload = {
            "m1": m1_result,
            "m2": m2_result,
            "m3": m3_result,
            "evaluation": eval_result
        }
        final_result = run_final(final_payload)
        final_duration = round(time.perf_counter() - final_start, 2)
        pipeline_results["final"] = final_result
        pdf_pages = final_result.get("publication_metrics", {}).get("pdf_pages", 0)
        print(f"[FINAL DONE - {final_duration:.2f}s] Generated IEEE Access Publication PDF ({pdf_pages} pages) -> outputs/final_report.pdf & outputs/final_report.json\n")
    except Exception as e:
        final_duration = round(time.perf_counter() - final_start, 2)
        print(f"\n[!] [FINAL FAILED - {final_duration:.2f}s] Error in {stage_name}: {e}")
        traceback.print_exc()
        print("\n[!] Pipeline stopped due to fatal error in Final Agent.")
        sys.exit(1)

    total_pipeline_time = round(time.perf_counter() - overall_start_time, 2)

    # -------------------------------------------------------------------------
    # FINAL RECAP BANNER
    # -------------------------------------------------------------------------
    print("=" * 78)
    print(" 🎉 ALL 5 AGENTS COMPLETED SUCCESSFULLY — END-TO-END PIPELINE FINISHED")
    print("=" * 78)
    print(f"{'Stage / Agent':<35} {'Owner / Team':<28} {'Duration':<12}")
    print("-" * 78)
    print(f"{'1. Research Analyst (M1)':<35} {'Karthik (23QM1A66B7)':<28} {m1_duration:<10.2f}s")
    print(f"{'2. Source Reviewer (M2)':<35} {'Rahul (23QM1A66A2)':<28} {m2_duration:<10.2f}s")
    print(f"{'3. Academic Writer (M3)':<35} {'Ruthvik & Kunal':<28} {m3_duration:<10.2f}s")
    print(f"{'4. Quality Gate (Eval)':<35} {'8-Dimension Scorecard':<28} {eval_duration:<10.2f}s")
    print(f"{'5. Publication Agent (Final)':<35} {'IEEE Access Engine':<28} {final_duration:<10.2f}s")
    print("-" * 78)
    print(f"{'TOTAL PIPELINE EXECUTION TIME':<63} {total_pipeline_time:<10.2f}s")
    print("=" * 78)
    print("\nVerified Generated Artifacts:")
    print(f"  [1] outputs/m1_research.json  ({len(m1_result.get('sources', []))} sources)")
    print(f"  [2] outputs/m2_review.json    ({verified_count} verified sources)")
    print(f"  [3] outputs/m3_report.json    ({word_count} words, {sections_count} sections)")
    print(f"  [4] outputs/evaluation.json   (Score: {score}/100.0, Grade: {grade})")
    print(f"  [5] outputs/final_report.json (Unified Master Package)")
    print(f"  [6] outputs/final_report.pdf  (IEEE Access 2-Column PDF, {pdf_pages} pages)\n")

    return final_result


if __name__ == "__main__":
    cli_topic = "Agentic AI: Autonomous Intelligence for Complex Goals"
    if len(sys.argv) > 1 and sys.argv[1].strip():
        cli_topic = sys.argv[1].strip()

    run_orchestrator(cli_topic)
