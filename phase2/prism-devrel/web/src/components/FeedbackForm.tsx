'use client';

import { useState } from 'react';
import { AgentResult, AgentType, AGENTS } from '@/types';

interface FeedbackFormProps {
  agent: AgentType;
  result: AgentResult;
  onSubmit: (approved: boolean, comment: string) => void;
  onClose: () => void;
}

export function FeedbackForm({ agent, result, onSubmit, onClose }: FeedbackFormProps) {
  const [approved, setApproved] = useState<boolean | null>(null);
  const [comment, setComment] = useState('');

  const agentInfo = AGENTS[agent];

  const handleSubmit = () => {
    if (approved === null) return;
    onSubmit(approved, comment);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-yellow-500 to-orange-500 px-6 py-4 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">👤</span>
              <div>
                <h3 className="text-xl font-bold">Human Review</h3>
                <p className="text-white/80 text-sm">
                  {agentInfo.icon} {agentInfo.name}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center hover:bg-white/30 transition-colors"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Agent Output Summary */}
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-semibold text-gray-700 mb-2">Agent Output Summary</h4>
            {result.output ? (
              <pre className="text-xs bg-gray-100 p-3 rounded overflow-auto max-h-40">
                {JSON.stringify(result.output, null, 2)}
              </pre>
            ) : (
              <p className="text-sm text-gray-500">No output available</p>
            )}
          </div>

          {/* Approval Buttons */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Do you approve this agent's output?
            </label>
            <div className="flex gap-3">
              <button
                onClick={() => setApproved(true)}
                className={`flex-1 py-3 px-4 rounded-lg border-2 transition-all ${
                  approved === true
                    ? 'border-green-500 bg-green-50 text-green-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-green-300'
                }`}
              >
                <span className="text-2xl block mb-1">✓</span>
                <span className="font-semibold">Approve</span>
              </button>
              <button
                onClick={() => setApproved(false)}
                className={`flex-1 py-3 px-4 rounded-lg border-2 transition-all ${
                  approved === false
                    ? 'border-red-500 bg-red-50 text-red-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-red-300'
                }`}
              >
                <span className="text-2xl block mb-1">✕</span>
                <span className="font-semibold">Reject</span>
              </button>
            </div>
          </div>

          {/* Comment */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Comments (Optional)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Provide feedback or suggestions..."
              className="w-full h-24 p-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
            />
          </div>

          {/* Submit */}
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 py-3 px-4 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={approved === null}
              className={`flex-1 py-3 px-4 rounded-lg font-semibold transition-colors ${
                approved === null
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-yellow-500 text-white hover:bg-yellow-600'
              }`}
            >
              Submit Feedback
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
