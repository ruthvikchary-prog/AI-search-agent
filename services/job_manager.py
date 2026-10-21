"""Asynchronous job execution and workflow stage progression manager.

Enables real-time progress polling, stage updates, and thread-safe execution
powering the neural-network visualization in the frontend.
"""

import threading
import uuid
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Callable, Any

from models.schemas import WorkflowJob, WorkflowStage, EvaluationReport

logger = logging.getLogger(__name__)


class JobManager:
    """Manages background multi-agent workflow jobs with thread-safe stage progression."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self._jobs: Dict[str, WorkflowJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._job_lock = threading.Lock()

    def create_job(self) -> WorkflowJob:
        """Create and register a new workflow job."""
        job_id = str(uuid.uuid4())
        job = WorkflowJob(
            job_id=job_id,
            stage=WorkflowStage.IDLE,
            stage_label="Initialized",
            status="pending",
            progress=0,
            message="Workflow job created and queued.",
            created_at=datetime.now(timezone.utc).isoformat() + "Z"
        )
        with self._job_lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[WorkflowJob]:
        """Retrieve the current state of a workflow job."""
        with self._job_lock:
            return self._jobs.get(job_id)

    def update_stage(
        self,
        job_id: str,
        stage: WorkflowStage,
        stage_label: str,
        progress: int,
        message: str
    ):
        """Update the active workflow stage and progress."""
        with self._job_lock:
            job = self._jobs.get(job_id)
            if job:
                job.stage = stage
                job.stage_label = stage_label
                job.status = "running"
                job.progress = progress
                job.message = message

    def complete_job(
        self,
        job_id: str,
        report_id: str,
        evaluation: Optional[EvaluationReport] = None,
        pdf_filename: Optional[str] = None
    ):
        """Mark job as successfully finished."""
        with self._job_lock:
            job = self._jobs.get(job_id)
            if job:
                job.stage = WorkflowStage.COMPLETED
                job.stage_label = "Complete"
                job.status = "completed"
                job.progress = 100
                job.message = "Academic report generation and validation complete."
                job.report_id = report_id
                job.evaluation = evaluation
                job.pdf_filename = pdf_filename
                job.completed_at = datetime.now(timezone.utc).isoformat() + "Z"

    def fail_job(self, job_id: str, error_message: str):
        """Mark job as failed with diagnostic message."""
        with self._job_lock:
            job = self._jobs.get(job_id)
            if job:
                job.stage = WorkflowStage.FAILED
                job.stage_label = "Execution Error"
                job.status = "failed"
                job.error = error_message
                job.message = f"Failed: {error_message}"
                job.completed_at = datetime.now(timezone.utc).isoformat() + "Z"

    def submit_task(self, fn: Callable[..., Any], *args, **kwargs):
        """Dispatch a background workflow task to the thread pool."""
        self._executor.submit(fn, *args, **kwargs)
