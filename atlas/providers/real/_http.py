"""Shared HTTP helpers for real provider implementations.

Provides :func:`http_post_json` — a minimal :mod:`urllib`-based JSON
POST that returns the parsed JSON response or raises
:class:`ProviderHTTPError`. Using :mod:`urllib` keeps the providers
dependency-free (no ``requests`` requirement).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ProviderHTTPError(RuntimeError):
    """Raised when a provider HTTP call fails."""

    def __init__(self, message: str, status: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def http_post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """POST ``payload`` as JSON to ``url`` and return the parsed JSON response.

    Raises :class:`ProviderHTTPError` on any failure (network error,
    non-200 status, or JSON parse error).
    """
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(
            req, timeout=timeout
        ) as resp:  # noqa: S310 — trusted internal API calls
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderHTTPError(
            f"HTTP {exc.code} from {url}: {body[:200]}",
            status=exc.code,
            body=body,
        ) from exc
    except urllib.error.URLError as exc:
        raise ProviderHTTPError(f"Network error calling {url}: {exc.reason}") from exc
    except OSError as exc:
        raise ProviderHTTPError(f"OS error calling {url}: {exc}") from exc
    if status != 200:
        raise ProviderHTTPError(
            f"HTTP {status} from {url}: {body[:200]}",
            status=status,
            body=body,
        )
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderHTTPError(f"Invalid JSON from {url}: {exc}") from exc


def http_get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """GET ``url`` and return the parsed JSON response."""
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(
            req, timeout=timeout
        ) as resp:  # noqa: S310 — trusted internal API calls
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderHTTPError(
            f"HTTP {exc.code} from {url}: {body[:200]}",
            status=exc.code,
            body=body,
        ) from exc
    except urllib.error.URLError as exc:
        raise ProviderHTTPError(f"Network error calling {url}: {exc.reason}") from exc
    if status != 200:
        raise ProviderHTTPError(
            f"HTTP {status} from {url}: {body[:200]}",
            status=status,
            body=body,
        )
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderHTTPError(f"Invalid JSON from {url}: {exc}") from exc


def env_key(name: str) -> str | None:
    """Return the value of environment variable ``name`` (or ``None``)."""
    value = os.environ.get(name)
    return value if value else None


__all__ = ["ProviderHTTPError", "env_key", "http_get_json", "http_post_json"]
