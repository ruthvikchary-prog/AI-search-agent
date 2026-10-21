"""Academic Report Evaluation Module (Student 4).

Responsible for:
1. Multi-dimensional quality grading:
   - Structural Completeness (15%)
   - Evidence Support & Grounding (20%)
   - Citation Consistency (15%)
   - Relevance to Topic (15%)
   - Academic Tone & Clarity (10%)
   - Logical Organization (10%)
   - Reference Integrity (10%)
   - Formatting Correctness (5%)
2. Hard Quality Gates: Fabricated references or severe unsupported claims trigger immediate failure
   regardless of high writing score.
3. Diagnostic issue detection separating Critical Errors vs. Warnings.
4. Generates actionable suggested corrections for the writer's bounded correction loop.
5. Fully deterministic and testable without requiring an active LLM.
"""

import re
from typing import List, Dict, Optional
from config import Config
from models.schemas import (
    AcademicReport,
    ResearchSource,
    EvaluationReport,
    EvaluationDimension,
    CitationValidationResult
)
from services.citation_validator import CitationValidator


class EvaluationAgent:
    """Rigorous academic quality evaluator and scorecard generator."""

    # Configurable dimension weights (sum to 1.0)
    DIMENSION_WEIGHTS = {
        "Structural Completeness": 0.15,
        "Evidence Support & Grounding": 0.20,
        "Citation Consistency": 0.15,
        "Topic Relevance": 0.15,
        "Academic Tone & Clarity": 0.10,
        "Logical Organization": 0.10,
        "Reference Integrity": 0.10,
        "Formatting Correctness": 0.05
    }

    COLLOQUIALISMS = {
        "gonna", "wanna", "a lot of", "kind of", "sort of", "huge deal",
        "awesome", "crazy", "stuff", "things", "cool", "anyways", "basically"
    }

    def __init__(self, passing_score: Optional[float] = None):
        self.passing_score = passing_score or Config.EVALUATION_PASSING_SCORE
        self.citation_validator = CitationValidator()

    def evaluate(
        self,
        report: AcademicReport,
        sources: List[ResearchSource],
        citation_validation: Optional[CitationValidationResult] = None,
        attempt: int = 0
    ) -> EvaluationReport:
        """Run comprehensive multi-dimensional academic evaluation on an AcademicReport."""
        if citation_validation is None:
            citation_validation = self.citation_validator.validate(report, sources)

        critical_errors: List[str] = []
        warnings: List[str] = []
        suggested_corrections: List[str] = []
        dimensions: List[EvaluationDimension] = []

        # 1. Structural Completeness Evaluation
        struct_score, struct_crit, struct_warn, struct_corr = self._eval_structural_completeness(report)
        critical_errors.extend(struct_crit)
        warnings.extend(struct_warn)
        suggested_corrections.extend(struct_corr)
        dimensions.append(EvaluationDimension(
            name="Structural Completeness",
            score=struct_score,
            weight=self.DIMENSION_WEIGHTS["Structural Completeness"],
            passed=struct_score >= 70.0,
            feedback="All core academic sections present." if struct_score >= 70.0 else "Missing required structural sections."
        ))

        # 2. Evidence Support & Grounding
        ev_score, ev_crit, ev_warn, ev_corr = self._eval_evidence_support(report, sources, citation_validation)
        critical_errors.extend(ev_crit)
        warnings.extend(ev_warn)
        suggested_corrections.extend(ev_corr)
        dimensions.append(EvaluationDimension(
            name="Evidence Support & Grounding",
            score=ev_score,
            weight=self.DIMENSION_WEIGHTS["Evidence Support & Grounding"],
            passed=ev_score >= 70.0,
            feedback="Strong evidence grounding in source excerpts." if ev_score >= 70.0 else "Insufficient grounding or unsupported claims."
        ))

        # 3. Citation Consistency
        cit_score, cit_crit, cit_warn, cit_corr = self._eval_citation_consistency(citation_validation)
        critical_errors.extend(cit_crit)
        warnings.extend(cit_warn)
        suggested_corrections.extend(cit_corr)
        dimensions.append(EvaluationDimension(
            name="Citation Consistency",
            score=cit_score,
            weight=self.DIMENSION_WEIGHTS["Citation Consistency"],
            passed=cit_score >= 70.0,
            feedback="Citations properly resolve to known sources." if cit_score >= 70.0 else "Unresolved or improperly mapped citations."
        ))

        # 4. Topic Relevance
        rel_score, rel_crit, rel_warn, rel_corr = self._eval_topic_relevance(report)
        critical_errors.extend(rel_crit)
        warnings.extend(rel_warn)
        suggested_corrections.extend(rel_corr)
        dimensions.append(EvaluationDimension(
            name="Topic Relevance",
            score=rel_score,
            weight=self.DIMENSION_WEIGHTS["Topic Relevance"],
            passed=rel_score >= 70.0,
            feedback="High thematic relevance to the research topic." if rel_score >= 70.0 else "Deviates from topic keywords."
        ))

        # 5. Academic Tone & Clarity
        tone_score, tone_warn, tone_corr = self._eval_academic_tone(report)
        warnings.extend(tone_warn)
        suggested_corrections.extend(tone_corr)
        dimensions.append(EvaluationDimension(
            name="Academic Tone & Clarity",
            score=tone_score,
            weight=self.DIMENSION_WEIGHTS["Academic Tone & Clarity"],
            passed=tone_score >= 65.0,
            feedback="Rigorous academic diction." if tone_score >= 65.0 else "Informal language or colloquialisms detected."
        ))

        # 6. Logical Organization
        org_score, org_warn, org_corr = self._eval_logical_organization(report)
        warnings.extend(org_warn)
        suggested_corrections.extend(org_corr)
        dimensions.append(EvaluationDimension(
            name="Logical Organization",
            score=org_score,
            weight=self.DIMENSION_WEIGHTS["Logical Organization"],
            passed=org_score >= 70.0,
            feedback="Logical section progression." if org_score >= 70.0 else "Weak section transitions or disorganized structure."
        ))

        # 7. Reference Integrity
        ref_score, ref_crit, ref_warn, ref_corr = self._eval_reference_integrity(report, citation_validation)
        critical_errors.extend(ref_crit)
        warnings.extend(ref_warn)
        suggested_corrections.extend(ref_corr)
        dimensions.append(EvaluationDimension(
            name="Reference Integrity",
            score=ref_score,
            weight=self.DIMENSION_WEIGHTS["Reference Integrity"],
            passed=ref_score >= 75.0,
            feedback="All bibliographic entries validated." if ref_score >= 75.0 else "Fabricated references or missing bibliography."
        ))

        # 8. Formatting Correctness
        fmt_score, fmt_warn, fmt_corr = self._eval_formatting(report)
        warnings.extend(fmt_warn)
        suggested_corrections.extend(fmt_corr)
        dimensions.append(EvaluationDimension(
            name="Formatting Correctness",
            score=fmt_score,
            weight=self.DIMENSION_WEIGHTS["Formatting Correctness"],
            passed=fmt_score >= 70.0,
            feedback="Adheres to academic layout conventions." if fmt_score >= 70.0 else "Formatting inconsistencies found."
        ))

        # Calculate weighted overall score
        composite_score = sum(d.score * d.weight for d in dimensions)
        composite_score = round(composite_score, 1)

        # HARD QUALITY GATE:
        # If any critical errors exist (e.g. fabricated references, 0 resolved citations, missing abstract),
        # the report CANNOT pass, regardless of composite score!
        has_critical_failure = len(critical_errors) > 0
        passed = (composite_score >= self.passing_score) and not has_critical_failure

        # Deduplicate suggestions and warnings
        unique_suggestions = list(dict.fromkeys(suggested_corrections))
        unique_warnings = list(dict.fromkeys(warnings))
        unique_critical = list(dict.fromkeys(critical_errors))

        return EvaluationReport(
            overall_score=composite_score,
            passed=passed,
            dimensions=dimensions,
            critical_errors=unique_critical,
            warnings=unique_warnings,
            suggested_corrections=unique_suggestions,
            correction_attempt=attempt
        )

    # =========================================================================
    # Individual Dimension Evaluators
    # =========================================================================

    def _eval_structural_completeness(self, report: AcademicReport):
        score = 100.0
        critical = []
        warnings = []
        corrections = []

        if not report.title or len(report.title.strip()) < 5:
            score -= 25.0
            critical.append("Missing or invalid document title.")
            corrections.append("Provide a descriptive academic title.")

        if not report.abstract or len(report.abstract.strip()) < 80:
            score -= 25.0
            critical.append("Abstract is missing or substantively insufficient (under 80 characters).")
            corrections.append("Expand the abstract to clearly state the problem, methodology, and key findings.")
        elif len(report.abstract.split()) < 100:
            score -= 10.0
            warnings.append("Abstract is relatively short for a peer-reviewed academic report.")

        if not report.keywords or len(report.keywords) < 2:
            score -= 10.0
            warnings.append("Fewer than 2 keywords provided.")
            corrections.append("Include at least 3-5 indexing keywords.")

        if not report.sections or len(report.sections) < 2:
            score -= 30.0
            critical.append("Paper lacks adequate sections (fewer than 2 body sections).")
            corrections.append("Structure the body into Introduction, Literature Review, Findings, and Discussion.")

        if not report.conclusion or len(report.conclusion.strip()) < 80:
            score -= 20.0
            critical.append("Conclusion is missing or truncated.")
            corrections.append("Provide a conclusive section summarizing implications and future work.")

        return max(0.0, score), critical, warnings, corrections

    def _eval_evidence_support(self, report: AcademicReport, sources: List[ResearchSource], cit_val: CitationValidationResult):
        score = 100.0
        critical = []
        warnings = []
        corrections = []

        if not sources:
            score -= 50.0
            critical.append("No research sources were supplied to ground this paper.")
            corrections.append("Supply verified research sources to substantiate the report.")
            return max(0.0, score), critical, warnings, corrections

        # Check in-text citations ratio
        resolved_count = len(cit_val.resolved_citations)
        if resolved_count == 0:
            score -= 60.0
            critical.append("Zero verified in-text citations found in the document body.")
            corrections.append("Cite source IDs (e.g. [SRC-1]) directly after factual assertions.")
        elif resolved_count < len(sources):
            score -= 15.0
            warnings.append(f"Only {resolved_count} of {len(sources)} available sources are cited.")
            corrections.append("Integrate evidence from the remaining uncited sources.")

        # Check unsupported claims
        if cit_val.unsupported_claims:
            penalty = min(30.0, len(cit_val.unsupported_claims) * 10.0)
            score -= penalty
            warnings.append(f"{len(cit_val.unsupported_claims)} claims have low lexical overlap with source excerpts.")
            corrections.append("Rephrase claims to align directly with the cited evidence excerpts.")

        return max(0.0, score), critical, warnings, corrections

    def _eval_citation_consistency(self, cit_val: CitationValidationResult):
        score = 100.0
        critical = []
        warnings = []
        corrections = []

        if cit_val.unresolved_citations:
            penalty = len(cit_val.unresolved_citations) * 20.0
            score -= penalty
            critical.append(f"{len(cit_val.unresolved_citations)} in-text citation(s) do not resolve to known sources: {', '.join(cit_val.unresolved_citations)}.")
            corrections.append("Remove or fix citations that do not map to ingested source IDs.")

        if cit_val.formatting_errors:
            score -= 15.0
            warnings.extend(cit_val.formatting_errors)
            corrections.append("Format citations and references strictly in the target citation style.")

        return max(0.0, score), critical, warnings, corrections

    def _eval_topic_relevance(self, report: AcademicReport):
        score = 100.0
        critical = []
        warnings = []
        corrections = []

        # Determine reference topic
        ref_topic = report.topic
        if not ref_topic or ref_topic in ("Improved Academic Report", "Document Revision", "Academic Research"):
            ref_topic = report.title.split(":")[0].split("–")[0].split("-")[0].strip() or report.title

        stopwords = {"with", "that", "this", "from", "were", "been", "have", "about", "study", "analysis", "improved", "academic", "report", "document", "revision", "investigation", "synthesis", "review"}
        topic_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", ref_topic.lower()))
        significant_words = topic_words - stopwords

        if not significant_words:
            # Fall back to title words
            title_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", report.title.lower())) - stopwords
            significant_words = title_words

        if not significant_words:
            return 85.0, critical, warnings, corrections

        full_doc_text = f"{report.title} {report.abstract} " + " ".join(s.content for s in report.sections)
        full_doc_lower = full_doc_text.lower()

        found = [w for w in significant_words if w in full_doc_lower]
        ratio = len(found) / len(significant_words)

        if ratio < 0.40:
            score -= 40.0
            critical.append(f"Report text demonstrates low topical overlap with '{ref_topic}'.")
            corrections.append("Re-orient the content to directly discuss the core themes of the topic.")
        elif ratio < 0.70:
            score -= 15.0
            warnings.append("Some primary topic terms are sparsely referenced in the document body.")

        return max(0.0, score), critical, warnings, corrections

    def _eval_academic_tone(self, report: AcademicReport):
        score = 100.0
        warnings = []
        corrections = []

        full_text = f"{report.abstract} " + " ".join(s.content for s in report.sections) + f" {report.conclusion}"
        lower_text = full_text.lower()

        found_colloquials = [c for c in self.COLLOQUIALISMS if re.search(rf"\b{re.escape(c)}\b", lower_text)]
        if found_colloquials:
            score -= min(30.0, len(found_colloquials) * 10.0)
            warnings.append(f"Informal colloquialisms detected: {', '.join(found_colloquials)}.")
            corrections.append("Replace informal phrases with rigorous academic terminology.")

        # Check for first-person overuse ("I think", "we believe")
        first_person_matches = re.findall(r"\b(i feel|i think|i believe|in my opinion)\b", lower_text)
        if first_person_matches:
            score -= 15.0
            warnings.append("Subjective first-person assertions detected.")
            corrections.append("Use objective academic phrasing (e.g. 'Evidence indicates' rather than 'I think').")

        return max(0.0, score), warnings, corrections

    def _eval_logical_organization(self, report: AcademicReport):
        score = 100.0
        warnings = []
        corrections = []

        headings = [s.heading.lower() for s in report.sections]
        has_intro = any("intro" in h or "background" in h for h in headings)
        if not has_intro:
            score -= 15.0
            warnings.append("First section does not clearly introduce the topic or background.")
            corrections.append("Add an introductory section setting up the problem statement.")

        has_findings = any("finding" in h or "result" in h or "evidence" in h or "analysis" in h or "discussion" in h for h in headings)
        if not has_findings:
            score -= 15.0
            warnings.append("Report lacks an explicit Findings, Analysis, or Discussion section.")
            corrections.append("Dedicate a specific section to presenting findings and evidence analysis.")

        return max(0.0, score), warnings, corrections

    def _eval_reference_integrity(self, report: AcademicReport, cit_val: CitationValidationResult):
        score = 100.0
        critical = []
        warnings = []
        corrections = []

        if not report.references:
            score -= 60.0
            critical.append("References section is empty.")
            corrections.append("Populate the References section with complete bibliographic citations.")
            return max(0.0, score), critical, warnings, corrections

        if cit_val.fabricated_references:
            score -= 60.0
            critical.append(f"Fabricated reference(s) detected: {', '.join(cit_val.fabricated_references)}.")
            corrections.append("Remove fabricated references that do not correspond to verified research sources.")

        if cit_val.unused_sources:
            score -= 10.0
            warnings.append(f"{len(cit_val.unused_sources)} reference(s) listed in bibliography are never cited in text.")
            corrections.append("Cite or prune unused bibliography entries.")

        return max(0.0, score), critical, warnings, corrections

    def _eval_formatting(self, report: AcademicReport):
        score = 100.0
        warnings = []
        corrections = []

        # Check section numbering consistency
        for s in report.sections:
            if not re.match(r"^\d+(\.\d+)*\s+", s.heading.strip()):
                score -= 5.0
                warnings.append(f"Section heading '{s.heading}' lacks standard academic numbering (e.g. '1. Title').")
                break

        # Check target word count proportionality
        total_words = sum(len(s.content.split()) for s in report.sections)
        min_expected_words = report.target_page_count * 200
        if total_words < min_expected_words:
            score -= 15.0
            warnings.append(f"Report length ({total_words} words) is below target expectations for a {report.target_page_count}-page paper.")
            corrections.append("Elaborate on section analyses to satisfy target length requirements.")

        return max(0.0, score), warnings, corrections
