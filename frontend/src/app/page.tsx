'use client';

import { useState, useCallback } from 'react';
import {
  GitHubIssue,
  IssuePipelineState,
  AgentType,
  AgentResult,
  AGENTS,
  HumanFeedback,
} from '@/types';
import { AgentPipeline } from '@/components/AgentPipeline';

const BACKEND_API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
const agentOrder: AgentType[] = ['issue_analysis', 'assignment', 'response', 'docs_gap', 'promotion'];

function createInitialAgentState(): Record<AgentType, AgentResult> {
  return agentOrder.reduce((acc, agent) => {
    acc[agent] = { agent, status: 'pending' };
    return acc;
  }, {} as Record<AgentType, AgentResult>);
}

export default function Home() {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [labels, setLabels] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdIssue, setCreatedIssue] = useState<GitHubIssue | null>(null);
  const [pipeline, setPipeline] = useState<IssuePipelineState | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [currentAgentIndex, setCurrentAgentIndex] = useState(-1);
  const [error, setError] = useState<string | null>(null);

  // Run a single agent
  const runAgent = useCallback(async (issue: GitHubIssue, agent: AgentType): Promise<AgentResult> => {
    try {
      const response = await fetch('/api/agents/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue, agent }),
      });
      return await response.json();
    } catch (error) {
      return {
        agent,
        status: 'error',
        error: 'Failed to run agent',
      };
    }
  }, []);

  // Start the pipeline for an issue
  const startPipeline = useCallback(async (issue: GitHubIssue) => {
    setIsRunning(true);
    setCurrentAgentIndex(0);

    const initialPipeline: IssuePipelineState = {
      issue,
      agents: createInitialAgentState(),
      overallProgress: 0,
      status: 'running',
      feedbacks: [],
      startTime: new Date().toISOString(),
    };
    setPipeline(initialPipeline);

    let currentPipeline = initialPipeline;

    for (let i = 0; i < agentOrder.length; i++) {
      const agent = agentOrder[i];
      setCurrentAgentIndex(i);

      currentPipeline = {
        ...currentPipeline,
        agents: {
          ...currentPipeline.agents,
          [agent]: { agent, status: 'running' },
        },
        overallProgress: (i / agentOrder.length) * 100,
      };
      setPipeline({ ...currentPipeline });

      const result = await runAgent(issue, agent);

      currentPipeline = {
        ...currentPipeline,
        agents: {
          ...currentPipeline.agents,
          [agent]: result,
        },
        overallProgress: ((i + 1) / agentOrder.length) * 100,
      };
      setPipeline({ ...currentPipeline });
    }

    currentPipeline = {
      ...currentPipeline,
      status: 'awaiting_feedback',
      endTime: new Date().toISOString(),
    };
    setPipeline({ ...currentPipeline });
    setIsRunning(false);
    setCurrentAgentIndex(-1);
  }, [runAgent]);

  // Create issue and start pipeline
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // Create issue via FastAPI backend
      const response = await fetch(`${BACKEND_API_URL}/api/github/issues`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          body: body.trim(),
          labels: labels.split(',').map(l => l.trim()).filter(Boolean),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create issue');
      }

      const issueData = await response.json();

      const issue: GitHubIssue = {
        number: issueData.number,
        title: issueData.title,
        body: issueData.body || '',
        labels: issueData.labels || [],
        html_url: issueData.html_url,
        user: issueData.user,
        created_at: new Date().toISOString(),
        state: 'open',
      };

      setCreatedIssue(issue);

      // Start agent pipeline
      await startPipeline(issue);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create issue');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Reset form
  const handleReset = () => {
    setTitle('');
    setBody('');
    setLabels('');
    setCreatedIssue(null);
    setPipeline(null);
    setError(null);
  };

  // Handle feedback submission
  const handleFeedbackSubmit = (agent: AgentType, approved: boolean, comment: string) => {
    if (!pipeline) return;

    const feedback: HumanFeedback = {
      agent,
      approved,
      comment,
      reviewer: 'Human Reviewer',
      timestamp: new Date().toISOString(),
    };

    const updatedFeedbacks = [...pipeline.feedbacks, feedback];
    const allReviewed = updatedFeedbacks.length === agentOrder.length;

    setPipeline({
      ...pipeline,
      feedbacks: updatedFeedbacks,
      status: allReviewed ? 'completed' : 'awaiting_feedback',
    });
  };

  return (
    <main className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                <span>🤖</span> DevRel Agent Pipeline
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                Phase 2 - AI Agent Orchestration
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-sm text-gray-500">Target Repository</div>
                <a
                  href="https://github.com/GSN-OMG/Prism"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  GSN-OMG/Prism
                </a>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Agent Overview Bar */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Agent Pipeline Overview</h2>
            {isRunning && (
              <div className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 bg-white rounded-full animate-pulse" />
                <span className="text-sm">Running {AGENTS[agentOrder[currentAgentIndex]]?.name}...</span>
              </div>
            )}
          </div>
          <div className="grid grid-cols-5 gap-4">
            {agentOrder.map((agent, idx) => {
              const agentInfo = AGENTS[agent];
              const isActive = currentAgentIndex === idx;
              const isCompleted = pipeline?.agents[agent]?.status === 'completed';

              return (
                <div
                  key={agent}
                  className={`p-3 rounded-lg transition-all ${
                    isActive
                      ? 'bg-white/30 ring-2 ring-white'
                      : isCompleted
                      ? 'bg-white/20'
                      : 'bg-white/10'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xl">{agentInfo.icon}</span>
                    <span className="font-medium text-sm">{agentInfo.name}</span>
                  </div>
                  <div className="text-xs text-white/70">
                    {isActive ? (
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                        Running
                      </span>
                    ) : isCompleted ? (
                      '✓ Completed'
                    ) : (
                      'Pending'
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Issue Creation Form */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-gray-900">
                    {createdIssue ? '✅ Issue Created' : '📝 Create New Issue'}
                  </h3>
                  {createdIssue && (
                    <button
                      onClick={handleReset}
                      className="text-sm text-indigo-600 hover:text-indigo-800"
                    >
                      New Issue
                    </button>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {createdIssue
                    ? `Issue #${createdIssue.number} created successfully`
                    : 'Fill out the form to create a GitHub issue'
                  }
                </p>
              </div>

              {createdIssue ? (
                <div className="p-6">
                  <div className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">📋</span>
                      <span className="font-medium text-gray-900">
                        #{createdIssue.number}
                      </span>
                      {pipeline?.status === 'completed' && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                          ✓ Done
                        </span>
                      )}
                      {isRunning && (
                        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded animate-pulse">
                          Running
                        </span>
                      )}
                    </div>
                    <h4 className="font-medium text-gray-800 mb-2">
                      {createdIssue.title}
                    </h4>
                    {createdIssue.body && (
                      <p className="text-sm text-gray-600 whitespace-pre-wrap">
                        {createdIssue.body.slice(0, 200)}
                        {createdIssue.body.length > 200 && '...'}
                      </p>
                    )}
                  </div>
                  <a
                    href={createdIssue.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800"
                  >
                    View on GitHub →
                  </a>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                  {error && (
                    <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                      {error}
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Title <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="Bug: Something is not working"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      required
                      disabled={isSubmitting}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Description
                    </label>
                    <textarea
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                      placeholder="Describe the issue in detail..."
                      rows={6}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
                      disabled={isSubmitting}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Labels
                    </label>
                    <input
                      type="text"
                      value={labels}
                      onChange={(e) => setLabels(e.target.value)}
                      placeholder="bug, help wanted (comma separated)"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      disabled={isSubmitting}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Separate multiple labels with commas
                    </p>
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting || !title.trim()}
                    className="w-full py-3 px-4 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                  >
                    {isSubmitting ? (
                      <>
                        <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                        Creating Issue...
                      </>
                    ) : (
                      <>
                        🚀 Create Issue & Run Agents
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          </div>

          {/* Pipeline Result Panel */}
          <div className="lg:col-span-2">
            {pipeline ? (
              <AgentPipeline
                pipeline={pipeline}
                onFeedbackSubmit={handleFeedbackSubmit}
              />
            ) : (
              <div className="bg-white rounded-xl shadow-lg p-12 text-center">
                <div className="text-6xl mb-4">👈</div>
                <h3 className="text-xl font-semibold text-gray-800 mb-2">
                  Create an Issue to Start
                </h3>
                <p className="text-gray-500 max-w-md mx-auto">
                  Fill out the form on the left to create a GitHub issue.
                  Once created, all 5 agents will analyze it.
                </p>
                <div className="mt-8 grid grid-cols-5 gap-2">
                  {agentOrder.map((agent) => (
                    <div
                      key={agent}
                      className="p-3 bg-gray-50 rounded-lg text-center"
                    >
                      <span className="text-2xl block mb-1">{AGENTS[agent].icon}</span>
                      <span className="text-xs text-gray-600">{AGENTS[agent].name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-800 text-white py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-gray-400 text-sm">
            DevRel Agent Pipeline • Phase 2 Hackathon Demo
          </p>
          <p className="text-gray-500 text-xs mt-2">
            LLM-Powered Responses • Human-in-the-Loop Feedback
          </p>
        </div>
      </footer>
    </main>
  );
}
