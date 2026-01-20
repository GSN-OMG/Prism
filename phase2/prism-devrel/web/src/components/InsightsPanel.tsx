'use client';

import { ContributionInsight } from '@/types';

interface InsightsPanelProps {
  insights: ContributionInsight[];
}

const typeStyles: Record<ContributionInsight['type'], { bg: string; border: string; label: string; labelBg: string }> = {
  strength: {
    bg: 'bg-green-50',
    border: 'border-green-300',
    label: 'Strength',
    labelBg: 'bg-green-100 text-green-800',
  },
  achievement: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-300',
    label: 'Achievement',
    labelBg: 'bg-yellow-100 text-yellow-800',
  },
  trend: {
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    label: 'Trend',
    labelBg: 'bg-blue-100 text-blue-800',
  },
  growth_area: {
    bg: 'bg-orange-50',
    border: 'border-orange-300',
    label: 'Growth Area',
    labelBg: 'bg-orange-100 text-orange-800',
  },
  recommendation: {
    bg: 'bg-purple-50',
    border: 'border-purple-300',
    label: 'Recommendation',
    labelBg: 'bg-purple-100 text-purple-800',
  },
};

export function InsightsPanel({ insights }: InsightsPanelProps) {
  if (insights.length === 0) {
    return (
      <div className="text-center py-4 text-gray-500 text-sm">
        No specific insights available for this contributor.
      </div>
    );
  }

  // Group insights by type
  const groupedInsights = insights.reduce((acc, insight) => {
    if (!acc[insight.type]) {
      acc[insight.type] = [];
    }
    acc[insight.type].push(insight);
    return acc;
  }, {} as Record<string, ContributionInsight[]>);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">💡</span>
        <h4 className="font-semibold text-gray-900">AI-Generated Insights</h4>
        <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
          {insights.length} insights
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {insights.map((insight, index) => {
          const style = typeStyles[insight.type];
          return (
            <div
              key={`${insight.type}-${index}`}
              className={`p-3 rounded-lg border ${style.bg} ${style.border} animate-fade-in`}
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="flex items-start gap-2">
                <span className="text-xl">{insight.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-900 text-sm">{insight.title}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${style.labelBg}`}>
                      {style.label}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">
                    {insight.description}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Insight Legend */}
      <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200">
        <span className="text-xs text-gray-500">Legend:</span>
        {Object.entries(typeStyles).map(([type, style]) => (
          <span
            key={type}
            className={`text-[10px] px-2 py-0.5 rounded ${style.labelBg}`}
          >
            {style.label}
          </span>
        ))}
      </div>
    </div>
  );
}
