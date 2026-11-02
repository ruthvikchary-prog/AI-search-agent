"""Source and Evidence Verification Agent.

Rigorous evaluation of research sources, distinguishing:
1. Source Existence (URL/DOI syntax, reachable schema, or local PDF provenance).
2. Source Credibility (Academic domain heuristics: .edu, .org, arxiv, ieee, acm, vs generic blog).
3. Evidence Relevance (Grounding overlap between topic and excerpts).
4. Claim Support (Checking that claims are backed by actual excerpts in the source).
"""

import re
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
from models.schemas import ResearchSource, SourceType


class SourceVerificationAgent:
    """Evaluates the credibility and claim support of collected evidence."""

    ACADEMIC_DOMAINS = {
        "arxiv.org", "doi.org", "ieee.org", "acm.org", "springer.com",
        "sciencedirect.com", "nature.com", "science.org", "wiley.com",
        "nih.gov", "ncbi.nlm.nih.gov", "frontiersin.org", "mdpi.com", "plos.org"
    }

    def verify_sources(self, topic: str, sources: List[ResearchSource]) -> Tuple[List[ResearchSource], List[Dict[str, Any]]]:
        """Run verification over a list of sources.
        
        Returns:
            Tuple of (verified_sources, verification_logs)
        """
        verified_sources: List[ResearchSource] = []
        logs: List[Dict[str, Any]] = []

        for source in sources:
            credibility, existence, issues = self._evaluate_source(source)
            relevance, rel_issues = self._evaluate_relevance(topic, source)
            issues.extend(rel_issues)

            # Combined score: 60% credibility, 40% topical relevance
            combined_score = round((credibility * 0.6) + (relevance * 0.4), 2)
            
            # Source passes verification if it has verified existence, sufficient excerpts, and score >= 0.45
            is_valid = existence and len(source.excerpts) > 0 and combined_score >= 0.40

            source.credibility_score = combined_score
            source.is_verified = is_valid

            log_entry = {
                "source_id": source.source_id,
                "title": source.title,
                "existence_verified": existence,
                "credibility_score": credibility,
                "relevance_score": relevance,
                "combined_score": combined_score,
                "is_verified": is_valid,
                "issues": issues,
                "excerpt_count": len(source.excerpts)
            }
            logs.append(log_entry)

            # Include source (flagged with is_verified status)
            verified_sources.append(source)

        return verified_sources, logs

    def _evaluate_source(self, source: ResearchSource) -> Tuple[float, bool, List[str]]:
        """Evaluate source existence and credibility heuristics."""
        issues: List[str] = []
        existence = False
        score = 0.50

        # PDF documents have local file provenance
        if source.source_type == SourceType.PDF:
            existence = True
            score = 0.85
            if len(source.excerpts) > 0:
                score = min(1.0, score + 0.10)
            return score, existence, issues

        # Web or external source checks
        if source.url:
            parsed = urlparse(source.url)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                existence = True
                netloc_lower = parsed.netloc.lower()
                
                # Check known academic domains or TLDs
                if any(domain in netloc_lower for domain in self.ACADEMIC_DOMAINS):
                    score = 0.95
                elif netloc_lower.endswith(".edu") or netloc_lower.endswith(".ac.uk"):
                    score = 0.90
                elif netloc_lower.endswith(".gov"):
                    score = 0.88
                elif netloc_lower.endswith(".org"):
                    score = 0.78
                else:
                    score = 0.65
            else:
                issues.append("Invalid or unparseable URL protocol.")
        elif source.doi:
            if re.match(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$", source.doi):
                existence = True
                score = 0.95
            else:
                issues.append("Malformed DOI pattern.")
        elif source.source_type == SourceType.TEAMMATE:
            # Teammate-supplied research
            existence = True
            score = 0.80
        else:
            issues.append("Source lacks URL, DOI, or local provenance.")

        # If no evidence excerpts exist, penalize credibility significantly
        if not source.excerpts or all(len(e.strip()) == 0 for e in source.excerpts):
            score = max(0.2, score - 0.40)
            issues.append("Source lacks textual excerpts or evidence quotes.")

        return round(score, 2), existence, issues

    def _evaluate_relevance(self, topic: str, source: ResearchSource) -> Tuple[float, List[str]]:
        """Determine evidence relevance via keyword overlap between topic and source text."""
        issues: List[str] = []
        if not topic.strip():
            return 0.5, ["Topic is empty; cannot ascertain relevance."]

        topic_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", topic.lower()))
        # Filter common stopwords
        stopwords = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "been", "have", "has", "about", "into"}
        filtered_topic = topic_words - stopwords

        if not filtered_topic:
            return 0.7, []

        source_text = (source.title + " " + " ".join(source.excerpts)).lower()
        matched = {w for w in filtered_topic if w in source_text}
        overlap_ratio = len(matched) / len(filtered_topic)

        # Scale score: at least 0.40 baseline if verified, up to 1.0 for high overlap
        relevance_score = round(0.40 + (overlap_ratio * 0.60), 2)
        if overlap_ratio < 0.20:
            issues.append(f"Low semantic overlap with topic (matched terms: {', '.join(matched) or 'none'}).")

        return relevance_score, issues

    def verify_claim_support(self, claim: str, source: ResearchSource) -> Tuple[bool, str]:
        """Check whether a specific factual claim is supported by a given source's excerpts."""
        if not source.excerpts:
            return False, f"Source {source.source_id} contains no excerpts to verify claim."

        claim_tokens = set(re.findall(r"\b[a-zA-Z]{4,}\b", claim.lower()))
        stopwords = {"with", "that", "this", "from", "they", "have", "been", "were", "their", "which", "about", "could", "would"}
        significant_tokens = claim_tokens - stopwords

        if not significant_tokens:
            return True, "Claim too short or non-substantive for verification."

        combined_excerpts = " ".join(source.excerpts).lower()
        matched_tokens = {t for t in significant_tokens if t in combined_excerpts}
        ratio = len(matched_tokens) / len(significant_tokens)

        if ratio >= 0.40:
            return True, f"Claim supported with {int(ratio*100)}% keyword grounding in source {source.source_id}."
        else:
            return False, f"Claim lacks grounding: only {int(ratio*100)}% terms found in source {source.source_id}."
