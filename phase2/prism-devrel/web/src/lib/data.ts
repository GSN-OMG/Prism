// Data from raw_data CSV files
// This simulates loading from the Python backend

import { Contributor, PromotionTrace, DecisionStep, PromotionOutput, STAGES, StageName } from '@/types';

// Contribution insights generator
interface ContributionInsight {
  type: 'strength' | 'growth_area' | 'achievement' | 'trend' | 'recommendation';
  icon: string;
  title: string;
  description: string;
}

function generateInsights(contributor: Contributor, allContributors: Contributor[]): ContributionInsight[] {
  const insights: ContributionInsight[] = [];

  // Calculate percentiles
  const prPercentile = calculatePercentile(contributor.merged_prs, allContributors.map(c => c.merged_prs));
  const reviewPercentile = calculatePercentile(contributor.reviews, allContributors.map(c => c.reviews));
  const activityPercentile = calculatePercentile(contributor.recent_activity_score, allContributors.map(c => c.recent_activity_score));

  // Strength insights
  if (contributor.merged_prs >= 5) {
    insights.push({
      type: 'strength',
      icon: '💪',
      title: 'Strong Developer',
      description: `Top ${100 - prPercentile}% in PR contributions. ${contributor.merged_prs} merged PRs demonstrate consistent code delivery.`,
    });
  }

  if (contributor.reviews >= 5) {
    insights.push({
      type: 'strength',
      icon: '🔍',
      title: 'Active Reviewer',
      description: `Top ${100 - reviewPercentile}% in code review activity. ${contributor.reviews} reviews show commitment to code quality.`,
    });
  }

  if (contributor.areas.length >= 3) {
    insights.push({
      type: 'strength',
      icon: '🌐',
      title: 'Cross-functional Contributor',
      description: `Active across ${contributor.areas.length} areas: ${contributor.areas.join(', ')}. Versatile team member.`,
    });
  }

  // Achievement insights
  if (contributor.merged_prs >= 8) {
    insights.push({
      type: 'achievement',
      icon: '🏆',
      title: 'Prolific Contributor',
      description: `Achieved 8+ merged PRs milestone. Ready for increased responsibility.`,
    });
  }

  if (contributor.reviews >= 8) {
    insights.push({
      type: 'achievement',
      icon: '⭐',
      title: 'Review Champion',
      description: `Completed 8+ code reviews. Demonstrates mentorship potential.`,
    });
  }

  if (contributor.recent_activity_score >= 1.5) {
    insights.push({
      type: 'achievement',
      icon: '🔥',
      title: 'High Engagement',
      description: `Activity score ${contributor.recent_activity_score.toFixed(1)} indicates sustained engagement with the project.`,
    });
  }

  // Trend insights
  const prToReviewRatio = contributor.merged_prs / Math.max(contributor.reviews, 1);
  if (prToReviewRatio > 3) {
    insights.push({
      type: 'trend',
      icon: '📊',
      title: 'Development Focused',
      description: `PR-to-review ratio of ${prToReviewRatio.toFixed(1)}:1 suggests primary focus on code development over review activities.`,
    });
  } else if (prToReviewRatio < 0.5) {
    insights.push({
      type: 'trend',
      icon: '📊',
      title: 'Review Focused',
      description: `Review-to-PR ratio indicates strong focus on maintaining code quality through reviews.`,
    });
  }

  // Growth area insights
  if (contributor.reviews < 3 && contributor.merged_prs >= 2) {
    insights.push({
      type: 'growth_area',
      icon: '📈',
      title: 'Review Opportunity',
      description: `Consider increasing code review participation to develop mentorship skills and broaden impact.`,
    });
  }

  if (contributor.merged_prs < 3 && contributor.reviews >= 3) {
    insights.push({
      type: 'growth_area',
      icon: '📈',
      title: 'Development Opportunity',
      description: `Strong reviewer who could increase impact by contributing more direct code changes.`,
    });
  }

  if (contributor.recent_activity_score < 1.0) {
    insights.push({
      type: 'growth_area',
      icon: '⏰',
      title: 'Engagement Opportunity',
      description: `Recent activity has decreased. Re-engaging could accelerate promotion timeline.`,
    });
  }

  // Recommendations
  if (contributor.merged_prs >= 5 && contributor.merged_prs < 8) {
    insights.push({
      type: 'recommendation',
      icon: '🎯',
      title: 'Close to Development Path',
      description: `Only ${8 - contributor.merged_prs} more PRs needed for promotion via development path.`,
    });
  }

  if (contributor.reviews >= 5 && contributor.reviews < 8) {
    insights.push({
      type: 'recommendation',
      icon: '🎯',
      title: 'Close to Reviewer Path',
      description: `Only ${8 - contributor.reviews} more reviews needed for promotion via reviewer path.`,
    });
  }

  // Peer comparison
  const avgPRs = allContributors.reduce((sum, c) => sum + c.merged_prs, 0) / allContributors.length;
  const avgReviews = allContributors.reduce((sum, c) => sum + c.reviews, 0) / allContributors.length;

  if (contributor.merged_prs > avgPRs * 1.5) {
    insights.push({
      type: 'trend',
      icon: '📈',
      title: 'Above Average PRs',
      description: `${((contributor.merged_prs / avgPRs - 1) * 100).toFixed(0)}% more PRs than peer average (${avgPRs.toFixed(1)}).`,
    });
  }

  if (contributor.reviews > avgReviews * 1.5) {
    insights.push({
      type: 'trend',
      icon: '📈',
      title: 'Above Average Reviews',
      description: `${((contributor.reviews / avgReviews - 1) * 100).toFixed(0)}% more reviews than peer average (${avgReviews.toFixed(1)}).`,
    });
  }

  return insights.slice(0, 6); // Limit to 6 insights
}

function calculatePercentile(value: number, allValues: number[]): number {
  const sorted = [...allValues].sort((a, b) => a - b);
  const index = sorted.findIndex(v => v >= value);
  return Math.round((index / sorted.length) * 100);
}

// Contributors from raw_data (excluding bots)
export const CONTRIBUTORS: Contributor[] = [
  {
    login: 'AnkanMisra',
    areas: ['code-review', 'community', 'development'],
    recent_activity_score: 0.6,
    merged_prs: 1,
    reviews: 1,
  },
  {
    login: 'HemanthIITJ',
    areas: ['community', 'development'],
    recent_activity_score: 1.0,
    merged_prs: 9,
    reviews: 0,
  },
  {
    login: 'gustavz',
    areas: ['code-review', 'development'],
    recent_activity_score: 1.3,
    merged_prs: 2,
    reviews: 9,
  },
  {
    login: 'habema',
    areas: ['community', 'development', 'issue-reporting'],
    recent_activity_score: 0.4,
    merged_prs: 3,
    reviews: 0,
  },
  {
    login: 'ihower',
    areas: ['code-review', 'community', 'development'],
    recent_activity_score: 2.0,
    merged_prs: 2,
    reviews: 3,
  },
];

// Infer current stage based on merged PRs
function inferStage(contributor: Contributor): StageName {
  if (contributor.merged_prs >= 20) return 'MAINTAINER';
  if (contributor.merged_prs >= 8) return 'CORE';
  if (contributor.merged_prs >= 2) return 'REGULAR';
  if (contributor.merged_prs >= 1) return 'FIRST_TIMER';
  return 'NEW';
}

// Suggest next stage based on multiple criteria
function suggestNextStage(currentStage: StageName, contributor: Contributor): StageName {
  // NEW -> FIRST_TIMER: first PR
  if (currentStage === 'NEW' && contributor.merged_prs >= 1) {
    return 'FIRST_TIMER';
  }

  // FIRST_TIMER -> REGULAR: 2+ PRs
  if (currentStage === 'FIRST_TIMER' && contributor.merged_prs >= 2) {
    return 'REGULAR';
  }

  // REGULAR -> CORE: Multiple paths
  // Path 1: 8+ merged PRs (development focus)
  // Path 2: 8+ reviews (review focus)
  // Path 3: 3+ PRs AND 5+ reviews (balanced)
  if (currentStage === 'REGULAR') {
    const strongDevelopment = contributor.merged_prs >= 8;
    const strongReviewer = contributor.reviews >= 8;
    const balancedContribution = contributor.merged_prs >= 3 && contributor.reviews >= 5;

    if (strongDevelopment || strongReviewer || balancedContribution) {
      return 'CORE';
    }
  }

  // CORE -> MAINTAINER: 20+ PRs AND 10+ reviews
  if (currentStage === 'CORE') {
    if (contributor.merged_prs >= 20 && contributor.reviews >= 10) {
      return 'MAINTAINER';
    }
  }

  return currentStage;
}

// Evaluate promotion with detailed trace and insights
export function evaluatePromotionWithTrace(contributor: Contributor, allContributors: Contributor[] = CONTRIBUTORS): PromotionTrace {
  const startTime = Date.now();
  const decisionSteps: DecisionStep[] = [];

  // Step 1: Load contributor data
  decisionSteps.push({
    step_number: 1,
    step_name: 'Load Contributor Data',
    input: { login: contributor.login },
    output: {
      merged_prs: contributor.merged_prs,
      reviews: contributor.reviews,
      recent_activity_score: contributor.recent_activity_score,
      areas: contributor.areas,
    },
    reasoning: `Loaded metrics for contributor @${contributor.login} from raw_data`,
    timestamp: new Date().toISOString(),
  });

  // Step 2: Infer current stage
  const currentStage = inferStage(contributor);
  decisionSteps.push({
    step_number: 2,
    step_name: 'Infer Current Stage',
    input: { merged_prs: contributor.merged_prs },
    output: { current_stage: currentStage, min_prs_required: STAGES[currentStage].minPRs },
    reasoning: `With ${contributor.merged_prs} merged PRs, contributor qualifies for ${STAGES[currentStage].label} stage (requires >= ${STAGES[currentStage].minPRs} PRs)`,
    timestamp: new Date().toISOString(),
  });

  // Step 3: Evaluate promotion paths (multiple criteria)
  const strongDevelopment = contributor.merged_prs >= 8;
  const strongReviewer = contributor.reviews >= 8;
  const balancedContribution = contributor.merged_prs >= 3 && contributor.reviews >= 5;
  const hasPromotionPath = strongDevelopment || strongReviewer || balancedContribution;

  // Determine which path qualifies
  let promotionPath = 'none';
  if (strongDevelopment) promotionPath = 'development';
  else if (strongReviewer) promotionPath = 'reviewer';
  else if (balancedContribution) promotionPath = 'balanced';

  decisionSteps.push({
    step_number: 3,
    step_name: 'Evaluate Promotion Paths',
    input: {
      merged_prs: contributor.merged_prs,
      reviews: contributor.reviews,
      recent_activity_score: contributor.recent_activity_score,
    },
    output: {
      path_development: { requirement: '8+ PRs', value: contributor.merged_prs, met: strongDevelopment },
      path_reviewer: { requirement: '8+ reviews', value: contributor.reviews, met: strongReviewer },
      path_balanced: { requirement: '3+ PRs AND 5+ reviews', prs: contributor.merged_prs, reviews: contributor.reviews, met: balancedContribution },
      qualified_path: promotionPath,
    },
    reasoning: `Evaluated 3 promotion paths: Development (8+ PRs) ${strongDevelopment ? '✓' : '✗'}, Reviewer (8+ reviews) ${strongReviewer ? '✓' : '✗'}, Balanced (3+ PRs & 5+ reviews) ${balancedContribution ? '✓' : '✗'}. ${hasPromotionPath ? `Qualifies via "${promotionPath}" path.` : 'No path qualified yet.'}`,
    timestamp: new Date().toISOString(),
  });

  // Step 4: Suggest next stage
  const suggestedStage = suggestNextStage(currentStage, contributor);
  const isCandidate = suggestedStage !== currentStage;

  decisionSteps.push({
    step_number: 4,
    step_name: 'Determine Promotion Eligibility',
    input: {
      current_stage: currentStage,
      has_promotion_path: hasPromotionPath,
      qualified_path: promotionPath,
    },
    output: { suggested_stage: suggestedStage, is_candidate: isCandidate },
    reasoning: isCandidate
      ? `✅ PROMOTED: ${STAGES[currentStage].label} → ${STAGES[suggestedStage].label} via "${promotionPath}" path`
      : `Contributor needs to meet one of: 8+ PRs (development), 8+ reviews (reviewer), or 3+ PRs & 5+ reviews (balanced)`,
    timestamp: new Date().toISOString(),
  });

  // Step 5: Calculate confidence
  let confidence = 0.4;
  if (isCandidate) {
    confidence = Math.min(1.0, 0.5 + contributor.recent_activity_score / 10.0);
  }

  decisionSteps.push({
    step_number: 5,
    step_name: 'Calculate Confidence Score',
    input: { is_candidate: isCandidate, recent_activity_score: contributor.recent_activity_score },
    output: { confidence: confidence.toFixed(2) },
    reasoning: isCandidate
      ? `Confidence calculated as 0.5 + (${contributor.recent_activity_score} / 10) = ${confidence.toFixed(2)}`
      : `Base confidence 0.4 applied for non-candidates`,
    timestamp: new Date().toISOString(),
  });

  // Step 6: Generate recommendation
  let recommendation: string;
  if (isCandidate) {
    const pathDescription = promotionPath === 'development' ? 'strong PR contributions'
      : promotionPath === 'reviewer' ? 'excellent code review activity'
      : 'balanced development and review contributions';
    recommendation = `✅ Promote @${contributor.login} from ${STAGES[currentStage].label} to ${STAGES[suggestedStage].label}. Recognized for ${pathDescription} in ${contributor.areas.join(', ')}.`;
  } else {
    const nextSteps = [];
    if (contributor.merged_prs < 8) nextSteps.push(`${8 - contributor.merged_prs} more PRs for development path`);
    if (contributor.reviews < 8) nextSteps.push(`${8 - contributor.reviews} more reviews for reviewer path`);
    recommendation = `@${contributor.login} should continue building contributions. Suggested: ${nextSteps.slice(0, 2).join(' or ')}.`;
  }

  decisionSteps.push({
    step_number: 6,
    step_name: 'Generate Recommendation',
    input: { is_candidate: isCandidate, current_stage: currentStage, suggested_stage: suggestedStage },
    output: { recommendation },
    reasoning: 'Final recommendation generated based on evaluation results',
    timestamp: new Date().toISOString(),
  });

  // Build evidence showing promotion paths
  const evidence = [
    {
      criterion: 'development_path',
      status: strongDevelopment ? 'met' : contributor.merged_prs >= 5 ? 'moderate' : 'below',
      detail: `${contributor.merged_prs}/8 merged PRs for development path${strongDevelopment ? ' ✓ QUALIFIED' : ''}`,
    },
    {
      criterion: 'reviewer_path',
      status: strongReviewer ? 'met' : contributor.reviews >= 5 ? 'moderate' : 'low',
      detail: `${contributor.reviews}/8 code reviews for reviewer path${strongReviewer ? ' ✓ QUALIFIED' : ''}`,
    },
    {
      criterion: 'balanced_path',
      status: balancedContribution ? 'met' : (contributor.merged_prs >= 3 || contributor.reviews >= 5) ? 'moderate' : 'below',
      detail: `${contributor.merged_prs}/3 PRs + ${contributor.reviews}/5 reviews for balanced path${balancedContribution ? ' ✓ QUALIFIED' : ''}`,
    },
    {
      criterion: 'activity_level',
      status: contributor.recent_activity_score >= 1.5 ? 'strong' : contributor.recent_activity_score >= 1.0 ? 'moderate' : 'low',
      detail: `Recent activity score: ${contributor.recent_activity_score}`,
    },
    {
      criterion: 'areas_of_contribution',
      status: contributor.areas.length >= 2 ? 'broad' : 'aligned',
      detail: `Active in: ${contributor.areas.join(', ')}`,
    },
  ];

  const evaluation: PromotionOutput = {
    is_candidate: isCandidate,
    current_stage: currentStage,
    suggested_stage: suggestedStage,
    confidence,
    evidence: evidence as PromotionOutput['evidence'],
    recommendation,
  };

  // Generate insights
  const insights = generateInsights(contributor, allContributors);

  // Add insight generation step to trace
  decisionSteps.push({
    step_number: 7,
    step_name: 'Generate Contribution Insights',
    input: { contributor_login: contributor.login, peer_count: allContributors.length },
    output: {
      insights_count: insights.length,
      insight_types: insights.map(i => i.type),
    },
    reasoning: `Generated ${insights.length} personalized insights based on contribution patterns and peer comparison.`,
    timestamp: new Date().toISOString(),
  });

  return {
    contributor,
    evaluation,
    decision_steps: decisionSteps,
    insights,
    total_duration_ms: Date.now() - startTime,
    model_used: 'rule-based + insights (demo)',
  };
}

// Get all contributors with their evaluations
export function getAllContributorsWithEvaluations(): PromotionTrace[] {
  return CONTRIBUTORS.map(c => evaluatePromotionWithTrace(c, CONTRIBUTORS));
}

// Get contributors list
export function getContributors(): Contributor[] {
  return CONTRIBUTORS;
}
