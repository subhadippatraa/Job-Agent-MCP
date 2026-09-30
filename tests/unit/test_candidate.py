"""Unit tests for candidate profile loading."""

from __future__ import annotations

import pytest
import yaml

from job_search_agent.models.candidate import CandidateProfile, load_candidate_profile


class TestCandidateProfile:
    def test_all_skills_deduplicated(self, sample_candidate):
        all_skills = sample_candidate.all_skills
        # Should not have duplicates
        assert len(all_skills) == len(set(s.lower() for s in all_skills))
        # Primary skills should come first
        assert all_skills[0] == "Python"

    def test_optional_fields_none(self):
        profile = CandidateProfile(name="Test")
        assert profile.work_authorization is None
        assert profile.salary_expectation is None
        assert profile.notice_period is None

    def test_load_from_yaml(self, tmp_path):
        data = {
            "name": "Test User",
            "years_experience": 2.5,
            "target_roles": ["AI Engineer"],
            "primary_skills": ["Python", "RAG"],
            "secondary_skills": ["Docker"],
        }
        yaml_path = tmp_path / "candidate.yaml"
        yaml_path.write_text(yaml.dump(data))

        profile = load_candidate_profile(yaml_path)
        assert profile.name == "Test User"
        assert profile.years_experience == 2.5
        assert "Python" in profile.primary_skills

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_candidate_profile(tmp_path / "nonexistent.yaml")

    def test_remote_preference_default(self):
        profile = CandidateProfile(name="Test")
        assert profile.remote_preference == "flexible"
