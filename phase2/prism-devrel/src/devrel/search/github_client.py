"""GitHub API client for repository docs analysis."""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class DocFile:
    """Single documentation file."""
    path: str
    name: str
    size: int
    url: str
    download_url: str | None


@dataclass(frozen=True)
class RepoDocsStructure:
    """Documentation structure of a repository."""
    repo: str
    docs_path: str
    files: tuple[DocFile, ...]
    directories: tuple[str, ...]
    total_files: int
    topics: tuple[str, ...]  # Extracted from file names


@dataclass(frozen=True)
class DocsComparison:
    """Comparison result between two repos' documentation."""
    target_repo: str
    reference_repo: str
    target_docs: RepoDocsStructure | None
    reference_docs: RepoDocsStructure | None
    missing_topics: tuple[str, ...]  # Topics in reference but not in target
    missing_paths: tuple[str, ...]  # Specific paths missing
    coverage_ratio: float  # 0.0 to 1.0
    suggestions: tuple[str, ...]


class GitHubClient:
    """Client for GitHub API to analyze repository documentation."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self._token = token or os.getenv("GITHUB_TOKEN")
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self._token:
            self._headers["Authorization"] = f"token {self._token}"

    def get_docs_structure(
        self,
        repo: str,
        docs_paths: tuple[str, ...] = ("docs", "doc", "documentation", "guide", "guides"),
    ) -> RepoDocsStructure | None:
        """Get documentation structure of a repository.

        Args:
            repo: Repository in "owner/repo" format
            docs_paths: Possible documentation directory names to check
        """
        for docs_path in docs_paths:
            structure = self._fetch_directory(repo, docs_path)
            if structure:
                return structure

        # Try root-level markdown files
        return self._fetch_root_docs(repo)

    def _fetch_directory(self, repo: str, path: str) -> RepoDocsStructure | None:
        """Fetch contents of a directory."""
        url = f"{self.BASE_URL}/repos/{repo}/contents/{path}"
        try:
            response = requests.get(url, headers=self._headers, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            contents = response.json()
        except requests.RequestException:
            return None

        if not isinstance(contents, list):
            return None

        files = []
        directories = []
        topics = set()

        for item in contents:
            if item["type"] == "file" and item["name"].endswith((".md", ".rst", ".txt")):
                files.append(
                    DocFile(
                        path=item["path"],
                        name=item["name"],
                        size=item.get("size", 0),
                        url=item["html_url"],
                        download_url=item.get("download_url"),
                    )
                )
                # Extract topic from filename
                topic = self._extract_topic(item["name"])
                if topic:
                    topics.add(topic)
            elif item["type"] == "dir":
                directories.append(item["path"])
                # Directory name is also a topic
                topics.add(item["name"].lower())

        # Recursively fetch subdirectories (max depth 2)
        for subdir in directories[:5]:  # Limit to prevent too many API calls
            sub_contents = self._fetch_subdirectory(repo, subdir)
            files.extend(sub_contents["files"])
            topics.update(sub_contents["topics"])

        return RepoDocsStructure(
            repo=repo,
            docs_path=path,
            files=tuple(files),
            directories=tuple(directories),
            total_files=len(files),
            topics=tuple(sorted(topics)),
        )

    def _fetch_subdirectory(self, repo: str, path: str) -> dict:
        """Fetch contents of a subdirectory."""
        url = f"{self.BASE_URL}/repos/{repo}/contents/{path}"
        result = {"files": [], "topics": set()}

        try:
            response = requests.get(url, headers=self._headers, timeout=10)
            if response.status_code != 200:
                return result
            contents = response.json()
        except requests.RequestException:
            return result

        if not isinstance(contents, list):
            return result

        for item in contents:
            if item["type"] == "file" and item["name"].endswith((".md", ".rst", ".txt")):
                result["files"].append(
                    DocFile(
                        path=item["path"],
                        name=item["name"],
                        size=item.get("size", 0),
                        url=item["html_url"],
                        download_url=item.get("download_url"),
                    )
                )
                topic = self._extract_topic(item["name"])
                if topic:
                    result["topics"].add(topic)

        return result

    def _fetch_root_docs(self, repo: str) -> RepoDocsStructure | None:
        """Fetch root-level documentation files."""
        url = f"{self.BASE_URL}/repos/{repo}/contents"
        try:
            response = requests.get(url, headers=self._headers, timeout=10)
            response.raise_for_status()
            contents = response.json()
        except requests.RequestException:
            return None

        files = []
        topics = set()

        for item in contents:
            if item["type"] == "file" and item["name"].lower().endswith(".md"):
                name_lower = item["name"].lower()
                if any(
                    kw in name_lower
                    for kw in ("readme", "contributing", "changelog", "guide", "doc", "tutorial")
                ):
                    files.append(
                        DocFile(
                            path=item["path"],
                            name=item["name"],
                            size=item.get("size", 0),
                            url=item["html_url"],
                            download_url=item.get("download_url"),
                        )
                    )
                    topic = self._extract_topic(item["name"])
                    if topic:
                        topics.add(topic)

        if not files:
            return None

        return RepoDocsStructure(
            repo=repo,
            docs_path=".",
            files=tuple(files),
            directories=(),
            total_files=len(files),
            topics=tuple(sorted(topics)),
        )

    def _extract_topic(self, filename: str) -> str | None:
        """Extract topic from filename."""
        name = filename.lower()
        # Remove extension
        for ext in (".md", ".rst", ".txt"):
            if name.endswith(ext):
                name = name[: -len(ext)]
                break

        # Skip generic names
        if name in ("readme", "index", "home", "main"):
            return None

        return name.replace("-", " ").replace("_", " ").strip()

    def compare_docs(
        self,
        target_repo: str,
        reference_repo: str,
    ) -> DocsComparison:
        """Compare documentation between two repositories.

        Args:
            target_repo: Repository to analyze (e.g., "openai/openai-agents-python")
            reference_repo: Reference repository with good docs
        """
        target_docs = self.get_docs_structure(target_repo)
        ref_docs = self.get_docs_structure(reference_repo)

        if not ref_docs:
            return DocsComparison(
                target_repo=target_repo,
                reference_repo=reference_repo,
                target_docs=target_docs,
                reference_docs=None,
                missing_topics=(),
                missing_paths=(),
                coverage_ratio=1.0 if target_docs else 0.0,
                suggestions=("Reference repository has no documentation to compare.",),
            )

        if not target_docs:
            return DocsComparison(
                target_repo=target_repo,
                reference_repo=reference_repo,
                target_docs=None,
                reference_docs=ref_docs,
                missing_topics=ref_docs.topics,
                missing_paths=tuple(f.path for f in ref_docs.files),
                coverage_ratio=0.0,
                suggestions=(
                    f"Target repository has no docs/ directory.",
                    f"Reference repository has {ref_docs.total_files} documentation files.",
                    f"Consider adding docs for: {', '.join(ref_docs.topics[:5])}",
                ),
            )

        # Compare topics
        target_topics = set(target_docs.topics)
        ref_topics = set(ref_docs.topics)
        missing_topics = tuple(sorted(ref_topics - target_topics))

        # Compare paths (normalized)
        target_names = {f.name.lower() for f in target_docs.files}
        ref_names = {f.name.lower() for f in ref_docs.files}
        missing_names = ref_names - target_names
        missing_paths = tuple(
            f.path for f in ref_docs.files if f.name.lower() in missing_names
        )

        # Calculate coverage
        if ref_topics:
            coverage = len(target_topics & ref_topics) / len(ref_topics)
        else:
            coverage = 1.0

        # Generate suggestions
        suggestions = []
        if missing_topics:
            suggestions.append(f"Missing topics: {', '.join(missing_topics[:5])}")
        if missing_paths:
            suggestions.append(f"Consider adding: {', '.join(missing_paths[:3])}")
        if coverage < 0.5:
            suggestions.append(
                f"Documentation coverage is low ({coverage:.0%}). "
                f"Reference repo has {ref_docs.total_files} docs, target has {target_docs.total_files}."
            )

        return DocsComparison(
            target_repo=target_repo,
            reference_repo=reference_repo,
            target_docs=target_docs,
            reference_docs=ref_docs,
            missing_topics=missing_topics,
            missing_paths=missing_paths,
            coverage_ratio=coverage,
            suggestions=tuple(suggestions) if suggestions else ("Documentation structure is comparable.",),
        )

    def search_similar_repos(self, topic: str, language: str = "python") -> list[str]:
        """Search for repositories with good documentation on a topic.

        Args:
            topic: Topic to search for (e.g., "redis caching")
            language: Programming language
        """
        query = f"{topic} documentation language:{language} stars:>100"
        url = f"{self.BASE_URL}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 5,
        }

        try:
            response = requests.get(url, headers=self._headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            return []

        repos = []
        for item in data.get("items", []):
            repos.append(item["full_name"])

        return repos
