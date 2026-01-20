'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  GitHubIssue,
  IssuePipelineState,
  AgentType,
  AgentResult,
  AGENTS,
  HumanFeedback,
} from '@/types';
import { AgentPipeline } from '@/components/AgentPipeline';

const agentOrder: AgentType[] = ['issue_analysis', 'assignment', 'response', 'docs_gap', 'promotion'];

function createInitialAgentState(): Record<AgentType, AgentResult> {
  return agentOrder.reduce((acc, agent) => {
    acc[agent] = { agent, status: 'pending' };
    return acc;
  }, {} as Record<AgentType, AgentResult>);
}

export default function Home() {
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<GitHubIssue | null>(null);
  const [pipeline, setPipeline] = useState<IssuePipelineState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [currentAgentIndex, setCurrentAgentIndex] = useState(-1);

  // Fetch issues on mount
  useEffect(() => {
    fetchIssues();
  }, []);

  const fetchIssues = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/issues');
      const data = await response.json();
      setIssues(data);
    } catch (error) {
      console.error('Failed to fetch issues:', error);
    } finally {
      setIsLoading(false);
    }
  };

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
    setSelectedIssue(issue);
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

    // Run agents sequentially
    let currentPipeline = initialPipeline;

    for (let i = 0; i < agentOrder.length; i++) {
      const agent = agentOrder[i];
      setCurrentAgentIndex(i);

      // Update agent to running
      currentPipeline = {
        ...currentPipeline,
        agents: {
          ...currentPipeline.agents,
          [agent]: { agent, status: 'running' },
        },
        overallProgress: (i / agentOrder.length) * 100,
      };
      setPipeline({ ...currentPipeline });

      // Run the agent
      const result = await runAgent(issue, agent);

      // Update agent result
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

    // All agents completed
    currentPipeline = {
      ...currentPipeline,
      status: 'awaiting_feedback',
      endTime: new Date().toISOString(),
    };
    setPipeline({ ...currentPipeline });
    setIsRunning(false);
    setCurrentAgentIndex(-1);
  }, [runAgent]);

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
                Phase 2 - Transparent AI Agent Orchestration with Human-in-the-Loop
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
          {/* Issue Selection Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-gray-900">GitHub Issues</h3>
                  <button
                    onClick={fetchIssues}
                    disabled={isLoading}
                    className="text-sm text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                  >
                    Refresh
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Select an issue to run the agent pipeline
                </p>
              </div>

              <div className="divide-y max-h-[600px] overflow-y-auto">
                {isLoading ? (
                  <div className="p-8 text-center text-gray-500">
                    <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full mx-auto mb-2" />
                    Loading issues...
                  </div>
                ) : issues.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    No open issues found
                  </div>
                ) : (
                  issues.map((issue) => {
                    const isSelected = selectedIssue?.number === issue.number;
                    return (
                      <div
                        key={issue.number}
                        className={`p-4 cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-indigo-50 border-l-4 border-indigo-500'
                            : 'hover:bg-gray-50'
                        }`}
                        onClick={() => !isRunning && startPipeline(issue)}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">📋</span>
                            <span className="font-medium text-gray-900">
                              #{issue.number}
                            </span>
                          </div>
                          {isSelected && !isRunning && pipeline?.status === 'completed' && (
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                              ✓ Done
                            </span>
                          )}
                          {isSelected && isRunning && (
                            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded animate-pulse">
                              Running
                            </span>
                          )}
                        </div>
                        <h4 className="font-medium text-gray-800 text-sm line-clamp-2 mb-2">
                          {issue.title}
                        </h4>
                        <div className="flex flex-wrap gap-1">
                          {issue.labels.slice(0, 3).map((label, idx) => (
                            <span
                              key={idx}
                              className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded"
                            >
                              {label}
                            </span>
                          ))}
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                          <img
                            src={issue.user.avatar_url}
                            alt={issue.user.login}
                            className="w-4 h-4 rounded-full"
                          />
                          <span>@{issue.user.login}</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
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
                  Select an Issue to Start
                </h3>
                <p className="text-gray-500 max-w-md mx-auto">
                  Click on an issue from the left panel to trigger the agent pipeline.
                  All 5 agents will analyze the issue in sequence.
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
            Issue triggers 5 agents in parallel • Human-in-the-loop feedback • Transparent decision traces
          </p>
        </div>
      </footer>
    </main>
  );
}
