"""Resume parser — extract text from PDF and build skill evidence map."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from job_search_agent.logging import get_logger

logger = get_logger(__name__)


class ResumeData:
    """Parsed resume data with cached text and skill evidence."""

    def __init__(self, text: str, source_path: str):
        self.text = text
        self.source_path = source_path
        self._evidence_cache: dict[str, list[str]] | None = None

    @property
    def sentences(self) -> list[str]:
        """Split resume text into sentences."""
        # Simple sentence splitting — handles bullet points and newlines
        raw = self.text.replace("\n", " ").replace("\r", "")
        # Split on period+space, bullet markers, or multiple spaces
        parts = re.split(r'(?<=[.!?])\s+|[•·▪▸►]\s*|\n+', raw)
        return [s.strip() for s in parts if s.strip() and len(s.strip()) > 10]

    def find_evidence(self, skill: str) -> list[str]:
        """Find resume sentences that mention a specific skill."""
        if self._evidence_cache is not None and skill.lower() in self._evidence_cache:
            return self._evidence_cache[skill.lower()]

        evidence = []
        skill_lower = skill.lower()

        # Also try variations
        variations = _skill_variations(skill)

        for sentence in self.sentences:
            sentence_lower = sentence.lower()
            if any(v in sentence_lower for v in variations):
                # Clean up and truncate very long sentences
                clean = sentence.strip()
                if len(clean) > 300:
                    clean = clean[:297] + "..."
                evidence.append(clean)

        return evidence

    def build_evidence_map(self, skills: list[str]) -> dict[str, list[str]]:
        """Build a complete skill→evidence mapping."""
        self._evidence_cache = {}
        for skill in skills:
            evidence = self.find_evidence(skill)
            self._evidence_cache[skill.lower()] = evidence
        return self._evidence_cache


def _skill_variations(skill: str) -> list[str]:
    """Generate search variations for a skill name."""
    lower = skill.lower()
    variations = [lower]

    # Handle common patterns
    # "FastAPI" → ["fastapi", "fast api"]
    if re.search(r'[a-z][A-Z]', skill):
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', skill).lower()
        variations.append(spaced)

    # "CI/CD" → ["ci/cd", "ci cd", "cicd"]
    if "/" in lower:
        variations.append(lower.replace("/", " "))
        variations.append(lower.replace("/", ""))

    # "LLM-as-a-Judge" → ["llm-as-a-judge", "llm as a judge"]
    if "-" in lower:
        variations.append(lower.replace("-", " "))

    # "pgvector" → ["pgvector", "pg_vector", "pg vector"]
    # "GitHub Actions" → ["github actions"]

    return variations


def parse_pdf(path: str | Path) -> ResumeData:
    """Parse a PDF resume and return structured ResumeData.

    Uses PyMuPDF (fitz) for extraction — fast and local, no external API calls.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Resume PDF not found at {path}")

    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path.suffix}")

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required for PDF parsing. Install with: pip install pymupdf"
        )

    logger.info("parsing_resume", path=str(path))

    doc = fitz.open(str(path))
    text_parts: list[str] = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        if text.strip():
            text_parts.append(text)

    doc.close()

    full_text = "\n\n".join(text_parts)

    if not full_text.strip():
        logger.warning("empty_resume", path=str(path))
        raise ValueError(f"No text content extracted from PDF: {path}")

    logger.info("resume_parsed", path=str(path), char_count=len(full_text))
    return ResumeData(text=full_text, source_path=str(path))


# Cache for the parsed resume
_cached_resume: ResumeData | None = None


def get_resume(path: str | Path | None = None) -> ResumeData | None:
    """Get the parsed resume, using cache if available."""
    global _cached_resume

    if _cached_resume is not None:
        return _cached_resume

    if path is None:
        from job_search_agent.config import get_settings
        path = get_settings().resolve_path(get_settings().resume_path)

    path = Path(path)
    if not path.exists():
        logger.info("no_resume_found", path=str(path))
        return None

    _cached_resume = parse_pdf(path)
    return _cached_resume


def clear_resume_cache() -> None:
    """Clear the cached resume (useful for testing or reload)."""
    global _cached_resume
    _cached_resume = None
