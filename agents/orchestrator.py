"""Multi-Agent Orchestrator and Bounded Correction Loop.

Coordinates the end-to-end research, verification, writing, evaluation,
and PDF export lifecycle with strict retry bounding (max 3 correction iterations).
Updates JobManager in real time so the UI neural-network visualization reflects
the exact active agent stage.
"""

import logging
from pathlib import Path
from typing import List, Optional

from config import Config
from models.schemas import (
    WorkflowStage,
    NewReportRequest,
    ImproveReportRequest,
    ResearchSource,
    SourceType,
    AcademicReport
)
from services.pdf_extractor import PdfExtractor
from services.search_service import SearchService
from services.citation_validator import CitationValidator
from services.report_formatter import ReportFormatter
from services.job_manager import JobManager
from services.storage import ReportStorage
from agents.source_verifier import SourceVerificationAgent
from agents.academic_writer import AcademicWriterAgent
from agents.evaluation import EvaluationAgent

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """Master workflow coordinator across specialized agents."""

    def __init__(self):
        self.job_manager = JobManager()
        self.pdf_extractor = PdfExtractor()
        self.search_service = SearchService()
        self.source_verifier = SourceVerificationAgent()
        self.academic_writer = AcademicWriterAgent()
        self.citation_validator = CitationValidator()
        self.evaluator = EvaluationAgent()

    def run_new_report_workflow(
        self,
        job_id: str,
        request: NewReportRequest,
        uploaded_pdf_path: Optional[Path] = None,
        teammate_sources: Optional[List[ResearchSource]] = None
    ):
        """Execute the complete multi-agent workflow for creating a new academic report."""
        try:
            # Stage 1: Input Validation
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.INPUT_VALIDATION,
                "Input Processing",
                10,
                f"Validating research topic '{request.topic}' and execution parameters."
            )

            all_sources: List[ResearchSource] = []
            source_counter = 1

            # Stage 2: PDF Extraction (if PDF provided)
            if uploaded_pdf_path and uploaded_pdf_path.exists():
                self.job_manager.update_stage(
                    job_id,
                    WorkflowStage.PDF_EXTRACTION,
                    "PDF Extraction",
                    20,
                    f"Extracting academic text and structure from {uploaded_pdf_path.name}."
                )
                try:
                    pdf_result = self.pdf_extractor.extract_from_path(uploaded_pdf_path)
                    # Create a ResearchSource for the uploaded document
                    pdf_text = pdf_result["text"]
                    # Extract representative chunks as excerpts
                    chunks = [c.strip() for c in pdf_text.split("\n\n") if len(c.strip()) > 80]
                    pdf_source = ResearchSource(
                        source_id=f"SRC-{source_counter}",
                        title=pdf_result.get("metadata", {}).get("Title") or uploaded_pdf_path.stem.replace("_", " ").title(),
                        authors=[pdf_result.get("metadata", {}).get("Author")] if pdf_result.get("metadata", {}).get("Author") else [],
                        year=None,
                        venue="Uploaded Primary Document",
                        url=None,
                        doi=None,
                        excerpts=chunks[:6] if chunks else [pdf_text[:500]],
                        credibility_score=0.95,
                        is_verified=True,
                        source_type=SourceType.PDF,
                        raw_metadata=pdf_result.get("metadata", {})
                    )
                    all_sources.append(pdf_source)
                    source_counter += 1
                except PdfExtractionError as e:
                    logger.warning(f"PDF extraction error: {e.message}")
                    if request.source_preference == "uploaded_only":
                        raise RuntimeError(f"Cannot proceed with uploaded-only research: {e.message}")

            # Additional manual research text provided by user
            if request.additional_text and request.additional_text.strip():
                manual_chunks = [c.strip() for c in request.additional_text.split("\n\n") if len(c.strip()) > 40]
                all_sources.append(ResearchSource(
                    source_id=f"SRC-{source_counter}",
                    title="User Provided Research Materials",
                    authors=[],
                    year=None,
                    venue="Direct Academic Notes",
                    excerpts=manual_chunks[:4] if manual_chunks else [request.additional_text[:500]],
                    credibility_score=0.85,
                    is_verified=True,
                    source_type=SourceType.MANUAL
                ))
                source_counter += 1

            # Teammate sources integration
            if teammate_sources:
                for tm_src in teammate_sources:
                    tm_src.source_id = f"SRC-{source_counter}"
                    all_sources.append(tm_src)
                    source_counter += 1

            # Stage 3: Research Collection (Web search if preferred or needed)
            if request.source_preference in ("online_only", "both") or len(all_sources) == 0:
                self.job_manager.update_stage(
                    job_id,
                    WorkflowStage.RESEARCH_COLLECTION,
                    "Research Collection",
                    35,
                    f"Searching for peer-reviewed literature and evidence on '{request.topic}'."
                )
                search_results = self.search_service.search(request.topic, max_results=5)
                for s in search_results:
                    s.source_id = f"SRC-{source_counter}"
                    all_sources.append(s)
                    source_counter += 1

            if not all_sources:
                raise RuntimeError("No research evidence could be gathered. Please provide uploaded text or enable online search.")

            # Stage 4: Source and Evidence Verification
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.SOURCE_VERIFICATION,
                "Source Verification Agent",
                45,
                f"Verifying credibility and topical grounding across {len(all_sources)} source records."
            )
            verified_sources, verif_logs = self.source_verifier.verify_sources(request.topic, all_sources)

            # Stage 5: Academic Report Writing
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.ACADEMIC_WRITING,
                "Academic Writer Agent",
                60,
                f"Synthesizing findings into a formal {request.citation_style.value} academic report."
            )
            report = self.academic_writer.generate_report(
                topic=request.topic,
                sources=verified_sources,
                citation_style=request.citation_style,
                length=request.length,
                target_page_count=request.target_page_count,
                additional_notes=request.additional_text
            )

            # Stage 6 & 7: Citation Validation & Quality Evaluation
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.CITATION_VALIDATION,
                "Citation Validator",
                70,
                "Running deterministic citation and reference verification."
            )
            cit_val = self.citation_validator.validate(report, verified_sources)

            self.job_manager.update_stage(
                job_id,
                WorkflowStage.QUALITY_EVALUATION,
                "Evaluation Module",
                78,
                "Evaluating report across 8 dimensions with quality gating."
            )
            evaluation = self.evaluator.evaluate(report, verified_sources, cit_val, attempt=0)

            # Stage 8: Bounded Correction Loop (Max 3 attempts)
            attempt = 0
            max_attempts = Config.MAX_CORRECTION_ATTEMPTS

            while not evaluation.passed and attempt < max_attempts:
                attempt += 1
                self.job_manager.update_stage(
                    job_id,
                    WorkflowStage.CORRECTION_LOOP,
                    f"Correction Loop (Pass {attempt}/{max_attempts})",
                    80 + (attempt * 3),
                    f"Refining report to resolve {len(evaluation.suggested_corrections)} detected quality issue(s)."
                )

                # Feed corrections back into the writer
                report = self.academic_writer.generate_report(
                    topic=request.topic,
                    sources=verified_sources,
                    citation_style=request.citation_style,
                    length=request.length,
                    target_page_count=request.target_page_count,
                    additional_notes=request.additional_text,
                    feedback_corrections=evaluation.suggested_corrections
                )

                # Re-validate citations and re-evaluate
                cit_val = self.citation_validator.validate(report, verified_sources)
                evaluation = self.evaluator.evaluate(report, verified_sources, cit_val, attempt=attempt)

            # Stage 9: Formatting & PDF Generation
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.FORMATTING_EXPORT,
                "Final Report Generator",
                92,
                "Rendering publication-quality academic PDF with running headers and page numbers."
            )
            pdf_path = ReportFormatter.generate_pdf(report)

            # Persist report and evaluation
            ReportStorage.save_report(report, evaluation, pdf_path)

            # Mark complete
            self.job_manager.complete_job(
                job_id=job_id,
                report_id=report.id,
                evaluation=evaluation,
                pdf_filename=pdf_path.name
            )

        except Exception as e:
            logger.exception(f"Workflow execution failure for job {job_id}: {e}")
            self.job_manager.fail_job(job_id, str(e))

    def run_improve_report_workflow(
        self,
        job_id: str,
        request: ImproveReportRequest,
        uploaded_pdf_path: Optional[Path] = None
    ):
        """Execute the workflow for improving and restructuring an existing report."""
        try:
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.INPUT_VALIDATION,
                "Input Processing",
                10,
                "Parsing existing report and preservation requirements."
            )

            all_sources: List[ResearchSource] = []
            source_counter = 1

            # Extract existing report from PDF if uploaded
            original_text = request.report_text
            if uploaded_pdf_path and uploaded_pdf_path.exists():
                try:
                    pdf_res = self.pdf_extractor.extract_from_path(uploaded_pdf_path)
                    original_text = pdf_res["text"]
                except Exception as e:
                    logger.warning(f"Could not extract PDF for improve: {e}")

            # Additional sources if provided
            if request.additional_sources and request.additional_sources.strip():
                chunks = [c.strip() for c in request.additional_sources.split("\n\n") if len(c.strip()) > 30]
                all_sources.append(ResearchSource(
                    source_id=f"SRC-{source_counter}",
                    title="Supplementary Reference Material",
                    authors=[],
                    year=None,
                    venue="Academic Reference Corpus",
                    excerpts=chunks[:4] if chunks else [request.additional_sources[:500]],
                    credibility_score=0.90,
                    is_verified=True,
                    source_type=SourceType.MANUAL
                ))
                source_counter += 1

            # Ingest online literature search if sources are sparse
            if not all_sources:
                # Infer topic from first 100 chars
                inferred_topic = original_text[:100].split("\n")[0]
                search_results = self.search_service.search(inferred_topic, max_results=3)
                for s in search_results:
                    s.source_id = f"SRC-{source_counter}"
                    all_sources.append(s)
                    source_counter += 1

            # Source verification
            verified_sources, _ = self.source_verifier.verify_sources("Report Improvement", all_sources)

            # Academic Writer: rewrite and improve
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.ACADEMIC_WRITING,
                "Academic Writer Agent",
                55,
                "Refactoring structure, citations, and clarity while preserving core findings."
            )
            report = self.academic_writer.rewrite_and_improve(
                original_text=original_text,
                sources=verified_sources,
                citation_style=request.citation_style,
                preserve_findings=request.preserve_findings
            )

            # Citation validation & Evaluation
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.CITATION_VALIDATION,
                "Citation Validator",
                70,
                "Validating preserved findings and citation consistency."
            )
            cit_val = self.citation_validator.validate(report, verified_sources)

            self.job_manager.update_stage(
                job_id,
                WorkflowStage.QUALITY_EVALUATION,
                "Evaluation Module",
                78,
                "Scoring improved report against academic standards."
            )
            evaluation = self.evaluator.evaluate(report, verified_sources, cit_val, attempt=0)

            # Bounded correction loop
            attempt = 0
            while not evaluation.passed and attempt < Config.MAX_CORRECTION_ATTEMPTS:
                attempt += 1
                self.job_manager.update_stage(
                    job_id,
                    WorkflowStage.CORRECTION_LOOP,
                    f"Correction Loop (Pass {attempt}/{Config.MAX_CORRECTION_ATTEMPTS})",
                    80 + (attempt * 3),
                    "Refining rewritten draft to resolve quality warnings."
                )
                report = self.academic_writer.rewrite_and_improve(
                    original_text=original_text,
                    sources=verified_sources,
                    citation_style=request.citation_style,
                    preserve_findings=request.preserve_findings,
                    feedback_corrections=evaluation.suggested_corrections
                )
                cit_val = self.citation_validator.validate(report, verified_sources)
                evaluation = self.evaluator.evaluate(report, verified_sources, cit_val, attempt=attempt)

            # Format and generate PDF
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.FORMATTING_EXPORT,
                "Final Report Generator",
                92,
                "Compiling revised academic PDF."
            )
            pdf_path = ReportFormatter.generate_pdf(report)

            # Save report
            ReportStorage.save_report(report, evaluation, pdf_path)

            self.job_manager.complete_job(
                job_id=job_id,
                report_id=report.id,
                evaluation=evaluation,
                pdf_filename=pdf_path.name
            )

        except Exception as e:
            logger.exception(f"Improvement workflow failure for job {job_id}: {e}")
            self.job_manager.fail_job(job_id, str(e))

    def run_re_correct_report_workflow(
        self,
        job_id: str,
        report_id: str,
        user_feedback: Optional[str] = None
    ):
        """Execute autonomous re-correction on an existing report to resolve all evaluation defects."""
        try:
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.INPUT_VALIDATION,
                "Quality Defect Analysis",
                10,
                f"Analyzing evaluation critiques and gating defects for report."
            )

            record = ReportStorage.get_report(report_id)
            if not record:
                raise ValueError(f"Report {report_id} not found.")

            rep_data = record.get("report", {})
            eval_data = record.get("evaluation") or {}

            report = AcademicReport(**rep_data)

            # Collect critiques
            suggested_corrections = list(eval_data.get("suggested_corrections") or [])
            critical_errors = list(eval_data.get("critical_errors") or [])
            warnings = list(eval_data.get("warnings") or [])

            combined_feedback = suggested_corrections + critical_errors + warnings
            if user_feedback:
                combined_feedback.append(user_feedback)

            # Determine clean topic
            clean_topic = report.topic
            if not clean_topic or clean_topic in ("Improved Academic Report", "Document Revision", "Academic Research"):
                clean_topic = report.title.split(":")[0].split("–")[0].split("-")[0].strip() or report.title
            clean_topic = clean_topic or "Academic Research"

            # Reconstruct research sources
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.SOURCE_VERIFICATION,
                "Reference Grounding",
                25,
                "Grounding citations against source excerpts."
            )

            all_sources: List[ResearchSource] = []
            source_counter = 1
            for ref in report.references:
                matching_excerpts = [s.content[:400] for s in report.sections if ref.source_id in s.citations]
                if not matching_excerpts:
                    matching_excerpts = [report.abstract[:400]]

                ref_title = ref.formatted_text
                if '"' in ref_title:
                    parts = ref_title.split('"')
                    if len(parts) >= 2:
                        ref_title = parts[1]
                elif '*' in ref_title:
                    parts = ref_title.split('*')
                    if len(parts) >= 2:
                        ref_title = parts[1]

                all_sources.append(ResearchSource(
                    source_id=ref.source_id or f"SRC-{source_counter}",
                    title=ref_title[:120],
                    authors=[],
                    year=None,
                    venue="Academic Reference",
                    url=ref.url,
                    doi=ref.doi,
                    excerpts=matching_excerpts,
                    credibility_score=0.95,
                    is_verified=True,
                    source_type=SourceType.MANUAL
                ))
                source_counter += 1

            if len(all_sources) < 2 and clean_topic:
                clean_query = clean_topic.split(":")[0].split("–")[0].split("-")[0].strip()
                search_res = self.search_service.search(clean_query, max_results=2)
                for s in search_res:
                    s.source_id = f"SRC-{source_counter}"
                    all_sources.append(s)
                    source_counter += 1

            verified_sources, _ = self.source_verifier.verify_sources(clean_topic, all_sources)
            markdown_content = ReportFormatter.to_markdown(report)

            # Writer rewrite with critiques
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.ACADEMIC_WRITING,
                "Academic Writer Agent",
                50,
                "Fixing evaluation issues, citations, and structural clarity."
            )

            revised_report = self.academic_writer.rewrite_and_improve(
                original_text=markdown_content,
                sources=verified_sources,
                citation_style=report.citation_style,
                preserve_findings=True,
                feedback_corrections=combined_feedback,
                topic=clean_topic
            )
            revised_report.id = report.id
            revised_report.topic = clean_topic

            # Citation validation
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.CITATION_VALIDATION,
                "Citation Validator",
                70,
                "Validating in-text citations and bibliographic alignment."
            )
            cit_val = self.citation_validator.validate(revised_report, verified_sources)

            # Evaluation
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.QUALITY_EVALUATION,
                "Evaluation Module",
                80,
                "Grading report across 8 dimensions."
            )
            evaluation = self.evaluator.evaluate(revised_report, verified_sources, cit_val, attempt=0)

            # Bounded correction loop
            attempt = 0
            while not evaluation.passed and attempt < Config.MAX_CORRECTION_ATTEMPTS:
                attempt += 1
                self.job_manager.update_stage(
                    job_id,
                    WorkflowStage.CORRECTION_LOOP,
                    f"Correction Loop (Pass {attempt}/{Config.MAX_CORRECTION_ATTEMPTS})",
                    80 + (attempt * 3),
                    "Refining draft to clear remaining quality warnings."
                )
                revised_report = self.academic_writer.rewrite_and_improve(
                    original_text=ReportFormatter.to_markdown(revised_report),
                    sources=verified_sources,
                    citation_style=report.citation_style,
                    preserve_findings=True,
                    feedback_corrections=evaluation.suggested_corrections + evaluation.critical_errors,
                    topic=clean_topic
                )
                revised_report.id = report.id
                revised_report.topic = clean_topic
                cit_val = self.citation_validator.validate(revised_report, verified_sources)
                evaluation = self.evaluator.evaluate(revised_report, verified_sources, cit_val, attempt=attempt)

            # Formatting & PDF
            self.job_manager.update_stage(
                job_id,
                WorkflowStage.FORMATTING_EXPORT,
                "Final Report Generator",
                92,
                "Re-compiling publication-quality PDF."
            )
            pdf_path = ReportFormatter.generate_pdf(revised_report)

            # Save updated report under same report ID
            ReportStorage.save_report(revised_report, evaluation, pdf_path)

            self.job_manager.complete_job(
                job_id=job_id,
                report_id=revised_report.id,
                evaluation=evaluation,
                pdf_filename=pdf_path.name
            )

        except Exception as e:
            logger.exception(f"Re-correction workflow failure for job {job_id}: {e}")
            self.job_manager.fail_job(job_id, str(e))
