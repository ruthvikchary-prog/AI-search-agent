"""Unit tests for multi-agent orchestrator and bounded correction loop."""

from models.schemas import (
    NewReportRequest,
    ImproveReportRequest,
    CitationStyle,
    ReportLength,
    WorkflowStage
)
from agents.orchestrator import MultiAgentOrchestrator
from services.job_manager import JobManager
from config import Config


def test_orchestrator_new_report_lifecycle():
    """Verify end-to-end execution of new report workflow using deterministic generators."""
    orchestrator = MultiAgentOrchestrator()
    job_manager = JobManager()

    job = job_manager.create_job()
    req = NewReportRequest(
        topic="Reinforcement Learning from Human Feedback",
        length=ReportLength.BRIEF,
        target_page_count=3,
        citation_style=CitationStyle.IEEE,
        source_preference="online_only",
        additional_text="RLHF aligns language models with user intent using PPO and reward models."
    )

    # Run synchronously with isolated writer in unit test
    orchestrator.academic_writer.client = None
    orchestrator.run_new_report_workflow(job_id=job.job_id, request=req)

    finished_job = job_manager.get_job(job.job_id)
    assert finished_job is not None
    assert finished_job.status == "completed"
    assert finished_job.stage == WorkflowStage.COMPLETED
    assert finished_job.report_id is not None
    assert finished_job.evaluation is not None
    assert finished_job.progress == 100


def test_correction_loop_is_strictly_bounded():
    """Verify that the correction loop terminates at or before MAX_CORRECTION_ATTEMPTS (3)."""
    orchestrator = MultiAgentOrchestrator()
    job_manager = JobManager()

    job = job_manager.create_job()
    # Force passing_score to an impossible 100.0 to trigger correction retries
    original_passing = Config.EVALUATION_PASSING_SCORE
    try:
        Config.EVALUATION_PASSING_SCORE = 100.0
        orchestrator.evaluator.passing_score = 100.0

        req = NewReportRequest(
            topic="Constrained Optimization Testing",
            length=ReportLength.BRIEF,
            target_page_count=2,
            citation_style=CitationStyle.IEEE,
            source_preference="both",
            additional_text="Constrained optimization models objective functions subjected to feasibility boundaries [SRC-1]."
        )
        orchestrator.academic_writer.client = None
        orchestrator.run_new_report_workflow(job_id=job.job_id, request=req)

        finished_job = job_manager.get_job(job.job_id)
        assert finished_job.status == "completed"
        # Must have completed without infinite loop
        eval_report = finished_job.evaluation
        assert eval_report is not None
        # Attempt count must not exceed 3
        assert eval_report.correction_attempt <= Config.MAX_CORRECTION_ATTEMPTS
        assert eval_report.correction_attempt <= 3
    finally:
        Config.EVALUATION_PASSING_SCORE = original_passing
        orchestrator.evaluator.passing_score = original_passing
