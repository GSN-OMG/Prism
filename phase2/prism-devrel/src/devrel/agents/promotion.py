from __future__ import annotations

from dataclasses import dataclass

from .types import AgentOutput, Contributor


@dataclass(frozen=True, slots=True)
class PromotionRecommendation:
    login: str
    next_stage: str
    rationale: str


def recommend_promotions(contributors: list[Contributor]) -> list[PromotionRecommendation]:
    results: list[PromotionRecommendation] = []
    for contributor in contributors:
        if contributor.recent_activity_score >= 3.0:
            results.append(
                PromotionRecommendation(
                    login=contributor.login,
                    next_stage="REGULAR",
                    rationale="Sustained recent contributions and high activity score.",
                )
            )
    return results


def draft_promotion_comment(recommendation: PromotionRecommendation) -> AgentOutput:
    body = (
        f"Shout-out to @{recommendation.login} for the recent contributions.\n\n"
        f"Recommendation: promote to **{recommendation.next_stage}**.\n"
        f"Rationale: {recommendation.rationale}\n"
    )
    return AgentOutput(title=f"Promotion: {recommendation.login}", body=body)

