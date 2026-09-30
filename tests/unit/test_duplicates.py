"""Unit tests for duplicate detection."""

from __future__ import annotations

from job_search_agent.models.job import Job
from job_search_agent.tools.search import _deduplicate


class TestDeduplication:
    def test_url_dedup(self):
        jobs = [
            Job(company="A", title="Engineer", canonical_url="https://example.com/1"),
            Job(company="A", title="Engineer", canonical_url="https://example.com/1"),
        ]
        unique, dups = _deduplicate(jobs)
        assert len(unique) == 1
        assert dups == 1

    def test_company_title_dedup(self):
        jobs = [
            Job(company="TechCorp", title="AI Engineer", canonical_url="https://greenhouse.io/1"),
            Job(
                company="TechCorp", title="AI Engineer", canonical_url="https://lever.co/2"
            ),  # Different URL
        ]
        unique, dups = _deduplicate(jobs)
        assert len(unique) == 1
        assert dups == 1

    def test_different_jobs_kept(self):
        jobs = [
            Job(company="A", title="AI Engineer", canonical_url="https://a.com/1"),
            Job(company="B", title="ML Engineer", canonical_url="https://b.com/1"),
            Job(company="A", title="Data Scientist", canonical_url="https://a.com/2"),
        ]
        unique, dups = _deduplicate(jobs)
        assert len(unique) == 3
        assert dups == 0

    def test_cross_provider_duplicate(self, ai_engineer_job, duplicate_job):
        """Same job from different providers should be deduplicated."""
        jobs = [ai_engineer_job, duplicate_job]
        unique, dups = _deduplicate(jobs)
        assert len(unique) == 1
        assert dups == 1

    def test_empty_list(self):
        unique, dups = _deduplicate([])
        assert len(unique) == 0
        assert dups == 0
