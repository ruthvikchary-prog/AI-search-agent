"""
citation_validator.py - Citation & Source Verification Engine
=============================================================================
Project: Multi-Agent Academic Research Assistant Using CrewAI
Module 3: Source Reviewer & Citation Validation (Student 3: Rahul)
Institution: KG Reddy College of Engineering & Technology
Batch 6 | Professional Elective - IV (Agentic AI)
=============================================================================
Provides algorithmic, heuristic, and metric-driven validation for:
  1. Domain Credibility & Tier Classification (.edu, .gov, arXiv, IEEE, etc.)
  2. Metadata Validation (Author, Date, SSL, URL Health)
  3. Deduplication of Sources
  4. Topic Relevance Scoring
  5. Claim-Evidence Cross-Verification & Hallucination Detection
  6. Citation Syntax & "Phantom Citation" Detection
  7. Quantitative Metrics Computation (Slide 13: Source Quality, Relevance, Count)
"""

import re
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional
import requests
import os
import sys

_curr_dir = os.path.dirname(os.path.abspath(__file__))
if _curr_dir not in sys.path:
    sys.path.insert(0, _curr_dir)

from schemas import (
    CredibilityTier,
    VerificationStatus,
    ClaimSupportStatus,
    RawSource,
    EvaluatedSource,
    ClaimVerificationResult,
    Module3Metrics,
)


# ============================================================================
# 1. Domain Authority & Knowledge Database
# ============================================================================

TIER_1_ACADEMIC_DOMAINS = {
    # Top Academic Repositories & Publishing Houses
    "arxiv.org", "sciencedirect.com", "ieeexplore.ieee.org", "ieee.org",
    "dl.acm.org", "acm.org", "nature.com", "springer.com", "link.springer.com",
    "ncbi.nlm.nih.gov", "nih.gov", "pubmed.ncbi.nlm.nih.gov", "semanticscholar.org",
    "openreview.net", "biorxiv.org", "medrxiv.org", "wiley.com",
    "tandfonline.com", "pnas.org", "cell.com", "thelancet.com", "jstor.org",
    "researchgate.net", "ssrn.com", "frontiersin.org", "oxfordacademic.com",
    "cambridge.org", "hindawi.com", "mdpi.com"
}

TIER_2_AUTHORITATIVE_TECH_DOMAINS = {
    # High-Authority Tech / Research Labs / Standards
    "github.com", "huggingface.co", "openai.com", "deepmind.google",
    "research.google", "microsoft.com", "anthropic.com", "meta.com",
    "nist.gov", "w3.org", "ietf.org", "iso.org", "apache.org",
    "paperswithcode.com", "kaggle.com", "stackoverflow.com", "aws.amazon.com"
}

TIER_3_GENERAL_MEDIA_DOMAINS = {
    # Mainstream Media & General Reference
    "wikipedia.org", "en.wikipedia.org", "reuters.com", "bbc.com", "bbc.co.uk",
    "techcrunch.com", "theverge.com", "wired.com", "forbes.com", "bloomberg.com",
    "mit.edu/news", "technologyreview.com", "zdnet.com", "venturebeat.com"
}

DISQUALIFIED_OR_LOW_TRUST_DOMAINS = {
    # Low-authority forums, personal opinion blogs, content farms
    "quora.com", "reddit.com", "twitter.com", "x.com", "facebook.com",
    "pinterest.com", "buzzfeed.com", "blogspot.com", "wordpress.com",
    "medium.com", "tumblr.com", "tiktok.com", "instagram.com"
}


# ============================================================================
# 2. Citation Validator Engine
# ============================================================================

class CitationValidator:
    """
    Core engine responsible for checking credibility, relevance,
    claim-source grounding, and computing evaluation metrics.
    """

    def __init__(self, quality_threshold: float = 65.0, relevance_threshold: float = 50.0):
        self.quality_threshold = quality_threshold
        self.relevance_threshold = relevance_threshold

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract clean hostname from URL string."""
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url if "://" in url else f"http://{url}")
        netloc = parsed.netloc.lower()
        # Remove port or www prefix if present
        netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc

    @staticmethod
    def check_url_reachability(url: str, timeout_seconds: float = 2.5) -> bool:
        """
        Performs a lightweight HTTP HEAD/GET request to ensure URL is not a 404 or dead link.
        Gracefully handles network offline states.
        """
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return False
        try:
            resp = requests.head(url, timeout=timeout_seconds, allow_redirects=True,
                                 headers={"User-Agent": "AcademicResearchAssistant/1.0"})
            if resp.status_code < 400:
                return True
            # Fallback to GET with stream=True in case server blocks HEAD
            resp = requests.get(url, timeout=timeout_seconds, stream=True,
                                headers={"User-Agent": "AcademicResearchAssistant/1.0"})
            return resp.status_code < 400
        except Exception:
            # If offline or rate-limited, do not fail silently, mark false
            return False

    def evaluate_source_credibility(self, source: RawSource) -> Tuple[CredibilityTier, float, str]:
        """
        Evaluates source authority based on domain, TLD (.edu/.gov), author, and date.
        Returns: (CredibilityTier, credibility_score [0-100], justification_notes)
        """
        domain = self.extract_domain(source.url)
        score = 50.0  # Base neutral score
        tier = CredibilityTier.TIER_3_GENERAL
        notes = []

        # 1. Top-level domain analysis
        if domain.endswith(".edu") or domain.endswith(".edu.in") or domain.endswith(".ac.uk"):
            score = 92.0
            tier = CredibilityTier.TIER_1_ACADEMIC
            notes.append("Accredited Higher Education institution domain (.edu/.ac)")
        elif domain.endswith(".gov") or domain.endswith(".gov.in"):
            score = 94.0
            tier = CredibilityTier.TIER_1_ACADEMIC
            notes.append("Official government institution domain (.gov)")
        elif any(domain == d or domain.endswith("." + d) for d in TIER_1_ACADEMIC_DOMAINS):
            score = 95.0
            tier = CredibilityTier.TIER_1_ACADEMIC
            notes.append("Recognized peer-reviewed academic repository / publisher")
        elif any(domain == d or domain.endswith("." + d) for d in TIER_2_AUTHORITATIVE_TECH_DOMAINS):
            score = 82.0
            tier = CredibilityTier.TIER_2_AUTHORITATIVE
            notes.append("Authoritative industry leader / official technical lab")
        elif any(domain == d or domain.endswith("." + d) for d in TIER_3_GENERAL_MEDIA_DOMAINS):
            score = 65.0
            tier = CredibilityTier.TIER_3_GENERAL
            notes.append("Reputable news / reference publication")
        elif any(domain == d or domain.endswith("." + d) for d in DISQUALIFIED_OR_LOW_TRUST_DOMAINS):
            score = 35.0
            tier = CredibilityTier.TIER_4_UNVERIFIED
            notes.append("Unmoderated social forum or user-generated blog platform")
        else:
            # Unknown domain
            score = 55.0
            notes.append("Standard web domain; requires peer corroboration")

        # 2. Author verification bonus
        if source.author and source.author.strip() and source.author.lower() not in {"unknown", "admin", "staff"}:
            score += 4.0
            notes.append(f"Identified author: {source.author}")
        else:
            notes.append("Missing or generic author attribution")

        # 3. Enhanced Publication Recency & Outdated Check
        recency_tier, recency_delta, recency_note = self.evaluate_recency(source.published_date)
        score += recency_delta
        notes.append(recency_note)

        # Clamp between 0.0 and 100.0
        score = max(0.0, min(100.0, score))
        return tier, round(score, 1), "; ".join(notes)

    @staticmethod
    def evaluate_recency(published_date: Optional[str]) -> Tuple[str, float, str]:
        """
        Determines temporal validity and whether a research paper is current or outdated.
        Returns: (recency_category, score_delta, audit_note)
        Categories:
          - RECENT (2022-2026): Contemporary AI research (< 4 years old) -> +5.0 bonus
          - FOUNDATIONAL (2017-2021): Established baseline literature -> +2.0 bonus
          - LEGACY (2010-2016): Aging research (> 8 years old) -> -5.0 penalty
          - OUTDATED (< 2010): Obsolete for modern AI architectures -> -15.0 penalty
          - UNDATED: Missing date metadata -> 0.0 delta
        """
        if not published_date:
            return "UNDATED", 0.0, "Missing publication date metadata"

        match = re.search(r"\b(19\d{2}|20\d{2})\b", str(published_date))
        if not match:
            return "UNDATED", 0.0, f"Unparseable date: '{published_date}'"

        year = int(match.group(1))

        if year >= 2022:
            return "RECENT", 5.0, f"Recent contemporary research ({year})"
        elif 2017 <= year <= 2021:
            return "FOUNDATIONAL", 2.0, f"Established foundational literature ({year})"
        elif 2010 <= year <= 2016:
            return "LEGACY", -5.0, f"Legacy publication ({year}, > 9 yrs old); may be superseded"
        else:
            return "OUTDATED", -15.0, f"Outdated research ({year}, > 15 yrs old); likely obsolete in fast-moving AI"

    @staticmethod
    def extract_canonical_id(url: str) -> str:
        """Extracts canonical IDs like arXiv IDs, DOIs, or clean normalized URL path."""
        if not url:
            return ""
        clean_url = url.lower().strip()
        # arXiv match: e.g. arxiv.org/abs/1706.03762 or arxiv.org/pdf/1706.03762.pdf
        arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", clean_url)
        if arxiv_match:
            return f"arxiv:{arxiv_match.group(1)}"
        # DOI match
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", clean_url)
        if doi_match:
            return f"doi:{doi_match.group(0)}"
        # General normalized URL (strips protocol, www, and query params)
        parsed = urllib.parse.urlparse(clean_url if "://" in clean_url else f"http://{clean_url}")
        host = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{host}{path}"

    @staticmethod
    def titles_are_duplicates(t1: str, t2: str, threshold: float = 0.80) -> bool:
        """Checks if two paper titles are near-identical via token overlap or containment."""
        if not t1 or not t2:
            return False
        tokens1 = set(re.findall(r"\b[a-z0-9]+\b", t1.lower()))
        tokens2 = set(re.findall(r"\b[a-z0-9]+\b", t2.lower()))
        if not tokens1 or not tokens2:
            return False
        if tokens1 == tokens2:
            return True
        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        containment = len(tokens1 & tokens2) / min(len(tokens1), len(tokens2))
        return jaccard >= threshold or containment >= 0.85

    def calculate_topic_relevance(self, topic: str, source: RawSource) -> float:
        """
        Computes semantic/keyword alignment between research topic and source content.
        Supports acronyms (e.g., AI, ML, LLM), stemming, and title weighting.
        Returns a score from 0.0 to 100.0.
        """
        if not topic:
            return 50.0

        # Tokenize and normalize topic
        stop_words = {
            "a", "an", "the", "and", "or", "in", "on", "at", "for", "with",
            "about", "is", "of", "to", "by", "as", "using", "use", "study", "research", "paper"
        }
        topic_words = [
            w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", topic)
            if w.lower() not in stop_words and len(w) >= 2
        ]

        if not topic_words:
            return 70.0

        combined_text = f"{source.title} {source.snippet}".lower()
        content_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", combined_text)]

        # Helper to check if two words match or share common root/stem
        def tokens_match(w1: str, w2: str) -> bool:
            if w1 == w2:
                return True
            # Singular / plural check
            if w1.rstrip("s") == w2.rstrip("s"):
                return True
            # Prefix root matching for length > 4 (e.g. transform -> transformer)
            if len(w1) > 4 and len(w2) > 4:
                prefix_len = min(len(w1), len(w2), 5)
                if w1[:prefix_len] == w2[:prefix_len]:
                    return True
            return False

        matches = 0
        for tw in topic_words:
            if any(tokens_match(tw, cw) for cw in content_tokens):
                matches += 1

        match_ratio = matches / len(topic_words)

        title_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", source.title.lower())]
        title_matches = sum(1 for tw in topic_words if any(tokens_match(tw, tt) for tt in title_tokens))
        title_bonus = 20.0 if title_matches > 0 else 0.0

        if matches > 0:
            raw_score = 45.0 + (match_ratio * 35.0) + title_bonus
        else:
            raw_score = 10.0

        return min(100.0, round(raw_score, 1))

    def deduplicate_sources(self, sources: List[RawSource]) -> Tuple[List[RawSource], List[RawSource]]:
        """
        Removes identical URLs, mirrored papers (e.g. arXiv abs vs pdf),
        and near-identical paper titles.
        Returns: (unique_sources, duplicate_sources)
        """
        seen_canonical_ids = {}  # id -> first source
        seen_titles = {}         # title -> first source
        unique = []
        duplicates = []

        for src in sources:
            canon_id = self.extract_canonical_id(src.url)
            is_dup = False
            orig_src = None
            dup_reason = ""

            # 1. Canonical ID / URL check
            if canon_id and canon_id in seen_canonical_ids:
                is_dup = True
                orig_src = seen_canonical_ids[canon_id]
                dup_reason = f"Duplicate canonical link/ID ({canon_id}) of source [{orig_src.id}]."

            # 2. Fuzzy Title similarity check
            if not is_dup and src.title:
                for past_title, past_src in seen_titles.items():
                    if self.titles_are_duplicates(src.title, past_title):
                        is_dup = True
                        orig_src = past_src
                        dup_reason = f"Duplicate paper title matching [{orig_src.id}]."
                        break

            if is_dup:
                duplicates.append(src)
            else:
                if canon_id:
                    seen_canonical_ids[canon_id] = src
                if src.title:
                    seen_titles[src.title] = src
                unique.append(src)

        return unique, duplicates

    def review_all_sources(self, topic: str, raw_sources: List[RawSource]) -> List[EvaluatedSource]:
        """
        Evaluates a list of raw sources against credibility and relevance thresholds.
        Filters out low-trust, duplicate, or irrelevant entries.
        """
        unique_sources, duplicates = self.deduplicate_sources(raw_sources)
        results: List[EvaluatedSource] = []

        # Process duplicates first as REJECTED
        for dup in duplicates:
            domain = self.extract_domain(dup.url)
            results.append(
                EvaluatedSource(
                    id=dup.id,
                    title=dup.title,
                    url=dup.url,
                    domain=domain,
                    author=dup.author,
                    published_date=dup.published_date,
                    credibility_tier=CredibilityTier.TIER_4_UNVERIFIED,
                    credibility_score=20.0,
                    relevance_score=0.0,
                    status=VerificationStatus.REJECTED,
                    status_reason="Redundant duplicate source URL or identical paper title.",
                    snippet=dup.snippet
                    , authors=dup.authors, venue=dup.venue, doi=dup.doi,
                    abstract=dup.abstract, metadata_status=dup.metadata_status
                )
            )

        # Process unique sources
        for src in unique_sources:
            domain = self.extract_domain(src.url)
            tier, cred_score, cred_notes = self.evaluate_source_credibility(src)
            rel_score = self.calculate_topic_relevance(topic, src)

            # Determine acceptance
            if cred_score < self.quality_threshold:
                status = VerificationStatus.REJECTED
                reason = f"Failed credibility threshold ({cred_score:.1f} < {self.quality_threshold}). {cred_notes}"
            elif rel_score < self.relevance_threshold:
                status = VerificationStatus.REJECTED
                reason = f"Failed topic relevance threshold ({rel_score:.1f}% < {self.relevance_threshold}%). Content off-topic."
            else:
                status = VerificationStatus.ACCEPTED
                reason = f"Passed authority ({cred_score:.1f} pts) & relevance ({rel_score:.1f}%). {cred_notes}"

            results.append(
                EvaluatedSource(
                    id=src.id,
                    title=src.title,
                    url=src.url,
                    domain=domain,
                    author=src.author,
                    published_date=src.published_date,
                    credibility_tier=tier,
                    credibility_score=cred_score,
                    relevance_score=rel_score,
                    status=status,
                    status_reason=reason,
                    snippet=src.snippet
                    , authors=src.authors, venue=src.venue, doi=src.doi,
                    abstract=src.abstract, metadata_status=src.metadata_status,
                    verification_evidence=[src.abstract] if src.abstract else []
                )
            )

        return results

    # ========================================================================
    # 3. Claim-Evidence Cross-Verification & Hallucination Guard
    # ========================================================================

    def verify_claim_against_sources(
        self,
        claim: str,
        verified_sources: List[EvaluatedSource]
    ) -> ClaimVerificationResult:
        """
        Cross-checks an individual research statement against the verified evidence pool.
        Performs entity matching, negation checks, and numerical verification to identify
        hallucinated facts or unsupported statements.
        """
        claim_cleaned = claim.strip()
        stop_words = {"this", "that", "with", "from", "these", "those", "have", "been", "were", "what"}
        claim_tokens = [
            w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-\.%]+\b", claim_cleaned)
            if len(w) > 2 and w.lower() not in stop_words
        ]

        # Extract numerical assertions in the claim (e.g. "85%", "10x", "2024")
        claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?|\b\d+x\b", claim_cleaned.lower()))

        best_status = ClaimSupportStatus.UNSUPPORTED
        best_confidence = 0.0
        supporting_ids = []
        matching_snippets = []
        notes = []

        for src in verified_sources:
            if src.status != VerificationStatus.ACCEPTED:
                continue

            src_text = f"{src.title} {src.snippet} {src.abstract or ''} {' '.join(src.verification_evidence)}".lower()
            src_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-\.%]+\b", src_text)]

            def token_matches(tok: str, candidates: list) -> bool:
                if tok in candidates:
                    return True
                if any(tok.rstrip("s") == c.rstrip("s") for c in candidates):
                    return True
                if len(tok) > 4:
                    prefix = tok[:4]
                    if any(c.startswith(prefix) for c in candidates if len(c) > 4):
                        return True
                return False

            # Measure token overlap
            matches = [t for t in claim_tokens if token_matches(t, src_tokens)]
            overlap_ratio = len(matches) / max(len(claim_tokens), 1)

            # Check numbers if present
            numbers_matched = True
            if claim_numbers:
                numbers_in_src = set(re.findall(r"\b\d+(?:\.\d+)?%?|\b\d+x\b", src_text))
                if not claim_numbers.issubset(numbers_in_src):
                    numbers_matched = False

            # Check for contradiction / negations
            contradiction_flag = False
            negations = ["not", "fails to", "disproven", "no evidence", "unsupported", "contrary"]
            for neg in negations:
                if neg in src_text and any(t in src_text for t in claim_tokens):
                    contradiction_flag = True
                    break

            if contradiction_flag and overlap_ratio > 0.4:
                best_status = ClaimSupportStatus.CONTRADICTED
                best_confidence = 0.85
                supporting_ids.append(src.id)
                matching_snippets.append(f"[{src.id}] Refuting context: '{src.snippet[:150]}...'")
                notes.append(f"Source [{src.id}] explicitly contradicts or expresses skepticism toward the claim.")
                break

            if overlap_ratio >= 0.5 and numbers_matched:
                best_status = ClaimSupportStatus.SUPPORTED
                confidence = round(min(0.98, 0.6 + (overlap_ratio * 0.35)), 2)
                if confidence > best_confidence:
                    best_confidence = confidence
                supporting_ids.append(src.id)
                matching_snippets.append(f"[{src.id}]: '{src.snippet[:180]}...'")
                notes.append(f"Corroborated by {src.domain} with matching facts.")
            elif overlap_ratio >= 0.3:
                if best_status != ClaimSupportStatus.SUPPORTED:
                    best_status = ClaimSupportStatus.PARTIALLY_SUPPORTED
                    best_confidence = max(best_confidence, round(overlap_ratio, 2))
                    supporting_ids.append(src.id)
                    matching_snippets.append(f"[{src.id}]: '{src.snippet[:120]}...'")
                    notes.append(f"Partial thematic overlap in {src.domain}; specific metrics unconfirmed.")

        if not supporting_ids:
            best_confidence = 0.05
            best_status = (
                ClaimSupportStatus.UNSUPPORTED
                if claim_numbers
                else ClaimSupportStatus.NEEDS_REVIEW
            )
            notes.append("No adequate source passage was retrieved; manual claim review is required.")

        return ClaimVerificationResult(
            claim=claim,
            status=best_status,
            supporting_source_ids=supporting_ids,
            confidence=best_confidence,
            evidence_snippet="\n".join(matching_snippets) if matching_snippets else "None found",
            reviewer_notes=" ".join(notes)
        )

    # ========================================================================
    # 4. Citation Syntax & Mapping Verifier
    # ========================================================================

    def validate_in_text_citations(
        self,
        draft_text: str,
        catalog_sources: List[EvaluatedSource]
    ) -> Dict[str, Any]:
        """
        Parses draft report citations (e.g., [S1], [1], [arXiv:2304.03442])
        and ensures every reference maps to a verified source in the catalog.
        Flags "Phantom Citations" (hallucinated sources).
        """
        # Find citations like [1], [S1], [Source-1], etc.
        citation_matches = re.findall(r"\[([A-Za-z0-9_\-\.:/ ]+)\]", draft_text)
        valid_ids = {src.id.lower(): src for src in catalog_sources if src.status == VerificationStatus.ACCEPTED}
        all_ids = {src.id.lower(): src for src in catalog_sources}

        phantom_citations = []
        valid_citations = []
        cited_rejected_sources = []

        for cit in citation_matches:
            cit_clean = cit.strip().lower()
            if cit_clean in valid_ids:
                valid_citations.append(cit)
            elif cit_clean in all_ids:
                cited_rejected_sources.append(cit)
            else:
                # Exclude markdown link anchors like [^1] or general words if not numeric/source key
                if re.match(r"^(?:s\d+|\d+|ref\d+|source\d+)$", cit_clean):
                    phantom_citations.append(cit)

        return {
            "total_citations_found": len(citation_matches),
            "valid_citations": list(set(valid_citations)),
            "phantom_citations": list(set(phantom_citations)),
            "cited_rejected_sources": list(set(cited_rejected_sources)),
            "integrity_score_pct": (
                round((len(valid_citations) / max(len(citation_matches), 1)) * 100, 1)
                if citation_matches else 100.0
            )
        }

    # ========================================================================
    # 5. Slide 13 Quantitative Evaluation Metrics
    # ========================================================================

    def compute_metrics(
        self,
        raw_sources_count: int,
        evaluated_sources: List[EvaluatedSource],
        claim_verifications: List[ClaimVerificationResult]
    ) -> Module3Metrics:
        """
        Computes formal metrics matching Slide 13 of the project presentation:
          - Source quality (%)
          - Relevance accuracy (%)
          - Verified sources count
        Plus literature survey benchmarks (RAGAs Faithfulness & MIRAGE Noise Filtering).
        """
        accepted = [s for s in evaluated_sources if s.status == VerificationStatus.ACCEPTED]
        rejected = [s for s in evaluated_sources if s.status == VerificationStatus.REJECTED]

        # 1. Source Quality (%)
        if accepted:
            avg_quality = sum(s.credibility_score for s in accepted) / len(accepted)
        else:
            avg_quality = 0.0

        # 2. Relevance Accuracy (%)
        if accepted:
            avg_relevance = sum(s.relevance_score for s in accepted) / len(accepted)
        else:
            avg_relevance = 0.0

        # 3. Faithfulness / Claim Support Rate (%) (RAGAs benchmark)
        supported_claims = sum(
            1 for c in claim_verifications
            if c.status in (ClaimSupportStatus.SUPPORTED, ClaimSupportStatus.PARTIALLY_SUPPORTED)
        )
        faithfulness = (
            (supported_claims / len(claim_verifications)) * 100.0
            if claim_verifications else 100.0
        )

        # 4. Noise Filtered Ratio (%) (MIRAGE benchmark)
        total_eval = len(evaluated_sources)
        noise_pct = (len(rejected) / total_eval * 100.0) if total_eval > 0 else 0.0

        return Module3Metrics(
            total_sources_received=raw_sources_count,
            verified_sources_count=len(accepted),
            rejected_sources_count=len(rejected),
            source_quality_pct=round(avg_quality, 1),
            relevance_accuracy_pct=round(avg_relevance, 1),
            faithfulness_pct=round(faithfulness, 1),
            noise_filtered_pct=round(noise_pct, 1)
        )
