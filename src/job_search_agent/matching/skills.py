"""Skill matching with alias resolution and fuzzy matching."""

from __future__ import annotations

from job_search_agent.models.match import SkillMatch

# Skill alias map — maps variations to canonical names
SKILL_ALIASES: dict[str, str] = {
    # Python ecosystem
    "python3": "python",
    "python 3": "python",
    "py": "python",
    "fastapi": "fastapi",
    "fast api": "fastapi",
    "django rest framework": "django",
    "drf": "django",
    "flask": "flask",
    # AI/ML
    "large language model": "llm",
    "large language models": "llm",
    "llms": "llm",
    "retrieval augmented generation": "rag",
    "retrieval-augmented generation": "rag",
    "langchain": "langchain",
    "lang chain": "langchain",
    "langgraph": "langgraph",
    "lang graph": "langgraph",
    "llamaindex": "llamaindex",
    "llama index": "llamaindex",
    "openai": "openai api",
    "openai api": "openai api",
    "gpt-4": "openai api",
    "gpt-4o": "openai api",
    "gpt4": "openai api",
    "chatgpt": "openai api",
    "anthropic": "anthropic api",
    "anthropic api": "anthropic api",
    "claude": "anthropic api",
    "claude api": "anthropic api",
    "ai agents": "ai agents",
    "agentic ai": "ai agents",
    "agent": "ai agents",
    "agents": "ai agents",
    "agent framework": "ai agents",
    "multi-agent": "multi-agent systems",
    "multi agent": "multi-agent systems",
    "multiagent": "multi-agent systems",
    "multi-agent systems": "multi-agent systems",
    "model context protocol": "mcp",
    "mcp": "mcp",
    "tool calling": "tool calling",
    "function calling": "tool calling",
    "tool use": "tool calling",
    "embeddings": "embeddings",
    "embedding": "embeddings",
    "vector embeddings": "embeddings",
    "semantic search": "hybrid search",
    "vector search": "hybrid search",
    "hybrid search": "hybrid search",
    "reranking": "reranking",
    "re-ranking": "reranking",
    "reranker": "reranking",
    # Cloud
    "amazon web services": "aws",
    "aws": "aws",
    "aws bedrock": "aws bedrock",
    "bedrock": "aws bedrock",
    "google cloud": "gcp",
    "gcp": "gcp",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",
    # Databases
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "pg": "postgresql",
    "pgvector": "pgvector",
    "pg_vector": "pgvector",
    # Infrastructure
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "ci cd": "ci/cd",
    "continuous integration": "ci/cd",
    "rest": "rest apis",
    "rest api": "rest apis",
    "rest apis": "rest apis",
    "github actions": "github actions",
    "gh actions": "github actions",
    # Async
    "async python": "async python",
    "asyncio": "async python",
    "async/await": "async python",
    # ML frameworks
    "pytorch": "pytorch",
    "torch": "pytorch",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "hugging face": "hugging face",
    "huggingface": "hugging face",
    "hf": "hugging face",
    # Evaluation
    "llm evaluation": "llm evaluation",
    "llm eval": "llm evaluation",
    "model evaluation": "llm evaluation",
    "llm-as-a-judge": "llm-as-a-judge",
    "llm as a judge": "llm-as-a-judge",
    "llm as judge": "llm-as-a-judge",
    # Safety
    "guardrails": "guardrails",
    "ai guardrails": "guardrails",
    "safety guardrails": "guardrails",
}

# Related skills — if you have skill A, you get partial credit for skill B
RELATED_SKILLS: dict[str, list[str]] = {
    "langchain": ["langgraph", "llamaindex"],
    "langgraph": ["langchain", "ai agents"],
    "ai agents": ["multi-agent systems", "tool calling", "langgraph"],
    "multi-agent systems": ["ai agents", "langgraph"],
    "rag": ["embeddings", "hybrid search", "vector search", "semantic search"],
    "embeddings": ["rag", "hybrid search", "pgvector", "pinecone"],
    "openai api": ["anthropic api", "llm", "tool calling"],
    "anthropic api": ["openai api", "llm", "tool calling"],
    "postgresql": ["pgvector"],
    "pgvector": ["postgresql", "embeddings"],
    "fastapi": ["rest apis", "async python", "pydantic"],
    "pydantic": ["fastapi", "python"],
    "docker": ["kubernetes", "ci/cd"],
    "aws": ["aws bedrock"],
    "aws bedrock": ["aws", "openai api", "anthropic api"],
    "mcp": ["tool calling", "ai agents"],
    "tool calling": ["mcp", "ai agents", "function calling"],
}


def canonicalize_skill(skill: str) -> str:
    """Convert a skill name to its canonical form using the alias map."""
    lower = skill.lower().strip()
    return SKILL_ALIASES.get(lower, lower)


def match_skills(
    candidate_skills: list[str],
    job_required: list[str],
    job_preferred: list[str],
    resume_evidence: dict[str, list[str]] | None = None,
) -> tuple[list[SkillMatch], list[SkillMatch]]:
    """Match candidate skills against job requirements.

    Returns (required_matches, preferred_matches).
    Each match includes whether it was exact, alias, partial, or missing.
    """
    # Canonicalize candidate skills
    candidate_canonical = {canonicalize_skill(s): s for s in candidate_skills}
    candidate_set = set(candidate_canonical.keys())

    # Check for related skill coverage
    candidate_with_related = set(candidate_set)
    for skill in list(candidate_set):
        related = RELATED_SKILLS.get(skill, [])
        for r in related:
            candidate_with_related.add(canonicalize_skill(r))

    def _check_skill(skill: str) -> SkillMatch:
        canonical = canonicalize_skill(skill)

        # Evidence from resume
        evidence = None
        if resume_evidence:
            for evidence_list in [
                resume_evidence.get(skill.lower(), []),
                resume_evidence.get(canonical, []),
            ]:
                if evidence_list:
                    evidence = evidence_list[0]  # First evidence line
                    break

        # Exact match
        if canonical in candidate_set:
            return SkillMatch(
                skill=skill,
                matched=True,
                match_type="exact",
                candidate_evidence=evidence,
            )

        # Alias match (candidate has a differently-named equivalent)
        if canonical in candidate_with_related:
            return SkillMatch(
                skill=skill,
                matched=True,
                match_type="alias",
                candidate_evidence=evidence,
            )

        # Partial match via related skills
        for cand_skill in candidate_set:
            related = RELATED_SKILLS.get(cand_skill, [])
            if canonical in [canonicalize_skill(r) for r in related]:
                return SkillMatch(
                    skill=skill,
                    matched=True,
                    match_type="partial",
                    candidate_evidence=evidence,
                )

        return SkillMatch(
            skill=skill,
            matched=False,
            match_type="missing",
            candidate_evidence=None,
        )

    required_matches = [_check_skill(s) for s in job_required]
    preferred_matches = [_check_skill(s) for s in job_preferred]

    return required_matches, preferred_matches


def compute_skill_score(matches: list[SkillMatch]) -> float:
    """Compute a 0-100 score from skill matches.

    - Exact match: 1.0
    - Alias match: 0.9
    - Partial match: 0.5
    - Missing: 0.0
    """
    if not matches:
        return 100.0  # No requirements = full score

    weights = {"exact": 1.0, "alias": 0.9, "partial": 0.5, "missing": 0.0}
    total = sum(weights.get(m.match_type, 0.0) for m in matches)
    return (total / len(matches)) * 100
