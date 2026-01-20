'use client';

import { AgentResult, AgentType, AGENTS, AgentStatus } from '@/types';

interface AgentCardProps {
  agent: AgentType;
  result: AgentResult;
  onViewDetails?: () => void;
}

const statusStyles: Record<AgentStatus, { bg: string; text: string; border: string; progressColor: string }> = {
  pending: {
    bg: 'bg-gray-50',
    text: 'text-gray-500',
    border: 'border-gray-200',
    progressColor: 'bg-gray-300',
  },
  running: {
    bg: 'bg-blue-50',
    text: 'text-blue-600',
    border: 'border-blue-300',
    progressColor: 'bg-blue-500',
  },
  completed: {
    bg: 'bg-green-50',
    text: 'text-green-600',
    border: 'border-green-300',
    progressColor: 'bg-green-500',
  },
  error: {
    bg: 'bg-red-50',
    text: 'text-red-600',
    border: 'border-red-300',
    progressColor: 'bg-red-500',
  },
};

const statusLabels: Record<AgentStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  error: 'Error',
};

export function AgentCard({ agent, result, onViewDetails }: AgentCardProps) {
  const agentInfo = AGENTS[agent];
  const style = statusStyles[result.status];

  const getProgressWidth = (): string => {
    switch (result.status) {
      case 'pending':
        return '0%';
      case 'running':
        return '50%';
      case 'completed':
        return '100%';
      case 'error':
        return '100%';
      default:
        return '0%';
    }
  };

  return (
    <div
      className={`rounded-lg border-2 ${style.border} ${style.bg} p-4 transition-all duration-300 hover:shadow-md`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{agentInfo.icon}</span>
          <span className="font-semibold text-gray-900">{agentInfo.name}</span>
        </div>
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${style.bg} ${style.text}`}>
          {result.status === 'running' && (
            <span className="inline-block w-2 h-2 bg-blue-500 rounded-full mr-1 animate-pulse" />
          )}
          Status: {statusLabels[result.status]}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-3">
        <div
          className={`h-full ${style.progressColor} transition-all duration-500 ${
            result.status === 'running' ? 'animate-pulse' : ''
          }`}
          style={{ width: getProgressWidth() }}
        />
      </div>

      {/* Description */}
      <p className="text-xs text-gray-500 mb-2">{agentInfo.description}</p>

      {/* Duration */}
      {result.durationMs && (
        <p className="text-xs text-gray-400">
          Duration: {(result.durationMs / 1000).toFixed(2)}s
        </p>
      )}

      {/* Error Message */}
      {result.status === 'error' && result.error && (
        <div className="mt-2 p-2 bg-red-100 rounded text-xs text-red-700">
          {result.error}
        </div>
      )}

      {/* View Details Button */}
      {result.status === 'completed' && onViewDetails && (
        <button
          onClick={onViewDetails}
          className="mt-3 w-full text-xs text-center py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          View Details
        </button>
      )}
    </div>
  );
}
