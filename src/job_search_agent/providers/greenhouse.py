"""Greenhouse ATS provider — uses the public Job Board API (no auth required)."""

from __future__ import annotations

import contextlib
import re
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from job_search_agent.config import get_settings
from job_search_agent.logging import get_logger
from job_search_agent.models.job import ATSProvider, Job, RemoteType
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery, matches_query

logger = get_logger(__name__)

# Greenhouse public API base
BOARDS_API = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseProvider(JobProvider):
    """Provider for Greenhouse-hosted job boards.

    Uses the public API: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
    No authentication required.
    """

    def __init__(self, board_tokens: list[str] | None = None):
        settings = get_settings()
        self.board_tokens = board_tokens or settings.greenhouse_boards
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "greenhouse"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                timeout=settings.http_timeout_seconds,
                headers={"Accept": "application/json"},
                follow_redirects=True,
            )
        return self._client

    async def search(self, query: SearchQuery) -> ProviderResult:
        """Search across all configured Greenhouse boards."""
        all_jobs: list[Job] = []
        errors: list[str] = []

        if not self.board_tokens:
            return ProviderResult(
                provider_name=self.name,
                jobs=[],
                errors=["No Greenhouse board tokens configured"],
            )

        for token in self.board_tokens:
            try:
                jobs = await self._fetch_board(token, query)
                all_jobs.extend(jobs)
                logger.info(
                    "greenhouse_board_fetched",
                    board=token,
                    count=len(jobs),
                )
            except Exception as e:
                error_msg = f"Greenhouse board '{token}': {e}"
                logger.error("greenhouse_board_error", board=token, error=str(e))
                errors.append(error_msg)

        # Apply limit
        if query.limit and len(all_jobs) > query.limit:
            all_jobs = all_jobs[: query.limit]

        return ProviderResult(
            provider_name=self.name,
            jobs=all_jobs,
            total_found=len(all_jobs),
            errors=errors,
        )

    @retry(
        stop=stop_after_attempt(get_settings().max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _fetch_board(self, token: str, query: SearchQuery) -> list[Job]:
        """Fetch jobs from a single Greenhouse board."""
        url = f"{BOARDS_API}/{token}/jobs"
        params = {"content": "true"}

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        jobs: list[Job] = []
        for raw_job in data.get("jobs", []):
            try:
                job = self._normalize(raw_job, token)
                if matches_query(job, query):
                    jobs.append(job)
            except Exception as e:
                logger.warning(
                    "greenhouse_job_parse_error",
                    board=token,
                    job_id=raw_job.get("id"),
                    error=str(e),
                )

        return jobs

    def _normalize(self, raw: dict, board_token: str) -> Job:
        """Normalize a raw Greenhouse API job into our canonical schema."""
        # Location
        location_parts = []
        for loc in raw.get("location", {}).get("name", "").split(","):
            loc = loc.strip()
            if loc:
                location_parts.append(loc)
        location_str = ", ".join(location_parts) if location_parts else None

        # Description: strip HTML
        desc_html = raw.get("content", "")
        description = _strip_html(desc_html) if desc_html else None

        # Extract skills and requirements from description
        required_skills, preferred_skills = _extract_skills_from_text(description or "")

        # Remote detection
        remote_type = _detect_remote(
            raw.get("location", {}).get("name", ""),
            description or "",
        )

        # Experience detection
        min_exp, max_exp = _extract_experience(description or "")

        # Posted date
        posted_at = None
        if raw.get("updated_at"):
            with contextlib.suppress(ValueError, AttributeError):
                posted_at = datetime.fromisoformat(raw["updated_at"].replace("Z", "+00:00"))

        job_id = str(raw.get("id", ""))
        job_url = f"https://boards.greenhouse.io/{board_token}/jobs/{job_id}"

        return Job(
            external_id=job_id,
            company=board_token.replace("-", " ").title(),
            title=raw.get("title", "Unknown"),
            normalized_title=_normalize_title(raw.get("title", "")),
            location=location_str,
            remote_type=remote_type,
            description=description,
            description_html=desc_html if desc_html else None,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            min_experience=min_exp,
            max_experience=max_exp,
            source="greenhouse",
            source_url=job_url,
            canonical_url=job_url,
            application_url=raw.get("absolute_url"),
            ats_provider=ATSProvider.GREENHOUSE,
            posted_at=posted_at,
            discovered_at=datetime.now(UTC),
            department=_extract_department(raw),
        )

    async def fetch_job(self, job_url: str) -> Job | None:
        """Fetch a single job by its Greenhouse URL."""
        # Extract board token and job ID from URL
        # Format: https://boards.greenhouse.io/{token}/jobs/{id}
        match = re.search(r"boards\.greenhouse\.io/(\w+)/jobs/(\d+)", job_url)
        if not match:
            return None

        token, job_id = match.group(1), match.group(2)
        url = f"{BOARDS_API}/{token}/jobs/{job_id}"
        params = {"content": "true"}

        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            raw = resp.json()
            return self._normalize(raw, token)
        except Exception as e:
            logger.error("greenhouse_fetch_error", url=job_url, error=str(e))
            return None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# --- Utility functions used across providers ---


def _strip_html(html: str) -> str:
    """Strip HTML tags and return clean text."""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator="\n", strip=True)


def _normalize_title(title: str) -> str:
    """Normalize a job title for matching."""
    title = title.lower().strip()
    # Remove common prefixes/suffixes
    for prefix in [
        "senior ",
        "sr. ",
        "sr ",
        "junior ",
        "jr. ",
        "jr ",
        "lead ",
        "staff ",
        "principal ",
    ]:
        if title.startswith(prefix):
            title = title[len(prefix) :]
    # Remove parenthetical clarifications
    title = re.sub(r"\([^)]*\)", "", title).strip()
    # Remove extra whitespace
    title = re.sub(r"\s+", " ", title)
    return title


def _detect_remote(location: str, description: str) -> RemoteType:
    """Detect remote work type from location and description text."""
    text = f"{location} {description}".lower()
    if "hybrid" in text:
        return RemoteType.HYBRID
    if "remote" in text:
        return RemoteType.REMOTE
    if "on-site" in text or "onsite" in text or "in-office" in text:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _extract_experience(text: str) -> tuple[int | None, int | None]:
    """Extract min/max years of experience from text.

    Only returns values when explicitly stated — never infers.
    """
    # Common patterns: "3+ years", "3-5 years", "3 to 5 years", "minimum 3 years"
    patterns = [
        r"experience\s*:\s*(\d+)\+?\s*years?",
        r"(\d+)\s*[-–to]+\s*(\d+)\s*(?:\+\s*)?years?\s*(?:of\s+)?(?:experience|exp)",
        r"(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)",
        r"minimum\s*(?:of\s+)?(\d+)\s*years?",
        r"at\s*least\s*(\d+)\s*years?",
        r"(\d+)\s*[-–to]+\s*(\d+)\s*(?:\+\s*)?(?:yrs?|years?)",
        r"(\d+)\+?\s*(?:yrs?)\s*(?:of\s+)?(?:experience|exp)",
    ]

    text_lower = text.lower()

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return int(groups[0]), int(groups[1])
            elif len(groups) == 1:
                return int(groups[0]), None
            break

    return None, None


def _extract_skills_from_text(text: str) -> tuple[list[str], list[str]]:
    """Extract required and preferred skills from job description text.

    This is a basic keyword-based extractor. LLM can enhance this later.
    """
    # Common technical skills to look for
    known_skills = [
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "Go",
        "Rust",
        "C++",
        "React",
        "Next.js",
        "Node.js",
        "FastAPI",
        "Django",
        "Flask",
        "AWS",
        "GCP",
        "Azure",
        "Docker",
        "Kubernetes",
        "Terraform",
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "Redis",
        "Elasticsearch",
        "LangChain",
        "LangGraph",
        "LlamaIndex",
        "RAG",
        "LLM",
        "OpenAI",
        "Anthropic",
        "GPT",
        "Claude",
        "Gemini",
        "PyTorch",
        "TensorFlow",
        "Hugging Face",
        "MLOps",
        "CI/CD",
        "GitHub Actions",
        "Jenkins",
        "REST",
        "GraphQL",
        "gRPC",
        "Pydantic",
        "SQLAlchemy",
        "Celery",
        "pgvector",
        "Pinecone",
        "Weaviate",
        "ChromaDB",
        "Embeddings",
        "Vector Search",
        "Semantic Search",
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "Computer Vision",
        "Agents",
        "Multi-Agent",
        "Tool Calling",
        "Function Calling",
        "MCP",
        "Model Context Protocol",
    ]

    text_lower = text.lower()
    found_required: list[str] = []
    found_preferred: list[str] = []

    # Try to find sections
    req_section = ""
    pref_section = ""

    # Look for "Required" / "Must have" sections
    req_match = re.search(
        r"(?:required|must\s+have|requirements|qualifications)[:\s]*(.*?)(?=preferred|nice|bonus|about|$)",
        text_lower,
        re.DOTALL,
    )
    if req_match:
        req_section = req_match.group(1)

    pref_match = re.search(
        r"(?:preferred|nice\s+to\s+have|bonus|plus)[:\s]*(.*?)(?=about|$)",
        text_lower,
        re.DOTALL,
    )
    if pref_match:
        pref_section = pref_match.group(1)

    for skill in known_skills:
        skill_lower = skill.lower()
        pattern = rf"(?<!\w){re.escape(skill_lower)}(?!\w)"
        if re.search(pattern, text_lower):
            if req_section and re.search(pattern, req_section):
                found_required.append(skill)
            elif pref_section and re.search(pattern, pref_section):
                found_preferred.append(skill)
            else:
                # Default to required if we can't determine section
                found_required.append(skill)

    return found_required, found_preferred


def _extract_department(raw: dict) -> str | None:
    """Extract department from Greenhouse API response."""
    departments = raw.get("departments", [])
    if departments:
        name = departments[0].get("name")
        return str(name) if name is not None else None
    return None
