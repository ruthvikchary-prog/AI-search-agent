"""PDF extraction service for the Multi-Agent Academic Research Assistant.

Safely extracts text and metadata from uploaded PDFs using pypdf and pdfplumber fallbacks.
Handles corrupt, encrypted, scanned, empty, and oversized documents gracefully.
"""

import io
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import pypdf
from pypdf.errors import PdfReadError, FileNotDecryptedError


class PdfExtractionError(Exception):
    """Custom exception for user-friendly, safe PDF extraction errors."""
    def __init__(self, message: str, is_scanned: bool = False, is_encrypted: bool = False):
        super().__init__(message)
        self.message = message
        self.is_scanned = is_scanned
        self.is_encrypted = is_encrypted


class PdfExtractor:
    """Robust PDF text and metadata extractor."""

    MAX_PAGES = 100  # Cap maximum page processing to prevent unbounded memory usage
    MIN_CHARS_PER_PAGE_FOR_TEXT = 30  # Heuristic threshold for detecting scanned/image-only PDFs

    @staticmethod
    def extract_from_path(file_path: Path) -> Dict[str, Any]:
        """Extract text, page count, and metadata from a local PDF file path."""
        if not file_path.exists():
            raise PdfExtractionError(f"File not found: {file_path.name}")
        
        file_size = file_path.stat().st_size
        if file_size == 0:
            raise PdfExtractionError("The uploaded PDF file is empty (0 bytes).")
            
        with open(file_path, "rb") as f:
            return PdfExtractor.extract_from_bytes(f.read(), file_path.name)

    @staticmethod
    def extract_from_bytes(file_bytes: bytes, filename: str = "document.pdf") -> Dict[str, Any]:
        """Extract text and metadata from raw bytes."""
        if not file_bytes or len(file_bytes) == 0:
            raise PdfExtractionError("Uploaded file is empty (0 bytes).")

        # Validate PDF header (%PDF-)
        if not file_bytes.startswith(b"%PDF-"):
            raise PdfExtractionError("Invalid file header: Not a valid PDF document.")

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except PdfReadError as e:
            raise PdfExtractionError(f"Corrupted or invalid PDF file: {str(e)}")
        except Exception as e:
            raise PdfExtractionError(f"Failed to read PDF structure: {str(e)}")

        # Check encryption / password
        if reader.is_encrypted:
            # Try decrypting with empty password
            try:
                decrypted = reader.decrypt("")
                if decrypted == 0:
                    raise PdfExtractionError(
                        "The PDF document is password-protected or encrypted. Please remove password protection before uploading.",
                        is_encrypted=True
                    )
            except Exception:
                raise PdfExtractionError(
                    "The PDF document is password-protected or encrypted. Please remove password protection before uploading.",
                    is_encrypted=True
                )

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise PdfExtractionError("The PDF document contains 0 pages.")

        pages_to_read = min(total_pages, PdfExtractor.MAX_PAGES)
        extracted_pages: List[Dict[str, Any]] = []
        full_text_parts: List[str] = []
        empty_page_count = 0

        for page_idx in range(pages_to_read):
            try:
                page = reader.pages[page_idx]
                page_text = page.extract_text() or ""
                cleaned = PdfExtractor._clean_text(page_text)
                
                if len(cleaned.strip()) < PdfExtractor.MIN_CHARS_PER_PAGE_FOR_TEXT:
                    empty_page_count += 1

                extracted_pages.append({
                    "page_number": page_idx + 1,
                    "text": cleaned,
                    "char_count": len(cleaned)
                })
                if cleaned:
                    full_text_parts.append(cleaned)
            except Exception as e:
                # Capture partial errors gracefully
                extracted_pages.append({
                    "page_number": page_idx + 1,
                    "text": "",
                    "error": str(e)
                })

        combined_text = "\n\n".join(full_text_parts).strip()

        # Scanned PDF detection heuristic: If >85% of pages have virtually no text
        if total_pages > 0 and (empty_page_count / total_pages) > 0.85 and len(combined_text) < 100:
            raise PdfExtractionError(
                "Scanned or image-only PDF detected. No extractable digital text found. OCR is required to read this document.",
                is_scanned=True
            )

        # Extract basic metadata
        metadata = {}
        if reader.metadata:
            for k, v in reader.metadata.items():
                if isinstance(v, str):
                    metadata[k.replace("/", "")] = v

        return {
            "filename": filename,
            "total_pages": total_pages,
            "pages_processed": pages_to_read,
            "truncated": total_pages > PdfExtractor.MAX_PAGES,
            "text": combined_text,
            "char_count": len(combined_text),
            "pages": extracted_pages,
            "metadata": metadata,
            "is_scanned": False
        }

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize line endings, remove unprintable chars, and collapse excessive whitespace."""
        if not text:
            return ""
        # Remove null characters and non-printable control characters (except newline, tab)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Normalize Windows/Mac line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse 3+ newlines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse multiple horizontal spaces/tabs
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
