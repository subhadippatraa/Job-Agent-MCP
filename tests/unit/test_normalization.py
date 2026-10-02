"""Unit tests for job normalization and parsing."""

from __future__ import annotations

from job_search_agent.models.job import RemoteType
from job_search_agent.providers.greenhouse import (
    _detect_remote,
    _extract_experience,
    _extract_skills_from_text,
    _normalize_title,
)


class TestTitleNormalization:
    def test_removes_seniority_prefix(self):
        assert _normalize_title("Senior AI Engineer") == "ai engineer"
        assert _normalize_title("Sr. ML Engineer") == "ml engineer"
        assert _normalize_title("Junior Python Developer") == "python developer"
        assert _normalize_title("Lead Data Scientist") == "data scientist"
        assert _normalize_title("Staff Engineer") == "engineer"

    def test_removes_parenthetical(self):
        assert _normalize_title("AI Engineer (Remote)") == "ai engineer"
        assert _normalize_title("Engineer (ML/AI)") == "engineer"

    def test_preserves_core_title(self):
        assert _normalize_title("AI Engineer") == "ai engineer"
        assert _normalize_title("RAG Engineer") == "rag engineer"


class TestRemoteDetection:
    def test_remote(self):
        assert _detect_remote("Remote", "") == RemoteType.REMOTE
        assert _detect_remote("", "This is a fully remote position") == RemoteType.REMOTE

    def test_hybrid(self):
        assert _detect_remote("Hybrid - NYC", "") == RemoteType.HYBRID
        assert _detect_remote("", "Remote with hybrid option") == RemoteType.HYBRID

    def test_onsite(self):
        assert _detect_remote("On-site, SF", "") == RemoteType.ONSITE

    def test_unknown(self):
        assert _detect_remote("Bangalore", "We are in Bangalore") == RemoteType.UNKNOWN


class TestExperienceExtraction:
    def test_plus_pattern(self):
        assert _extract_experience("3+ years of experience") == (3, None)

    def test_experience_prefix(self):
        assert _extract_experience("Experience: 2+ years building AI systems") == (2, None)

    def test_range_pattern(self):
        assert _extract_experience("3-5 years of experience") == (3, 5)

    def test_minimum_pattern(self):
        assert _extract_experience("minimum 2 years") == (2, None)

    def test_at_least_pattern(self):
        assert _extract_experience("at least 4 years") == (4, None)

    def test_no_experience(self):
        assert _extract_experience("We are looking for a great engineer") == (None, None)


class TestSkillExtraction:
    def test_finds_common_skills(self):
        text = "We need experience with Python, FastAPI, and Docker"
        required, preferred = _extract_skills_from_text(text)
        skill_names = [s.lower() for s in required + preferred]
        assert "python" in skill_names
        assert "fastapi" in skill_names
        assert "docker" in skill_names

    def test_empty_text(self):
        required, preferred = _extract_skills_from_text("")
        assert required == []
        assert preferred == []

    def test_ai_skills(self):
        text = "Experience with LangChain, RAG, and OpenAI required. PyTorch is nice to have."
        required, preferred = _extract_skills_from_text(text)
        all_skills = [s.lower() for s in required + preferred]
        assert "langchain" in all_skills
        assert "rag" in all_skills

    def test_does_not_match_inside_words(self):
        required, _ = _extract_skills_from_text(
            "Build trusted systems with ongoing evaluation using JavaScript."
        )
        assert "Rust" not in required
        assert "Go" not in required
        assert "Java" not in required
        assert "JavaScript" in required
