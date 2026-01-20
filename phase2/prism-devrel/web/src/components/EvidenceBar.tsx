'use client';

import { PromotionEvidence } from '@/types';

interface EvidenceBarProps {
  evidence: PromotionEvidence[];
  contributor: {
    recent_activity_score: number;
    merged_prs: number;
    reviews: number;
  };
}

const statusColors: Record<string, { bg: string; text: string; border: string }> = {
  met: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-500' },
  exceeds: { bg: 'bg-green-200', text: 'text-green-900', border: 'border-green-600' },
  strong: { bg: 'bg-green-200', text: 'text-green-900', border: 'border-green-600' },
  moderate: { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-500' },
  positive: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-500' },
  aligned: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-500' },
  broad: { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-500' },
  not_met: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-500' },
  below: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-500' },
  low: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-500' },
};

const pathIcons: Record<string, string> = {
  development_path: '💻',
  reviewer_path: '👀',
  balanced_path: '⚖️',
  activity_level: '📈',
  areas_of_contribution: '🎯',
};

export function EvidenceBar({ evidence, contributor }: EvidenceBarProps) {
  const getProgressInfo = (criterion: string): { value: number; max: number; threshold: number } | null => {
    switch (criterion) {
      case 'development_path':
        return { value: contributor.merged_prs, max: 10, threshold: 8 };
      case 'reviewer_path':
        return { value: contributor.reviews, max: 10, threshold: 8 };
      case 'balanced_path':
        // Show combined progress
        const prsProgress = Math.min(contributor.merged_prs / 3, 1) * 50;
        const reviewsProgress = Math.min(contributor.reviews / 5, 1) * 50;
        return { value: prsProgress + reviewsProgress, max: 100, threshold: 100 };
      case 'activity_level':
        return { value: contributor.recent_activity_score, max: 3, threshold: 1.5 };
      default:
        return null;
    }
  };

  const getProgressColor = (status: string): string => {
    if (['met', 'exceeds', 'strong'].includes(status)) return 'bg-green-500';
    if (['moderate', 'positive', 'aligned'].includes(status)) return 'bg-yellow-500';
    return 'bg-red-400';
  };

  const formatCriterionName = (criterion: string): string => {
    return criterion
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };

  return (
    <div className="space-y-3">
      {evidence.map((e, index) => {
        const colors = statusColors[e.status] || statusColors.moderate;
        const progressInfo = getProgressInfo(e.criterion);
        const icon = pathIcons[e.criterion] || '📋';
        const isQualified = e.detail.includes('QUALIFIED');

        return (
          <div
            key={e.criterion}
            className={`p-3 rounded-lg border-l-4 ${colors.bg} ${colors.border} animate-fade-in ${isQualified ? 'ring-2 ring-green-400' : ''}`}
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-gray-900 flex items-center gap-2">
                <span>{icon}</span>
                {formatCriterionName(e.criterion)}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${colors.bg} ${colors.text} font-semibold`}>
                {isQualified ? '✓ QUALIFIED' : e.status.toUpperCase()}
              </span>
            </div>

            {/* Progress bar for path criteria */}
            {progressInfo && (
              <div className="mt-2">
                <div className="h-3 bg-gray-200 rounded-full overflow-hidden relative">
                  <div
                    className={`h-full rounded-full transition-all duration-1000 ${getProgressColor(e.status)}`}
                    style={{ width: `${Math.min(100, (progressInfo.value / progressInfo.max) * 100)}%` }}
                  />
                  {/* Threshold marker */}
                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-gray-800"
                    style={{ left: `${(progressInfo.threshold / progressInfo.max) * 100}%` }}
                  >
                    <div className="absolute -top-5 left-1/2 transform -translate-x-1/2 text-[10px] text-gray-500 whitespace-nowrap">
                      threshold
                    </div>
                  </div>
                </div>
              </div>
            )}

            <p className="text-sm text-gray-600 mt-2">{e.detail}</p>
          </div>
        );
      })}

      {/* Summary */}
      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          <strong>승격 조건:</strong> Development (8+ PRs) <strong>또는</strong> Reviewer (8+ reviews) <strong>또는</strong> Balanced (3+ PRs & 5+ reviews) 중 하나 충족
        </p>
      </div>
    </div>
  );
}
