"""Flask Backend Application for the Multi-Agent Academic Research Assistant.

Provides RESTful endpoints for multi-agent academic report generation,
source verification, PDF extraction, deterministic evaluation, and PDF export.
"""

import uuid
import logging
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from pydantic import ValidationError

from config import Config
from models.schemas import (
    AcademicReport,
    NewReportRequest,
    ImproveReportRequest,
    TeammateResearchSubmission,
    CitationStyle,
    ReportLength
)
from services.job_manager import JobManager
from services.storage import ReportStorage
from services.report_formatter import ReportFormatter
from agents.orchestrator import MultiAgentOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("academic_assistant")

app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER

orchestrator = MultiAgentOrchestrator()
job_manager = JobManager()


def allowed_file(filename: str) -> bool:
    """Validate allowed file extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@app.route("/")
def index():
    """Render the main single-page application dashboard."""
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint providing runtime and configuration status."""
    return jsonify({
        "status": "healthy",
        "service": "Multi-Agent Academic Research Assistant",
        "version": "1.0.0",
        "llm_configured": bool(Config.GROQ_API_KEY),
        "llm_model": Config.GROQ_MODEL,
        "search_provider": Config.SEARCH_PROVIDER,
        "supported_citation_styles": Config.SUPPORTED_CITATION_STYLES
    }), 200


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Retrieve current background job stage, progress, and result."""
    safe_id = "".join(c for c in job_id if c.isalnum() or c in ("-", "_"))
    job = job_manager.get_job(safe_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.model_dump()), 200


@app.route("/api/reports", methods=["GET"])
def list_reports():
    """List real persisted reports without fabricated data."""
    reports = ReportStorage.list_reports(limit=50)
    return jsonify({"reports": reports, "count": len(reports)}), 200


@app.route("/api/reports/<report_id>", methods=["GET"])
def get_report(report_id: str):
    """Get full structured report data, evaluation scorecard, and HTML preview."""
    safe_id = "".join(c for c in report_id if c.isalnum() or c in ("-", "_"))
    record = ReportStorage.get_report(safe_id)
    if not record:
        return jsonify({"error": "Report not found"}), 404

    rep_data = record.get("report", {})
    try:
        report_obj = AcademicReport(**rep_data)
        html_preview = ReportFormatter.to_academic_html(report_obj)
        markdown_text = ReportFormatter.to_markdown(report_obj)
    except Exception as e:
        logger.warning(f"Error parsing AcademicReport for HTML preview: {e}")
        html_preview = "<p>Preview unavailable.</p>"
        markdown_text = ""

    return jsonify({
        "report": rep_data,
        "evaluation": record.get("evaluation"),
        "pdf_filename": record.get("pdf_filename"),
        "html_preview": html_preview,
        "markdown": markdown_text,
        "saved_at": record.get("saved_at")
    }), 200


@app.route("/api/reports/<report_id>/download", methods=["GET"])
def download_report_pdf(report_id: str):
    """Safely stream the generated academic PDF for download."""
    safe_id = "".join(c for c in report_id if c.isalnum() or c in ("-", "_"))
    record = ReportStorage.get_report(safe_id)
    if not record:
        abort(404, description="Report record not found.")

    pdf_filename = record.get("pdf_filename")
    if not pdf_filename:
        abort(404, description="No PDF file associated with this report.")

    # Guard against path traversal
    safe_pdf_fn = secure_filename(pdf_filename)
    pdf_path = Config.GENERATED_FOLDER / safe_pdf_fn

    if not pdf_path.exists():
        abort(404, description="Generated PDF file does not exist on server.")

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=safe_pdf_fn
    )


@app.route("/api/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id: str):
    """Delete a report record and its associated PDF."""
    success = ReportStorage.delete_report(report_id)
    if success:
        return jsonify({"success": True, "message": "Report deleted successfully"}), 200
    return jsonify({"error": "Report not found or could not be deleted"}), 404


@app.route("/api/reports/generate", methods=["POST"])
def generate_report_endpoint():
    """Start asynchronous workflow for generating a brand new academic report.
    
    Accepts multipart/form-data or JSON.
    """
    try:
        # Determine payload source (form-data or JSON)
        uploaded_pdf_path = None
        if request.content_type and "multipart/form-data" in request.content_type:
            topic = request.form.get("topic", "").strip()
            citation_style = request.form.get("citation_style", Config.DEFAULT_CITATION_STYLE)
            length = request.form.get("length", "standard")
            target_page_count = int(request.form.get("target_page_count", 5))
            source_preference = request.form.get("source_preference", "both")
            additional_text = request.form.get("additional_text", "")

            # Handle PDF upload
            if "pdf_file" in request.files:
                file = request.files["pdf_file"]
                if file and file.filename and file.filename.strip():
                    if not allowed_file(file.filename):
                        return jsonify({"error": "Only valid .pdf files are accepted."}), 400
                    
                    filename = f"upload_{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                    target_path = Config.UPLOAD_FOLDER / filename
                    file.save(str(target_path))
                    uploaded_pdf_path = target_path
        else:
            data = request.get_json(force=True) or {}
            topic = data.get("topic", "").strip()
            citation_style = data.get("citation_style", Config.DEFAULT_CITATION_STYLE)
            length = data.get("length", "standard")
            target_page_count = int(data.get("target_page_count", 5))
            source_preference = data.get("source_preference", "both")
            additional_text = data.get("additional_text", "")

        # Validate with Pydantic
        req_model = NewReportRequest(
            topic=topic,
            length=ReportLength(length),
            target_page_count=target_page_count,
            citation_style=CitationStyle(citation_style),
            source_preference=source_preference,
            additional_text=additional_text
        )

        # Create async job
        job = job_manager.create_job()

        # Submit background thread
        job_manager.submit_task(
            orchestrator.run_new_report_workflow,
            job_id=job.job_id,
            request=req_model,
            uploaded_pdf_path=uploaded_pdf_path
        )

        return jsonify({
            "success": True,
            "job_id": job.job_id,
            "status": "pending",
            "message": "Academic research workflow started."
        }), 202

    except ValidationError as e:
        return jsonify({"error": "Input validation error", "details": e.errors()}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception(f"Report generation request failure: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route("/api/reports/improve", methods=["POST"])
def improve_report_endpoint():
    """Start asynchronous workflow for improving an existing academic report."""
    try:
        uploaded_pdf_path = None
        if request.content_type and "multipart/form-data" in request.content_type:
            report_text = request.form.get("report_text", "").strip()
            citation_style = request.form.get("citation_style", Config.DEFAULT_CITATION_STYLE)
            preserve_findings = request.form.get("preserve_findings", "true").lower() == "true"
            additional_sources = request.form.get("additional_sources", "")

            if "pdf_file" in request.files:
                file = request.files["pdf_file"]
                if file and file.filename and file.filename.strip():
                    if not allowed_file(file.filename):
                        return jsonify({"error": "Only valid .pdf files are accepted."}), 400
                    filename = f"improve_{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                    target_path = Config.UPLOAD_FOLDER / filename
                    file.save(str(target_path))
                    uploaded_pdf_path = target_path
                    if not report_text:
                        report_text = f"Existing report extracted from uploaded file {file.filename}."
        else:
            data = request.get_json(force=True) or {}
            report_text = data.get("report_text", "").strip()
            citation_style = data.get("citation_style", Config.DEFAULT_CITATION_STYLE)
            preserve_findings = bool(data.get("preserve_findings", True))
            additional_sources = data.get("additional_sources", "")

        # Validate with Pydantic
        req_model = ImproveReportRequest(
            report_text=report_text,
            citation_style=CitationStyle(citation_style),
            preserve_findings=preserve_findings,
            additional_sources=additional_sources
        )

        # Create async job
        job = job_manager.create_job()

        # Submit background task
        job_manager.submit_task(
            orchestrator.run_improve_report_workflow,
            job_id=job.job_id,
            request=req_model,
            uploaded_pdf_path=uploaded_pdf_path
        )

        return jsonify({
            "success": True,
            "job_id": job.job_id,
            "status": "pending",
            "message": "Report improvement workflow started."
        }), 202

    except ValidationError as e:
        return jsonify({"error": "Input validation error", "details": e.errors()}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception(f"Report improvement request failure: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route("/api/reports/<report_id>/re-correct", methods=["POST"])
def recorrect_report_endpoint(report_id: str):
    """Trigger autonomous re-correction of an existing academic report based on its evaluation scorecard."""
    try:
        safe_id = "".join(c for c in report_id if c.isalnum() or c in ("-", "_"))
        record = ReportStorage.get_report(safe_id)
        if not record:
            return jsonify({"error": "Report not found"}), 404

        feedback = ""
        if request.is_json:
            data = request.get_json(silent=True) or {}
            feedback = data.get("feedback", "")

        # Create async job
        job = job_manager.create_job()

        # Submit background task
        job_manager.submit_task(
            orchestrator.run_re_correct_report_workflow,
            job_id=job.job_id,
            report_id=safe_id,
            user_feedback=feedback
        )

        return jsonify({
            "success": True,
            "job_id": job.job_id,
            "report_id": safe_id,
            "status": "pending",
            "message": "Re-correction workflow initiated."
        }), 202

    except Exception as e:
        logger.exception(f"Report re-correction request failure: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route("/api/teammate/submit-research", methods=["POST"])
def submit_teammate_research():
    """Ingest structured research sources from connected teammate agents in the multi-agent system."""
    try:
        data = request.get_json(force=True)
        submission = TeammateResearchSubmission(**data)

        # Create job to run research generation with teammate sources
        req_model = NewReportRequest(
            topic=submission.topic,
            length=ReportLength.STANDARD,
            target_page_count=5,
            citation_style=CitationStyle.IEEE,
            source_preference="teammate"
        )

        job = job_manager.create_job()
        job_manager.submit_task(
            orchestrator.run_new_report_workflow,
            job_id=job.job_id,
            request=req_model,
            teammate_sources=submission.sources
        )

        return jsonify({
            "success": True,
            "job_id": job.job_id,
            "agent_name": submission.agent_name,
            "sources_received": len(submission.sources),
            "message": f"Successfully ingested {len(submission.sources)} sources from teammate {submission.agent_name}."
        }), 202

    except ValidationError as e:
        return jsonify({"error": "Validation error for teammate payload", "details": e.errors()}), 400
    except Exception as e:
        logger.exception(f"Teammate research submission failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["GET", "POST"])
def settings_endpoint():
    """Get or update application user preferences."""
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        if "default_citation_style" in data:
            style = data["default_citation_style"]
            if style in Config.SUPPORTED_CITATION_STYLES:
                Config.DEFAULT_CITATION_STYLE = style
        if "passing_score" in data:
            try:
                Config.EVALUATION_PASSING_SCORE = float(data["passing_score"])
            except ValueError:
                pass
        return jsonify({
            "success": True,
            "message": "Settings updated",
            "current_settings": {
                "default_citation_style": Config.DEFAULT_CITATION_STYLE,
                "passing_score": Config.EVALUATION_PASSING_SCORE,
                "groq_model": Config.GROQ_MODEL,
                "search_provider": Config.SEARCH_PROVIDER
            }
        }), 200

    return jsonify({
        "default_citation_style": Config.DEFAULT_CITATION_STYLE,
        "supported_citation_styles": Config.SUPPORTED_CITATION_STYLES,
        "passing_score": Config.EVALUATION_PASSING_SCORE,
        "max_correction_attempts": Config.MAX_CORRECTION_ATTEMPTS,
        "groq_model": Config.GROQ_MODEL,
        "groq_configured": bool(Config.GROQ_API_KEY),
        "search_provider": Config.SEARCH_PROVIDER
    }), 200


if __name__ == "__main__":
    logger.info(f"Starting Multi-Agent Academic Assistant on port {Config.PORT}...")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
