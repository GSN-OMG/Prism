'use client';

import { useState } from 'react';
import { PromotionTrace, STAGES, StageName } from '@/types';
import { StageProgress } from './StageProgress';
import { EvidenceBar } from './EvidenceBar';
import { DecisionTrace } from './DecisionTrace';
import { InsightsPanel } from './InsightsPanel';

interface ContributorCardProps {
  trace: PromotionTrace;
}

export function ContributorCard({ trace }: ContributorCardProps) {
  const [showTrace, setShowTrace] = useState(false);
  const [showInsights, setShowInsights] = useState(true);
  const { contributor, evaluation, decision_steps, insights, total_duration_ms, model_used } = trace;

  const currentStageInfo = STAGES[evaluation.current_stage as StageName];
  const suggestedStageInfo = STAGES[evaluation.suggested_stage as StageName];

  return (
    <div className={`bg-white rounded-xl shadow-lg overflow-hidden transition-all duration-300 ${
      evaluation.is_candidate ? 'ring-2 ring-green-500' : ''
    }`}>
      {/* Header */}
      <div className={`px-6 py-4 ${evaluation.is_candidate ? 'bg-gradient-to-r from-green-500 to-green-600' : 'bg-gradient-to-r from-gray-600 to-gray-700'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center text-2xl">
              👤
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">@{contributor.login}</h3>
              <p className="text-white/80 text-sm">
                {contributor.areas.join(' · ')}
              </p>
            </div>
          </div>
          {evaluation.is_candidate && (
            <div className="bg-white text-green-600 px-4 py-2 rounded-full font-bold text-sm animate-pulse">
              ✨ Promotion Candidate
            </div>
          )}
        </div>
      </div>

      {/* Metrics */}
      <div className="px-6 py-4 bg-gray-50 border-b">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-gray-900">{contributor.merged_prs}</div>
            <div className="text-xs text-gray-500">Merged PRs</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900">{contributor.reviews}</div>
            <div className="text-xs text-gray-500">Code Reviews</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900">{contributor.recent_activity_score.toFixed(1)}</div>
            <div className="text-xs text-gray-500">Activity Score</div>
          </div>
        </div>
      </div>

      {/* Stage Progress */}
      <div className="px-6 py-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Stage Progression</h4>
        <StageProgress
          currentStage={evaluation.current_stage}
          suggestedStage={evaluation.suggested_stage}
          isCandidate={evaluation.is_candidate}
        />
      </div>

      {/* Evaluation Result */}
      <div className="px-6 py-4 border-t">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-semibold text-gray-700">Evaluation Result</h4>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Confidence:</span>
            <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${evaluation.confidence >= 0.6 ? 'bg-green-500' : evaluation.confidence >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'}`}
                style={{ width: `${evaluation.confidence * 100}%` }}
              />
            </div>
            <span className="text-xs font-bold">{(evaluation.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Stage transition */}
        <div className="flex items-center justify-center gap-4 py-4 bg-gray-50 rounded-lg mb-4">
          <div className="text-center">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-lg ${
              currentStageInfo ? `bg-${currentStageInfo.color}-500` : 'bg-gray-500'
            }`} style={{ backgroundColor: currentStageInfo?.color === 'gray' ? '#9CA3AF' : currentStageInfo?.color === 'blue' ? '#3B82F6' : currentStageInfo?.color === 'green' ? '#22C55E' : currentStageInfo?.color === 'purple' ? '#A855F7' : '#F97316' }}>
              {currentStageInfo?.label.charAt(0)}
            </div>
            <div className="mt-2 text-sm font-medium">{currentStageInfo?.label || evaluation.current_stage}</div>
            <div className="text-xs text-gray-500">Current</div>
          </div>

          <div className="flex flex-col items-center">
            {evaluation.is_candidate ? (
              <>
                <svg className="w-8 h-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
                <span className="text-xs text-green-600 font-semibold">PROMOTE</span>
              </>
            ) : (
              <>
                <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 12H6" />
                </svg>
                <span className="text-xs text-gray-500">MAINTAIN</span>
              </>
            )}
          </div>

          <div className="text-center">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center font-bold text-lg ${
              evaluation.is_candidate ? 'text-white' : 'text-gray-400 bg-gray-200'
            }`} style={{ backgroundColor: evaluation.is_candidate ? (suggestedStageInfo?.color === 'gray' ? '#9CA3AF' : suggestedStageInfo?.color === 'blue' ? '#3B82F6' : suggestedStageInfo?.color === 'green' ? '#22C55E' : suggestedStageInfo?.color === 'purple' ? '#A855F7' : '#F97316') : undefined }}>
              {suggestedStageInfo?.label.charAt(0)}
            </div>
            <div className="mt-2 text-sm font-medium">{suggestedStageInfo?.label || evaluation.suggested_stage}</div>
            <div className="text-xs text-gray-500">Suggested</div>
          </div>
        </div>

        {/* Recommendation */}
        <div className={`p-4 rounded-lg ${evaluation.is_candidate ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border border-gray-200'}`}>
          <p className={`text-sm ${evaluation.is_candidate ? 'text-green-800' : 'text-gray-700'}`}>
            💡 {evaluation.recommendation}
          </p>
        </div>
      </div>

      {/* Evidence */}
      <div className="px-6 py-4 border-t">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Evaluation Criteria</h4>
        <EvidenceBar evidence={evaluation.evidence} contributor={contributor} />
      </div>

      {/* AI Insights */}
      <div className="px-6 py-4 border-t bg-gradient-to-r from-indigo-50 to-purple-50">
        <button
          onClick={() => setShowInsights(!showInsights)}
          className="w-full flex items-center justify-between mb-3"
        >
          <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
            <span>🤖</span> AI Contribution Insights
            <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
              {insights.length}
            </span>
          </h4>
          <svg
            className={`w-5 h-5 text-gray-500 transition-transform ${showInsights ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {showInsights && <InsightsPanel insights={insights} />}
      </div>

      {/* Decision Trace Toggle */}
      <div className="px-6 py-4 border-t">
        <button
          onClick={() => setShowTrace(!showTrace)}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <span className="text-sm font-medium text-gray-700">
            {showTrace ? 'Hide' : 'Show'} Decision Trace
          </span>
          <svg
            className={`w-5 h-5 text-gray-500 transition-transform ${showTrace ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showTrace && (
          <div className="mt-4">
            <DecisionTrace
              steps={decision_steps}
              modelUsed={model_used}
              durationMs={total_duration_ms}
            />
          </div>
        )}
      </div>
    </div>
  );
}
