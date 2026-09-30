"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

# Load .env from project root (two levels up from this file, or cwd)
_project_root = Path(__file__).resolve().parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()  # Try cwd


class MatchWeights(BaseSettings):
    """Configurable weights for the matching algorithm. Must sum to ~1.0."""

    required_skills: float = Field(default=0.35, alias="MATCH_WEIGHT_REQUIRED_SKILLS")
    experience: float = Field(default=0.20, alias="MATCH_WEIGHT_EXPERIENCE")
    role_similarity: float = Field(default=0.15, alias="MATCH_WEIGHT_ROLE_SIMILARITY")
    preferred_skills: float = Field(default=0.10, alias="MATCH_WEIGHT_PREFERRED_SKILLS")
    location: float = Field(default=0.10, alias="MATCH_WEIGHT_LOCATION")
    domain: float = Field(default=0.10, alias="MATCH_WEIGHT_DOMAIN")

    model_config = {"env_prefix": "", "extra": "ignore"}


class Settings(BaseSettings):
    """Central application settings."""

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./jobagent.db",
        alias="DATABASE_URL",
    )

    # Candidate
    candidate_profile_path: str = Field(
        default="profile/candidate.yaml",
        alias="CANDIDATE_PROFILE_PATH",
    )
    resume_path: str = Field(
        default="resume/master_resume.pdf",
        alias="RESUME_PATH",
    )

    # Search defaults
    default_search_limit: int = Field(default=50, alias="DEFAULT_SEARCH_LIMIT")
    default_posted_within_hours: int = Field(default=24, alias="DEFAULT_POSTED_WITHIN_HOURS")
    http_timeout_seconds: int = Field(default=30, alias="HTTP_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")

    # Provider boards (comma-separated strings parsed to lists)
    greenhouse_boards: list[str] = Field(
        default_factory=lambda: ["stripe", "figma"], alias="GREENHOUSE_BOARDS"
    )
    lever_companies: list[str] = Field(default_factory=lambda: ["netflix"], alias="LEVER_COMPANIES")
    ashby_boards: list[str] = Field(default_factory=lambda: ["linear"], alias="ASHBY_BOARDS")

    # LLM
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514", alias="ANTHROPIC_MODEL")
    llm_provider: str = Field(default="none", alias="LLM_PROVIDER")

    # Matching
    match_weights: MatchWeights = Field(default_factory=MatchWeights)
    auto_shortlist_min_score: int = Field(default=75, alias="AUTO_SHORTLIST_MIN_SCORE")

    # Safety
    require_human_approval: bool = Field(
        default=True,
        alias="REQUIRE_HUMAN_APPROVAL",
        description=(
            "When True (default), the agent will NEVER auto-submit applications. "
            "prepare_application returns a prep package, and record_application "
            "only records after the user explicitly confirms submission. "
            "Set to False ONLY if you have an external automation pipeline that "
            "handles approval logic (e.g., a CI/CD workflow with manual gates)."
        ),
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    model_config = {"env_prefix": "", "extra": "ignore", "populate_by_name": True}

    @field_validator("greenhouse_boards", "lever_companies", "ashby_boards", mode="before")
    @classmethod
    def split_comma_list(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.database_url

    @property
    def project_root(self) -> Path:
        return _project_root

    def resolve_path(self, relative: str) -> Path:
        """Resolve a path relative to the project root."""
        p = Path(relative)
        if p.is_absolute():
            return p
        return self.project_root / p


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None
