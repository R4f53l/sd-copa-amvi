"""
Minimal JSON-over-HTTP client for third-party public APIs.

Uses only the standard library. Every failure (network, HTTP status,
invalid JSON) is raised as ``ExternalServiceError`` so callers can degrade
gracefully instead of breaking the page.
"""

import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 5  # seconds
USER_AGENT = "copa-amvi/1.0 (+https://github.com/R4f53l/sd-copa-amvi)"


class ExternalServiceError(Exception):
    """A third-party API could not be reached or answered badly."""


def get_json(url, params=None, timeout=DEFAULT_TIMEOUT):
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.load(response)
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        raise ExternalServiceError(f"{url}: {exc}") from exc
