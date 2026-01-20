from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    limit: int | None = None
    remaining: int | None = None
    reset_at: str | None = None
    resource: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.limit is not None:
            out["limit"] = self.limit
        if self.remaining is not None:
            out["remaining"] = self.remaining
        if self.reset_at is not None:
            out["reset_at"] = self.reset_at
        if self.resource is not None:
            out["resource"] = self.resource
        return out


class GitHubApiError(RuntimeError):
    def __init__(
        self, message: str, *, status: int, url: str, rate_limit: RateLimitInfo | None
    ):
        super().__init__(message)
        self.status = status
        self.url = url
        self.rate_limit = rate_limit


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _iso_from_unix_seconds(value: str | None) -> str | None:
    seconds = _parse_int(value)
    if seconds is None:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def _parse_rate_limit(headers: Mapping[str, str] | Any) -> RateLimitInfo | None:
    # `headers` may be an `email.message.Message` (urllib), which is mapping-like.
    limit = _parse_int(headers.get("X-RateLimit-Limit"))
    remaining = _parse_int(headers.get("X-RateLimit-Remaining"))
    reset_at = _iso_from_unix_seconds(headers.get("X-RateLimit-Reset"))
    resource = headers.get("X-RateLimit-Resource")

    if limit is None and remaining is None and reset_at is None and resource is None:
        return None
    return RateLimitInfo(
        limit=limit, remaining=remaining, reset_at=reset_at, resource=resource
    )


class GitHubClient:
    def __init__(
        self,
        *,
        token: str | None,
        base_url: str = "https://api.github.com",
        user_agent: str = "prism-github-context-builder",
        api_version: str = "2022-11-28",
        timeout_sec: float = 30.0,
        urlopen_impl: Callable[..., Any] = urlopen,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._api_version = api_version
        self._timeout_sec = timeout_sec
        self._urlopen = urlopen_impl

        self.rate_limit_events: int = 0
        self.last_rate_limit: RateLimitInfo | None = None

    def _build_url(self, path: str, query: Mapping[str, Any] | None) -> str:
        url = f"{self._base_url}{path}"
        if not query:
            return url
        qs = urlencode({k: v for k, v in query.items() if v is not None})
        return f"{url}?{qs}" if qs else url

    def request_json(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        url = self._build_url(path, query)
        req_headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self._user_agent,
            "X-GitHub-Api-Version": self._api_version,
        }
        if headers:
            req_headers.update(dict(headers))
        if self._token:
            req_headers["Authorization"] = f"Bearer {self._token}"

        request = Request(url, headers=req_headers)

        try:
            with self._urlopen(request, timeout=self._timeout_sec) as response:
                rate_limit = _parse_rate_limit(response.headers)
                if rate_limit is not None:
                    self.last_rate_limit = rate_limit

                if getattr(response, "status", None) == 204:
                    return None

                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw)
        except HTTPError as error:
            rate_limit = _parse_rate_limit(error.headers)
            if rate_limit is not None:
                self.last_rate_limit = rate_limit

            try:
                payload = json.loads(error.read() or b"{}")
            except Exception:
                payload = {}

            message = str(
                payload.get("message") or f"GitHub API request failed ({error.code})"
            )
            if error.code == 403 and "rate limit" in message.lower():
                self.rate_limit_events += 1

            raise GitHubApiError(
                message,
                status=int(error.code),
                url=url,
                rate_limit=rate_limit,
            ) from None
        except URLError as error:
            raise GitHubApiError(
                str(error),
                status=0,
                url=url,
                rate_limit=self.last_rate_limit,
            ) from None

    def paginate(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int = 10,
        item_key: str | None = None,
    ) -> list[Any]:
        all_items: list[Any] = []
        for page in range(1, max_pages + 1):
            payload = self.request_json(
                path,
                query={
                    **(dict(query) if query else {}),
                    "per_page": per_page,
                    "page": page,
                },
            )
            items = payload.get(item_key, []) if item_key else payload
            if not isinstance(items, list):
                raise TypeError(
                    f"Expected list from GitHub pagination (path={path}, item_key={item_key!r})."
                )
            all_items.extend(items)
            if len(items) < per_page:
                break
        return all_items
