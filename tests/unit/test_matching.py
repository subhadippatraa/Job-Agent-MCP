"""Unit tests for the matching/scoring engine."""

from __future__ import annotations

import pytest

from job_search_agent.matching.experience import compute_experience_score
from job_search_agent.matching.scorer import score_job
from job_search_agent.matching.skills import (
    canonicalize_skill,
    compute_skill_score,
    match_skills,
)
from job_search_agent.matching.titles import compute_title_similarity
from job_search_agent.models.candidate import CandidateProfile
from job_search_agent.models.job import Job


class TestSkillCanonicalization:
    def test_exact(self):
        assert canonicalize_skill("Python") == "python"

    def test_alias(self):
        assert canonicalize_skill("LLMs") == "llm"
        assert canonicalize_skill("Retrieval Augmented Generation") == "rag"
        assert canonicalize_skill("function calling") == "tool calling"

    def test_unknown_passthrough(self):
        assert canonicalize_skill("SomeNewTech") == "somenewtecH".lower()


class TestSkillMatching:
    def test_exact_match(self, sample_candidate):
        req_matches, _ = match_skills(
            candidate_skills=sample_candidate.all_skills,
            job_required=["Python", "FastAPI"],
            job_preferred=[],
        )
        assert all(m.matched for m in req_matches)
        assert all(m.match_type == "exact" for m in req_matches)

    def test_alias_match(self, sample_candidate):
        req_matches, _ = match_skills(
            candidate_skills=sample_candidate.all_skills,
            job_required=["LLMs"],  # Should match via alias
            job_preferred=[],
        )
        # LLMs maps to "llm" which isn't directly in candidate skills,
        # but OpenAI API/Anthropic API are related
        assert len(req_matches) == 1

    def test_missing_skill(self, sample_candidate):
        req_matches, _ = match_skills(
            candidate_skills=sample_candidate.all_skills,
            job_required=["C++", "CUDA"],
            job_preferred=[],
        )
        missing = [m for m in req_matches if not m.matched]
        assert len(missing) == 2

    def test_empty_requirements(self, sample_candidate):
        score = compute_skill_score([])
        assert score == 100.0


class TestExperienceMatching:
    def test_candidate_meets_requirement(self):
        score, detail = compute_experience_score(1.8, 1, None)
        assert score == 100.0

    def test_minor_gap_1_8_vs_2(self):
        """Key test: 1.8yr candidate vs 2yr requirement = minor penalty."""
        score, detail = compute_experience_score(1.8, 2, None)
        assert score >= 80.0, f"1.8yr vs 2yr should be minor penalty, got {score}"
        assert score <= 95.0
        assert "short" in detail.lower() or "gap" in detail.lower()

    def test_major_gap_1_8_vs_5(self):
        """Key test: 1.8yr candidate vs 5+ years = significant penalty."""
        score, detail = compute_experience_score(1.8, 5, None)
        assert score < 50.0, f"1.8yr vs 5yr should be significant penalty, got {score}"

    def test_no_requirement(self):
        score, _ = compute_experience_score(1.8, None, None)
        assert score == 100.0

    def test_candidate_experience_unknown(self):
        score, _ = compute_experience_score(None, 2, None)
        assert score == 70.0

    def test_negligible_gap(self):
        score, _ = compute_experience_score(1.7, 2, None)
        assert score >= 85.0


class TestTitleSimilarity:
    def test_exact_match(self):
        score, _ = compute_title_similarity(
            ["AI Engineer"], "AI Engineer"
        )
        assert score == 100.0

    def test_close_match(self):
        score, _ = compute_title_similarity(
            ["AI Engineer"], "Senior AI Engineer"
        )
        # "senior" is stripped in normalization, so this should match
        assert score >= 85.0

    def test_same_group(self):
        score, _ = compute_title_similarity(
            ["AI Engineer"], "Machine Learning Engineer"
        )
        assert score >= 80.0

    def test_weak_match(self):
        score, _ = compute_title_similarity(
            ["AI Engineer"], "Full Stack Software Engineer"
        )
        assert score <= 60.0


class TestCompositeScoring:
    def test_strong_match(self, sample_candidate, ai_engineer_job):
        """AI Engineer job should score well for our candidate."""
        result = score_job(ai_engineer_job, sample_candidate)
        assert result.score >= 70.0, f"Expected strong match, got {result.score}"
        assert result.recommendation in ("exceptional_match", "strong_match", "good_match")
        assert len(result.matched_skills) > 5
        assert result.breakdown is not None

    def test_senior_job_penalty(self, sample_candidate, senior_ml_job):
        """Senior ML job (5+ years) should score lower for 1.8yr candidate."""
        result = score_job(senior_ml_job, sample_candidate)
        assert result.score < 65.0, f"Expected low match for senior role, got {result.score}"
        assert not result.experience_match or result.score < 60

    def test_generic_swe_low_relevance(self, sample_candidate, generic_swe_job):
        """Generic SWE job should score lower than AI-specific jobs."""
        result = score_job(generic_swe_job, sample_candidate)
        ai_result = score_job(
            Job(
                id="x", company="X", title="AI Engineer",
                required_skills=["Python", "RAG", "LangChain", "FastAPI"],
                min_experience=1,
            ),
            sample_candidate,
        )
        assert result.score < ai_result.score, "Generic SWE should score lower than AI job"

    def test_score_explainability(self, sample_candidate, ai_engineer_job):
        """Every score component should be traceable."""
        result = score_job(ai_engineer_job, sample_candidate)
        bd = result.breakdown
        assert bd is not None
        # Verify weighted sum roughly equals total
        weighted_sum = (
            bd.required_skills_score * bd.required_skills_weight
            + bd.preferred_skills_score * bd.preferred_skills_weight
            + bd.experience_score * bd.experience_weight
            + bd.role_similarity_score * bd.role_similarity_weight
            + bd.location_score * bd.location_weight
            + bd.domain_score * bd.domain_weight
        )
        assert abs(weighted_sum - result.score) < 1.0, (
            f"Weighted sum {weighted_sum:.1f} != score {result.score}"
        )

    def test_recommendation_labels(self):
        from job_search_agent.models.match import MatchResult
        assert MatchResult.classify_score(95) == "exceptional_match"
        assert MatchResult.classify_score(85) == "strong_match"
        assert MatchResult.classify_score(75) == "good_match"
        assert MatchResult.classify_score(65) == "possible_match"
        assert MatchResult.classify_score(50) == "low_match"
