"""Tavily API client for external search and insights."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class TavilySearchResult:
    """Single search result from Tavily."""
    title: str
    url: str
    content: str
    score: float


@dataclass(frozen=True)
class TavilyInsight:
    """Aggregated insight from Tavily search."""
    query: str
    answer: str | None
    results: tuple[TavilySearchResult, ...]
    related_repos: tuple[str, ...]


class TavilyClient:
    """Client for Tavily Search API."""

    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self._api_key:
            raise ValueError("TAVILY_API_KEY not set")

    def search(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 5,
        include_answer: bool = True,
        include_domains: list[str] | None = None,
    ) -> TavilyInsight:
        """Perform a search using Tavily API.

        Args:
            query: Search query
            search_depth: "basic" or "advanced"
            max_results: Maximum number of results
            include_answer: Include AI-generated answer
            include_domains: Limit to specific domains (e.g., ["github.com"])
        """
        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
        }
        if include_domains:
            payload["include_domains"] = include_domains

        response = requests.post(
            f"{self.BASE_URL}/search",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for r in data.get("results", []):
            results.append(
                TavilySearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=float(r.get("score", 0.0)),
                )
            )

        # Extract GitHub repos from results
        related_repos = []
        for r in results:
            if "github.com" in r.url:
                parts = r.url.replace("https://github.com/", "").split("/")
                if len(parts) >= 2:
                    repo = f"{parts[0]}/{parts[1]}"
                    if repo not in related_repos:
                        related_repos.append(repo)

        return TavilyInsight(
            query=query,
            answer=data.get("answer"),
            results=tuple(results),
            related_repos=tuple(related_repos[:5]),
        )

    def search_similar_repos(self, repo_name: str, topic: str) -> TavilyInsight:
        """Search for similar repositories and insights.

        Args:
            repo_name: Current repository (e.g., "openai/openai-agents-python")
            topic: Topic to search for (e.g., "agent framework", "documentation")
        """
        query = f"GitHub repositories similar to {repo_name} {topic} best practices"
        return self.search(
            query=query,
            include_domains=["github.com", "docs.github.com"],
            max_results=5,
        )

    def search_issue_context(self, issue_title: str, issue_body: str, repo_name: str) -> TavilyInsight:
        """Search for external context related to an issue.

        Args:
            issue_title: Issue title
            issue_body: Issue body/description
            repo_name: Repository name
        """
        # Extract key terms from issue
        query = f"{issue_title} solution {repo_name} GitHub"
        return self.search(
            query=query,
            max_results=5,
            include_answer=True,
        )

    def search_docs_best_practices(self, topic: str, repo_type: str = "python agent framework") -> TavilyInsight:
        """Search for documentation best practices.

        Args:
            topic: Documentation topic (e.g., "Redis caching", "OAuth")
            repo_type: Type of repository
        """
        query = f"{topic} documentation best practices {repo_type} GitHub examples"
        return self.search(
            query=query,
            max_results=5,
            include_answer=True,
        )
