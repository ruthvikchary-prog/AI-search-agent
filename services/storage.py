"""Persistence service for storing and retrieving academic reports and metadata."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from config import Config
from models.schemas import AcademicReport, EvaluationReport

logger = logging.getLogger(__name__)


class ReportStorage:
    """Safely manages filesystem storage for reports and their evaluation scorecards."""

    @staticmethod
    def save_report(
        report: AcademicReport,
        evaluation: Optional[EvaluationReport] = None,
        pdf_path: Optional[Path] = None
    ) -> Path:
        """Persist report, evaluation, and reference to PDF as a JSON record."""
        Config.GENERATED_FOLDER.mkdir(parents=True, exist_ok=True)
        report_file = Config.GENERATED_FOLDER / f"report_{report.id}.json"

        data: Dict[str, Any] = {
            "report": report.model_dump(),
            "evaluation": evaluation.model_dump() if evaluation else None,
            "pdf_filename": pdf_path.name if pdf_path else None,
            "saved_at": report.created_at
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return report_file

    @staticmethod
    def get_report(report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a saved report record by ID, preventing path traversal."""
        # Sanitize report_id (allow only alphanumeric, dashes, underscores)
        safe_id = "".join(c for c in report_id if c.isalnum() or c in ("-", "_"))
        if not safe_id:
            return None

        report_file = Config.GENERATED_FOLDER / f"report_{safe_id}.json"
        if not report_file.exists():
            return None

        try:
            with open(report_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load report {report_id}: {e}")
            return None

    @staticmethod
    def list_reports(limit: int = 50) -> List[Dict[str, Any]]:
        """List all saved reports ordered by creation date."""
        reports = []
        if not Config.GENERATED_FOLDER.exists():
            return []

        for p in Config.GENERATED_FOLDER.glob("report_*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                    rep = rec.get("report", {})
                    eval_data = rec.get("evaluation")
                    reports.append({
                        "id": rep.get("id"),
                        "title": rep.get("title"),
                        "topic": rep.get("topic"),
                        "citation_style": rep.get("citation_style"),
                        "created_at": rep.get("created_at"),
                        "score": eval_data.get("overall_score") if eval_data else None,
                        "passed": eval_data.get("passed") if eval_data else None,
                        "pdf_filename": rec.get("pdf_filename")
                    })
            except Exception as e:
                logger.warning(f"Error reading report summary for {p}: {e}")

        # Sort descending by creation date
        reports.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return reports[:limit]

    @staticmethod
    def delete_report(report_id: str) -> bool:
        """Safely delete a report and its corresponding PDF file."""
        safe_id = "".join(c for c in report_id if c.isalnum() or c in ("-", "_"))
        if not safe_id:
            return False

        report_file = Config.GENERATED_FOLDER / f"report_{safe_id}.json"
        if report_file.exists():
            try:
                # Also delete associated PDF if mentioned
                with open(report_file, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                    pdf_fn = rec.get("pdf_filename")
                    if pdf_fn:
                        pdf_path = Config.GENERATED_FOLDER / pdf_fn
                        if pdf_path.exists():
                            pdf_path.unlink()
                report_file.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to delete report {safe_id}: {e}")
                return False
        return False
