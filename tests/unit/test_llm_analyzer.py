"""Unit tests for LLM analyzer — extraction, comparison, merge logic."""

from __future__ import annotations

import json

from job_search_agent.llm.analyzer import (
    _clean_json_response,
    merge_llm_extraction,
)


class TestCleanJsonResponse:
    def test_plain_json(self):
        raw = '{"key": "value"}'
        assert json.loads(_clean_json_response(raw)) == {"key": "value"}

    def test_markdown_fenced(self):
        raw = '```json\n{"key": "value"}\n```'
        assert json.loads(_clean_json_response(raw)) == {"key": "value"}

    def test_with_preamble(self):
        raw = 'Here is the result:\n\n{"key": "value"}\n\nDone.'
        assert json.loads(_clean_json_response(raw)) == {"key": "value"}

    def test_triple_backtick_no_lang(self):
        raw = '```\n{"a": 1}\n```'
        assert json.loads(_clean_json_response(raw)) == {"a": 1}


class TestMergeLlmExtraction:
    def test_no_llm_data(self):
        """When LLM returns None, regex results pass through unchanged."""
        req, pref, min_exp, max_exp, meta = merge_llm_extraction(
            regex_skills=(["Python", "FastAPI"], ["Docker"]),
            regex_experience=(2, 5),
            llm_data=None,
        )
        assert req == ["Python", "FastAPI"]
        assert pref == ["Docker"]
        assert min_exp == 2
        assert max_exp == 5
        assert meta == {}

    def test_llm_adds_new_skills(self):
        """LLM-discovered skills are appended, not replacing regex skills."""
        llm_data = {
            "required_skills": ["Python", "LangChain", "RAG"],
            "preferred_skills": ["Kubernetes"],
        }
        req, pref, min_exp, max_exp, meta = merge_llm_extraction(
            regex_skills=(["Python", "FastAPI"], ["Docker"]),
            regex_experience=(2, None),
            llm_data=llm_data,
        )
        # Python is in both — should not duplicate
        assert "Python" in req
        assert req.count("Python") == 1
        # LangChain and RAG are new from LLM
        assert "LangChain" in req
        assert "RAG" in req
        # FastAPI is from regex
        assert "FastAPI" in req
        # Kubernetes is new preferred
        assert "Kubernetes" in pref
        # Docker is from regex
        assert "Docker" in pref
        # Metadata tracks LLM-only additions
        assert "LangChain" in meta["llm_only_required_skills"]
        assert "RAG" in meta["llm_only_required_skills"]
        assert meta["llm_enhanced"] is True

    def test_llm_fills_experience_gaps(self):
        """LLM fills experience gaps but doesn't override regex."""
        llm_data = {
            "required_skills": [],
            "preferred_skills": [],
            "min_experience_years": 3,
            "max_experience_years": 7,
        }
        # Regex found min but not max
        req, pref, min_exp, max_exp, meta = merge_llm_extraction(
            regex_skills=([], []),
            regex_experience=(2, None),
            llm_data=llm_data,
        )
        assert min_exp == 2  # Regex wins (not None)
        assert max_exp == 7  # LLM fills the gap

    def test_llm_preserves_metadata(self):
        """LLM metadata like seniority, red flags are preserved."""
        llm_data = {
            "required_skills": [],
            "preferred_skills": [],
            "seniority_level": "senior",
            "responsibilities": ["Build RAG pipelines"],
            "tech_stack": ["Python", "LangChain"],
            "red_flags": ["Unpaid trial period"],
            "ai_ml_relevance": 85,
        }
        _, _, _, _, meta = merge_llm_extraction(
            regex_skills=([], []),
            regex_experience=(None, None),
            llm_data=llm_data,
        )
        assert meta["seniority_level"] == "senior"
        assert "Build RAG pipelines" in meta["responsibilities"]
        assert "Unpaid trial period" in meta["red_flags"]
        assert meta["ai_ml_relevance"] == 85

    def test_no_duplicate_across_required_and_preferred(self):
        """Skills in required should not appear in preferred."""
        llm_data = {
            "required_skills": ["Python"],
            "preferred_skills": ["Python", "Go"],
        }
        req, pref, _, _, _ = merge_llm_extraction(
            regex_skills=(["Python"], []),
            regex_experience=(None, None),
            llm_data=llm_data,
        )
        assert "Python" in req
        assert "Python" not in pref  # Already in required
        assert "Go" in pref
