from unittest.mock import patch

import pytest

from job_search_agent.providers.generic import _validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/jobs",
        "http://169.254.169.254/latest/meta-data",
        "http://user:password@example.com/jobs",
    ],
)
async def test_rejects_unsafe_job_urls(url):
    with pytest.raises(ValueError):
        await _validate_public_http_url(url)


async def test_rejects_domains_resolving_to_private_addresses():
    result = [(2, 1, 6, "", ("10.0.0.1", 0))]
    with patch("socket.getaddrinfo", return_value=result), pytest.raises(ValueError):
        await _validate_public_http_url("https://jobs.example.com/role")
