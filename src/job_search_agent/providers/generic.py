"""Generic URL analyzer — fetch and parse any job posting URL."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from job_search_agent.config import get_settings
from job_search_agent.logging import get_logger
from job_search_agent.models.job import ATSProvider, Job
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery
from job_search_agent.providers.greenhouse import (
    _detect_remote,
    _extract_experience,
    _extract_skills_from_text,
    _normalize_title,
)

logger = get_logger(__name__)


class GenericProvider(JobProvider):
    """Generic provider that analyzes any job posting URL.

    Fetches the page, extracts structured data using heuristics,
    and normalizes into the canonical Job schema.
    Does not perform automated search — only analyzes user-supplied URLs.
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "generic"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                timeout=settings.http_timeout_seconds,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "JobSearchAgent/0.1 (job-analysis-tool)",
                },
                follow_redirects=True,
            )
        return self._client

    async def search(self, query: SearchQuery) -> ProviderResult:
        """Generic provider doesn't support search — only URL analysis."""
        return ProviderResult(
            provider_name=self.name,
            jobs=[],
            errors=["Generic provider does not support search. Use analyze_job_url instead."],
        )

    async def fetch_job(self, job_url: str) -> Job | None:
        """Fetch and analyze a job posting URL."""
        try:
            resp = await self.client.get(job_url)
            resp.raise_for_status()
            html = resp.text
            return self._parse_html(html, job_url)
        except Exception as e:
            logger.error("generic_fetch_error", url=job_url, error=str(e))
            return None

    def _parse_html(self, html: str, url: str) -> Job:
        """Parse HTML job posting into canonical schema."""
        soup = BeautifulSoup(html, "lxml")

        # Title — try multiple strategies
        title = self._extract_title(soup)

        # Company
        company = self._extract_company(soup, url)

        # Description
        description = self._extract_description(soup)

        # Skills
        required_skills, preferred_skills = _extract_skills_from_text(description)

        # Location
        location = self._extract_location(soup, description)

        # Remote
        remote_type = _detect_remote(location or "", description)

        # Experience
        min_exp, max_exp = _extract_experience(description)

        # ATS detection
        ats_provider = self._detect_ats(url, html)

        return Job(
            company=company,
            title=title,
            normalized_title=_normalize_title(title),
            location=location,
            remote_type=remote_type,
            description=description,
            description_html=str(soup.body) if soup.body else None,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            min_experience=min_exp,
            max_experience=max_exp,
            source="generic",
            source_url=url,
            canonical_url=url,
            application_url=url,
            ats_provider=ats_provider,
            discovered_at=datetime.now(UTC),
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract job title from the page."""
        # Try structured data first
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                import json

                data = json.loads(tag.string or "")
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    return data.get("title", "Unknown")
            except (json.JSONDecodeError, AttributeError):
                pass

        # Try common title elements
        for selector in [
            "h1.job-title",
            "h1.posting-headline",
            "h1[data-qa='job-title']",
            ".job-title h1",
            ".job-header h1",
            "h1",
        ]:
            el = soup.select_one(selector)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)

        # Fall back to <title>
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            # Remove common suffixes
            for suffix in [" - ", " | ", " – "]:
                if suffix in text:
                    return text.split(suffix)[0].strip()
            return text

        return "Unknown"

    def _extract_company(self, soup: BeautifulSoup, url: str) -> str:
        """Extract company name from the page or URL."""
        # Try structured data
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                import json

                data = json.loads(tag.string or "")
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    org = data.get("hiringOrganization", {})
                    if isinstance(org, dict):
                        return org.get("name", "Unknown")
            except (json.JSONDecodeError, AttributeError):
                pass

        # Try meta tags
        for meta in soup.find_all("meta", attrs={"property": "og:site_name"}):
            if meta.get("content"):
                return meta["content"]

        # Extract from URL
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain_parts = parsed.hostname.split(".") if parsed.hostname else []
        if len(domain_parts) >= 2:
            return domain_parts[-2].title()

        return "Unknown"

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract job description text."""
        # Try common description containers
        for selector in [
            ".job-description",
            ".posting-description",
            ".job-details",
            "[data-qa='job-description']",
            ".description",
            "article",
            "main",
            ".content",
        ]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text

        # Fall back to body text
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)[:5000]

        return ""

    def _extract_location(self, soup: BeautifulSoup, description: str) -> str | None:
        """Extract location from structured data or page elements."""
        # Try structured data
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                import json

                data = json.loads(tag.string or "")
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    loc = data.get("jobLocation", {})
                    if isinstance(loc, dict):
                        address = loc.get("address", {})
                        if isinstance(address, dict):
                            parts = [
                                address.get("addressLocality", ""),
                                address.get("addressRegion", ""),
                                address.get("addressCountry", ""),
                            ]
                            location = ", ".join(p for p in parts if p)
                            if location:
                                return location
            except (json.JSONDecodeError, AttributeError):
                pass

        # Try common elements
        for selector in [".location", ".job-location", "[data-qa='job-location']"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) < 100:
                    return text

        return None

    def _detect_ats(self, url: str, html: str) -> ATSProvider:
        """Detect which ATS platform hosts this job."""
        url_lower = url.lower()
        html_lower = html[:2000].lower()

        if "greenhouse.io" in url_lower:
            return ATSProvider.GREENHOUSE
        if "lever.co" in url_lower:
            return ATSProvider.LEVER
        if "ashbyhq.com" in url_lower:
            return ATSProvider.ASHBY
        if "workday.com" in url_lower or "myworkdayjobs.com" in url_lower:
            return ATSProvider.WORKDAY
        if "icims.com" in url_lower:
            return ATSProvider.ICIMS
        if "taleo" in url_lower:
            return ATSProvider.TALEO

        # Check HTML for ATS signatures
        if "greenhouse" in html_lower:
            return ATSProvider.GREENHOUSE
        if "lever" in html_lower:
            return ATSProvider.LEVER

        return ATSProvider.GENERIC

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
