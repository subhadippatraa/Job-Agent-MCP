"""Shared test fixtures."""

from __future__ import annotations

import pytest

from job_search_agent.models.candidate import CandidateProfile
from job_search_agent.models.job import Job


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    """Sample candidate matching the specified AI engineer profile."""
    return CandidateProfile(
        name="Test Candidate",
        current_location="India",
        years_experience=1.8,
        target_roles=[
            "AI Engineer",
            "Generative AI Engineer",
            "LLM Engineer",
            "RAG Engineer",
            "Agentic AI Engineer",
        ],
        preferred_locations=["Remote", "Bangalore", "India"],
        preferred_countries=["India", "US"],
        remote_preference="flexible",
        primary_skills=[
            "Python", "FastAPI", "Pydantic", "RAG", "LangGraph",
            "LangChain", "AI Agents", "OpenAI API", "Embeddings",
        ],
        secondary_skills=[
            "PostgreSQL", "Docker", "AWS", "Redis", "CI/CD",
            "Async Python", "REST APIs", "Anthropic API",
        ],
        skills=[
            "Python", "FastAPI", "Pydantic", "RAG", "LangGraph",
            "LangChain", "AI Agents", "OpenAI API", "Embeddings",
            "PostgreSQL", "Docker", "AWS", "Redis", "CI/CD",
            "Async Python", "REST APIs", "Anthropic API",
            "Multi-Agent Systems", "MCP", "Tool Calling",
            "Hybrid Search", "Reranking", "pgvector",
        ],
        domain_interests=["AI/ML", "Generative AI", "Backend Engineering"],
    )


@pytest.fixture
def ai_engineer_job() -> Job:
    """Realistic AI Engineer job posting."""
    return Job(
        id="test-job-1",
        company="TechCorp",
        title="AI Engineer",
        normalized_title="ai engineer",
        location="Bangalore, India",
        country="India",
        remote_type="hybrid",
        employment_type="full_time",
        description=(
            "We are looking for an AI Engineer to build LLM-powered applications. "
            "You will work on RAG pipelines, AI agents, and production ML systems. "
            "Experience with Python, FastAPI, and LangChain is required. "
            "Knowledge of vector databases like pgvector or Pinecone is a plus."
        ),
        required_skills=[
            "Python", "FastAPI", "LangChain", "RAG", "LLM",
            "Docker", "PostgreSQL", "REST APIs", "AI Agents",
            "Embeddings",
        ],
        preferred_skills=[
            "pgvector", "Pinecone", "Kubernetes", "LangGraph",
            "AWS",
        ],
        min_experience=2,
        max_experience=5,
        source="greenhouse",
        ats_provider="greenhouse",
    )


@pytest.fixture
def senior_ml_job() -> Job:
    """Senior ML Engineer job requiring 5+ years."""
    return Job(
        id="test-job-2",
        company="BigTech Inc",
        title="Senior Machine Learning Engineer",
        normalized_title="machine learning engineer",
        location="San Francisco, CA",
        country="US",
        remote_type="onsite",
        employment_type="full_time",
        description=(
            "Looking for a Senior ML Engineer with 5+ years of experience "
            "in production ML systems, PyTorch, and distributed training."
        ),
        required_skills=[
            "Python", "PyTorch", "TensorFlow", "Distributed Systems",
            "Kubernetes", "MLOps", "C++", "CUDA",
        ],
        preferred_skills=["Spark", "Ray", "Triton"],
        min_experience=5,
        max_experience=10,
        source="lever",
        ats_provider="lever",
    )


@pytest.fixture
def generic_swe_job() -> Job:
    """Generic SWE job with weak AI relevance."""
    return Job(
        id="test-job-3",
        company="WebStartup",
        title="Full Stack Software Engineer",
        normalized_title="full stack software engineer",
        location="Remote",
        remote_type="remote",
        employment_type="full_time",
        description=(
            "Build web applications using React, Node.js, and PostgreSQL. "
            "We need someone comfortable with CI/CD and cloud deployment."
        ),
        required_skills=[
            "JavaScript", "React", "Node.js", "PostgreSQL",
            "HTML", "CSS", "Git",
        ],
        preferred_skills=["TypeScript", "Docker", "AWS"],
        min_experience=2,
        max_experience=4,
        source="ashby",
        ats_provider="ashby",
    )


@pytest.fixture
def duplicate_job(ai_engineer_job: Job) -> Job:
    """Duplicate of ai_engineer_job from a different provider."""
    return Job(
        id="test-job-4",
        company="TechCorp",
        title="AI Engineer",
        normalized_title="ai engineer",
        location="Bangalore, India",
        country="India",
        remote_type="hybrid",
        description=ai_engineer_job.description,
        required_skills=ai_engineer_job.required_skills,
        source="lever",  # Different source
        source_url="https://jobs.lever.co/techcorp/different-id",
        canonical_url="https://jobs.lever.co/techcorp/different-id",
        ats_provider="lever",
    )
