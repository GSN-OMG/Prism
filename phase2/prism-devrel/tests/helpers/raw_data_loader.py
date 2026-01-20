"""Load raw_data CSV files and convert to internal types."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from devrel.agents.types import Contributor

# 봇 및 CI/CD 계정 패턴
BOT_PATTERNS = (
    "[bot]",
    "github-actions",
    "dependabot",
    "renovate",
    "copilot",
    "chatgpt-codex-connector",
    "codecov",
    "stale",
    "mergify",
    "semantic-release",
)


def is_bot_account(login: str) -> bool:
    """Check if the login is a bot or CI/CD account."""
    login_lower = login.lower()
    for pattern in BOT_PATTERNS:
        if pattern in login_lower:
            return True
    return False


def raw_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "raw_data"


@dataclass
class UserActivity:
    user_id: str
    action: str
    reference: str
    occurred_at: datetime


@dataclass
class RepoUser:
    user_id: str
    role: str


def load_repo_users(repo: str | None = None) -> list[RepoUser]:
    """Load repo_user.csv and return list of RepoUser."""
    path = raw_data_dir() / "repo_user.csv"
    users: list[RepoUser] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if repo and row["repo_full_name"] != repo:
                continue
            users.append(RepoUser(user_id=row["user_id"], role=row["role"]))
    return users


def load_user_activities(repo: str | None = None) -> list[UserActivity]:
    """Load repo_user_activity.csv and return list of UserActivity."""
    path = raw_data_dir() / "repo_user_activity.csv"
    activities: list[UserActivity] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if repo and row["repo_full_name"] != repo:
                continue
            occurred_at = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
            activities.append(
                UserActivity(
                    user_id=row["user_id"],
                    action=row["action"],
                    reference=row["reference"],
                    occurred_at=occurred_at,
                )
            )
    return activities


def infer_areas_from_activities(activities: list[UserActivity]) -> list[str]:
    """Infer contributor areas from their activity patterns."""
    areas: set[str] = set()
    for act in activities:
        if act.action == "reviewed":
            areas.add("code-review")
        elif act.action == "pr_opened":
            areas.add("development")
        elif act.action == "issue_opened":
            areas.add("issue-reporting")
        elif act.action == "commented":
            areas.add("community")
    return sorted(areas)


def compute_activity_score(activities: list[UserActivity], days: int = 30) -> float:
    """Compute recent activity score based on last N days."""
    if not activities:
        return 0.0
    now = max(a.occurred_at for a in activities)
    cutoff = now.timestamp() - (days * 86400)
    recent = [a for a in activities if a.occurred_at.timestamp() >= cutoff]
    return round(len(recent) / 10.0, 2)  # Normalize to reasonable range


def build_contributors_from_raw_data(
    repo: str | None = None,
    exclude_bots: bool = True,
) -> list[Contributor]:
    """Build Contributor objects from raw_data CSVs.

    Args:
        repo: Repository name to filter by (e.g., "openai/openai-agents-python")
        exclude_bots: If True, exclude bot and CI/CD accounts (default: True)
    """
    users = load_repo_users(repo)
    activities = load_user_activities(repo)

    # Group activities by user
    user_activities: dict[str, list[UserActivity]] = defaultdict(list)
    for act in activities:
        user_activities[act.user_id].append(act)

    contributors: list[Contributor] = []
    for user in users:
        # Skip bots if exclude_bots is True
        if exclude_bots and is_bot_account(user.user_id):
            continue

        user_acts = user_activities.get(user.user_id, [])
        if not user_acts:
            continue  # Skip users with no activity

        # Count specific actions
        pr_count = sum(1 for a in user_acts if a.action == "pr_opened")
        review_count = sum(1 for a in user_acts if a.action == "reviewed")

        # Get date range
        dates = sorted(a.occurred_at for a in user_acts)
        first_date = dates[0].strftime("%Y-%m-%d") if dates else None
        last_date = dates[-1].strftime("%Y-%m-%d") if dates else None

        contributors.append(
            Contributor(
                login=user.user_id,
                areas=tuple(infer_areas_from_activities(user_acts)),
                recent_activity_score=compute_activity_score(user_acts),
                merged_prs=pr_count,
                reviews=review_count,
                first_contribution_date=first_date,
                last_contribution_date=last_date,
            )
        )

    return contributors


def get_active_contributors(
    repo: str | None = None,
    min_activity: int = 3,
    exclude_bots: bool = True,
) -> list[Contributor]:
    """Get contributors with minimum activity threshold.

    Args:
        repo: Repository name to filter by
        min_activity: Minimum merged_prs + reviews count
        exclude_bots: If True, exclude bot and CI/CD accounts (default: True)
    """
    all_contributors = build_contributors_from_raw_data(repo, exclude_bots=exclude_bots)
    return [c for c in all_contributors if c.merged_prs + c.reviews >= min_activity]


def get_issue_numbers_from_activities(repo: str | None = None) -> list[int]:
    """Extract issue numbers from activity references."""
    activities = load_user_activities(repo)
    issue_numbers: set[int] = set()
    for act in activities:
        if "/issues/" in act.reference:
            try:
                num = int(act.reference.split("/issues/")[-1])
                issue_numbers.add(num)
            except ValueError:
                pass
    return sorted(issue_numbers)
