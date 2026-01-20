from __future__ import annotations

from .types import Contributor, PromotionEvidence, PromotionOutput


def evaluate_promotion(contributor: Contributor) -> PromotionOutput:
    current_stage = _infer_stage(contributor)
    suggested_stage = _suggest_next_stage(current_stage, contributor)

    evidence: list[PromotionEvidence] = []
    evidence.append(
        PromotionEvidence(
            criterion="recent_activity",
            status="met" if contributor.recent_activity_score >= 2.5 else "not_met",
            detail=f"recent_activity_score={contributor.recent_activity_score}",
        )
    )
    evidence.append(
        PromotionEvidence(
            criterion="merged_prs",
            status="met" if contributor.merged_prs >= 2 else "not_met",
            detail=f"merged_prs={contributor.merged_prs}",
        )
    )
    evidence.append(
        PromotionEvidence(
            criterion="reviews",
            status="met" if contributor.reviews >= 3 else "not_met",
            detail=f"reviews={contributor.reviews}",
        )
    )

    is_candidate = suggested_stage != current_stage
    confidence = 0.4
    if is_candidate:
        confidence = min(1.0, 0.5 + contributor.recent_activity_score / 10.0)

    recommendation = (
        f"Consider promoting @{contributor.login} to {suggested_stage}."
        if is_candidate
        else f"No promotion suggested for @{contributor.login}."
    )

    return PromotionOutput(
        is_candidate=is_candidate,
        current_stage=current_stage,
        suggested_stage=suggested_stage,
        confidence=float(confidence),
        evidence=tuple(evidence),
        recommendation=recommendation,
    )


def _infer_stage(contributor: Contributor) -> str:
    if contributor.merged_prs >= 30:
        return "MAINTAINER"
    if contributor.merged_prs >= 10:
        return "CORE"
    if contributor.merged_prs >= 2:
        return "REGULAR"
    if contributor.merged_prs >= 1:
        return "FIRST_TIMER"
    return "NEW"


def _suggest_next_stage(current_stage: str, contributor: Contributor) -> str:
    if current_stage == "NEW" and contributor.merged_prs >= 1:
        return "FIRST_TIMER"
    if current_stage == "FIRST_TIMER" and contributor.merged_prs >= 2:
        return "REGULAR"
    if current_stage == "REGULAR" and contributor.merged_prs >= 10:
        return "CORE"
    if current_stage == "CORE" and contributor.merged_prs >= 30:
        return "MAINTAINER"
    return current_stage
