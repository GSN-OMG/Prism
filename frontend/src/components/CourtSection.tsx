'use client';

import { useState } from 'react';
import {
  CourtResult,
  CourtStageOutput,
  PromptUpdateProposal,
  CourtLesson,
  COURT_STAGES,
  AgentType,
  AGENTS,
  CourtStageStatus,
} from '@/types';

interface CourtSectionProps {
  agent: AgentType;
  courtResult: CourtResult | null;
  isRunning: boolean;
  stageStatus?: CourtStageStatus;
  onRunCourt: () => void;
  onApprovePromptUpdate?: (updateIndex: number) => void;
  onRejectPromptUpdate?: (updateIndex: number) => void;
}

function StageCard({ stage, output }: { stage: string; output: CourtStageOutput }) {
  const [expanded, setExpanded] = useState(true);
  const stageInfo = COURT_STAGES[stage];

  const getStageColor = () => {
    switch (stage) {
      case 'prosecutor':
        return 'border-red-300 bg-red-50';
      case 'defense':
        return 'border-green-300 bg-green-50';
      case 'jury':
        return 'border-blue-300 bg-blue-50';
      case 'judge':
        return 'border-purple-300 bg-purple-50';
      default:
        return 'border-gray-300 bg-gray-50';
    }
  };

  return (
    <div className={`border-2 rounded-lg overflow-hidden ${getStageColor()}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-white/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xl">{stageInfo?.icon || '?'}</span>
          <span className="font-semibold text-sm">{stageInfo?.name || stage}</span>
        </div>
        <span className={`text-xs transform transition-transform ${expanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 border-t border-white/50 bg-white/30">
          <p className="text-xs text-gray-500 mb-1">{stageInfo?.role}</p>
          <p className="text-sm text-gray-700">{output.reasoning}</p>
        </div>
      )}
    </div>
  );
}

function LessonCard({ lesson }: { lesson: CourtLesson }) {
  const isPositive = lesson.polarity === 'do';

  return (
    <div
      className={`p-3 rounded-lg border ${
        isPositive ? 'border-green-200 bg-green-50' : 'border-orange-200 bg-orange-50'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span>{isPositive ? '✅' : '⚠️'}</span>
        <span className="font-medium text-sm">{lesson.title}</span>
      </div>
      <p className="text-xs text-gray-600">{lesson.content}</p>
    </div>
  );
}

function PromptUpdateCard({
  update,
  index,
  onApprove,
  onReject,
}: {
  update: PromptUpdateProposal;
  index: number;
  onApprove?: () => void;
  onReject?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const getStatusBadge = () => {
    switch (update.status) {
      case 'proposed':
        return <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">Proposed</span>;
      case 'approved':
        return <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">Approved</span>;
      case 'rejected':
        return <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">Rejected</span>;
      case 'applied':
        return <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">Applied</span>;
      default:
        return null;
    }
  };

  return (
    <div className="border border-purple-200 rounded-lg bg-purple-50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-purple-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span>📝</span>
          <span className="font-medium text-sm">Prompt Update for {update.role}</span>
          {getStatusBadge()}
        </div>
        <span className={`text-xs transform transition-transform ${expanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 border-t border-purple-200 bg-white">
          <div className="mb-2">
            <span className="text-xs font-medium text-gray-500">Reason:</span>
            <p className="text-sm text-gray-700">{update.reason}</p>
          </div>
          <div className="mb-3">
            <span className="text-xs font-medium text-gray-500">Proposal:</span>
            <p className="text-sm text-gray-700 bg-gray-50 p-2 rounded mt-1">{update.proposal}</p>
          </div>
          {update.status === 'proposed' && (
            <div className="flex gap-2">
              <button
                onClick={onApprove}
                className="flex-1 px-3 py-1.5 bg-green-500 text-white text-sm rounded hover:bg-green-600 transition-colors"
              >
                Approve
              </button>
              <button
                onClick={onReject}
                className="flex-1 px-3 py-1.5 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition-colors"
              >
                Reject
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function CourtSection({
  agent,
  courtResult,
  isRunning,
  stageStatus,
  onRunCourt,
  onApprovePromptUpdate,
  onRejectPromptUpdate,
}: CourtSectionProps) {
  const agentInfo = AGENTS[agent];

  if (!courtResult && !isRunning) {
    return (
      <div className="mt-4 p-4 border-2 border-dashed border-indigo-200 rounded-lg bg-indigo-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">⚖️</span>
            <div>
              <h5 className="font-semibold text-indigo-800">Retrospective Court</h5>
              <p className="text-xs text-indigo-600">
                Run court agents to evaluate {agentInfo.name} output
              </p>
            </div>
          </div>
          <button
            onClick={onRunCourt}
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-2"
          >
            <span>⚖️</span>
            Start Court
          </button>
        </div>
      </div>
    );
  }

  if (isRunning) {
    const stages = ['prosecutor', 'defense', 'jury', 'judge'] as const;
    const defaultStatus: CourtStageStatus = { prosecutor: 'pending', defense: 'pending', jury: 'pending', judge: 'pending' };
    const currentStatus = stageStatus || defaultStatus;

    return (
      <div className="mt-4 border-2 border-indigo-300 rounded-lg bg-indigo-50 overflow-hidden">
        <div className="px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 text-white">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            <div>
              <h5 className="font-semibold">Court in Session...</h5>
              <p className="text-xs text-white/80">
                Evaluating {agentInfo.name} output
              </p>
            </div>
          </div>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-2 gap-2">
            {stages.map((stage) => {
              const status = currentStatus[stage];
              const stageInfo = COURT_STAGES[stage];
              const getStageColor = () => {
                if (status === 'completed') {
                  switch (stage) {
                    case 'prosecutor': return 'border-red-300 bg-red-50';
                    case 'defense': return 'border-green-300 bg-green-50';
                    case 'jury': return 'border-blue-300 bg-blue-50';
                    case 'judge': return 'border-purple-300 bg-purple-50';
                    default: return 'border-gray-300 bg-gray-50';
                  }
                }
                if (status === 'running') return 'border-yellow-400 bg-yellow-50 animate-pulse';
                return 'border-gray-200 bg-gray-50 opacity-50';
              };

              return (
                <div key={stage} className={`border-2 rounded-lg p-3 ${getStageColor()}`}>
                  <div className="flex items-center gap-2">
                    {status === 'running' && (
                      <div className="w-4 h-4 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin"></div>
                    )}
                    {status === 'completed' && <span className="text-green-500">✓</span>}
                    {status === 'pending' && <span className="text-gray-400">○</span>}
                    <span className="text-lg">{stageInfo?.icon || '?'}</span>
                    <span className="font-medium text-sm">{stageInfo?.name || stage}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {status === 'running' && 'Analyzing...'}
                    {status === 'completed' && 'Complete'}
                    {status === 'pending' && 'Waiting...'}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4 border-2 border-indigo-300 rounded-lg bg-indigo-50 overflow-hidden">
      {/* Court Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 text-white">
        <div className="flex items-center gap-2">
          <span className="text-xl">⚖️</span>
          <div>
            <h5 className="font-semibold">Retrospective Court Result</h5>
            <p className="text-xs text-white/80">
              Case ID: {courtResult.case_id.slice(0, 8)}...
            </p>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Court Stages */}
        <div>
          <h6 className="text-sm font-semibold text-gray-700 mb-2">Court Proceedings</h6>
          <div className="grid grid-cols-2 gap-2">
            {(['prosecutor', 'defense', 'jury', 'judge'] as const).map((stage) => (
              <StageCard
                key={stage}
                stage={stage}
                output={courtResult.stages[stage]}
              />
            ))}
          </div>
        </div>

        {/* Lessons */}
        {courtResult.lessons.length > 0 && (
          <div>
            <h6 className="text-sm font-semibold text-gray-700 mb-2">Lessons Learned</h6>
            <div className="space-y-2">
              {courtResult.lessons.map((lesson, idx) => (
                <LessonCard key={idx} lesson={lesson} />
              ))}
            </div>
          </div>
        )}

        {/* Prompt Updates */}
        {courtResult.prompt_updates.length > 0 && (
          <div>
            <h6 className="text-sm font-semibold text-gray-700 mb-2">Prompt Update Proposals</h6>
            <div className="space-y-2">
              {courtResult.prompt_updates.map((update, idx) => (
                <PromptUpdateCard
                  key={idx}
                  update={update}
                  index={idx}
                  onApprove={() => onApprovePromptUpdate?.(idx)}
                  onReject={() => onRejectPromptUpdate?.(idx)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
