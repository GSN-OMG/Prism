'use client';

import { useState } from 'react';
import { IssuePipelineState, AgentType, AGENTS } from '@/types';
import { AgentCard } from './AgentCard';
import { AgentOutputModal } from './AgentOutputModal';
import { FeedbackForm } from './FeedbackForm';

interface AgentPipelineProps {
  pipeline: IssuePipelineState;
  onFeedbackSubmit: (agent: AgentType, approved: boolean, comment: string) => void;
}

const agentOrder: AgentType[] = ['issue_analysis', 'assignment', 'response', 'docs_gap', 'promotion'];

export function AgentPipeline({ pipeline, onFeedbackSubmit }: AgentPipelineProps) {
  const [selectedAgent, setSelectedAgent] = useState<AgentType | null>(null);
  const [feedbackAgent, setFeedbackAgent] = useState<AgentType | null>(null);

  const completedCount = agentOrder.filter(
    (a) => pipeline.agents[a]?.status === 'completed'
  ).length;

  const overallProgress = (completedCount / agentOrder.length) * 100;

  const getStatusColor = () => {
    if (pipeline.status === 'completed') return 'from-green-500 to-green-600';
    if (pipeline.status === 'running') return 'from-blue-500 to-blue-600';
    if (pipeline.status === 'awaiting_feedback') return 'from-yellow-500 to-yellow-600';
    return 'from-gray-400 to-gray-500';
  };

  const getStatusLabel = () => {
    switch (pipeline.status) {
      case 'idle':
        return 'Ready to Start';
      case 'running':
        return 'Processing...';
      case 'awaiting_feedback':
        return 'Awaiting Human Review';
      case 'completed':
        return 'Completed';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Issue Header */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-4 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">📋</span>
            <div>
              <h3 className="text-xl font-bold">Issue #{pipeline.issue.number}</h3>
              <p className="text-white/80 text-sm truncate max-w-md">{pipeline.issue.title}</p>
            </div>
          </div>
          <a
            href={pipeline.issue.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-white/20 rounded-lg text-sm hover:bg-white/30 transition-colors"
          >
            View on GitHub
          </a>
        </div>
      </div>

      {/* Overall Progress */}
      <div className="px-6 py-4 border-b bg-gray-50">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-semibold text-gray-700">Project Progress</h4>
          <span className={`text-sm font-medium px-3 py-1 rounded-full bg-gradient-to-r ${getStatusColor()} text-white`}>
            {getStatusLabel()}
          </span>
        </div>
        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full bg-gradient-to-r ${getStatusColor()} transition-all duration-500`}
            style={{ width: `${overallProgress}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-2">
          {completedCount} of {agentOrder.length} agents completed
        </p>
      </div>

      {/* Agent Cards Grid */}
      <div className="px-6 py-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {agentOrder.map((agentType) => (
            <AgentCard
              key={agentType}
              agent={agentType}
              result={pipeline.agents[agentType] || { agent: agentType, status: 'pending' }}
              onViewDetails={
                pipeline.agents[agentType]?.status === 'completed'
                  ? () => setSelectedAgent(agentType)
                  : undefined
              }
            />
          ))}
        </div>
      </div>

      {/* Human-in-the-Loop Section */}
      {pipeline.status === 'awaiting_feedback' && (
        <div className="px-6 py-4 border-t bg-yellow-50">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">👤</span>
            <h4 className="font-semibold text-yellow-800">Human Review Required</h4>
          </div>
          <p className="text-sm text-yellow-700 mb-4">
            All agents have completed. Please review the results and provide feedback.
          </p>
          <div className="flex flex-wrap gap-2">
            {agentOrder.map((agentType) => {
              const hasFeedback = pipeline.feedbacks.some((f) => f.agent === agentType);
              return (
                <button
                  key={agentType}
                  onClick={() => setFeedbackAgent(agentType)}
                  disabled={hasFeedback}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    hasFeedback
                      ? 'bg-green-100 text-green-700 cursor-not-allowed'
                      : 'bg-white border border-yellow-300 text-yellow-700 hover:bg-yellow-100'
                  }`}
                >
                  {AGENTS[agentType].icon} {AGENTS[agentType].name}
                  {hasFeedback && ' ✓'}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Feedback Summary */}
      {pipeline.feedbacks.length > 0 && (
        <div className="px-6 py-4 border-t bg-gray-50">
          <h4 className="font-semibold text-gray-700 mb-3">Feedback Summary</h4>
          <div className="space-y-2">
            {pipeline.feedbacks.map((feedback, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg border ${
                  feedback.approved
                    ? 'bg-green-50 border-green-200'
                    : 'bg-red-50 border-red-200'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">
                    {AGENTS[feedback.agent].icon} {AGENTS[feedback.agent].name}
                  </span>
                  <span
                    className={`text-xs font-semibold px-2 py-1 rounded ${
                      feedback.approved
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {feedback.approved ? 'Approved' : 'Rejected'}
                  </span>
                </div>
                {feedback.comment && (
                  <p className="text-xs text-gray-600">{feedback.comment}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Output Modal */}
      {selectedAgent && (
        <AgentOutputModal
          agent={selectedAgent}
          result={pipeline.agents[selectedAgent]}
          onClose={() => setSelectedAgent(null)}
        />
      )}

      {/* Feedback Modal */}
      {feedbackAgent && (
        <FeedbackForm
          agent={feedbackAgent}
          result={pipeline.agents[feedbackAgent]}
          onSubmit={(approved, comment) => {
            onFeedbackSubmit(feedbackAgent, approved, comment);
            setFeedbackAgent(null);
          }}
          onClose={() => setFeedbackAgent(null)}
        />
      )}
    </div>
  );
}
