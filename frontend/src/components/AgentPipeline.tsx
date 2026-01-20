'use client';

import { useState } from 'react';
import {
  IssuePipelineState,
  AgentType,
  AGENTS,
  AgentResult,
  IssueAnalysisOutput,
  AssignmentOutput,
  ResponseOutput,
  DocGapOutput,
  PromotionOutput,
  DecisionStep
} from '@/types';
import { FeedbackForm } from './FeedbackForm';

interface AgentPipelineProps {
  pipeline: IssuePipelineState;
  onFeedbackSubmit: (agent: AgentType, approved: boolean, comment: string) => void;
}

const agentOrder: AgentType[] = ['issue_analysis', 'assignment', 'response', 'docs_gap', 'promotion'];

// Format output based on agent type
function formatAgentOutput(agent: AgentType, output: AgentResult['output']): React.ReactNode {
  if (!output) return <span className="text-gray-400">No output available</span>;

  switch (agent) {
    case 'issue_analysis': {
      const o = output as IssueAnalysisOutput;
      return (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="font-medium text-gray-600">Type:</span> <span className="capitalize">{o.issue_type}</span></div>
            <div><span className="font-medium text-gray-600">Priority:</span> <span className={`capitalize ${o.priority === 'critical' ? 'text-red-600 font-bold' : o.priority === 'high' ? 'text-orange-600' : 'text-gray-700'}`}>{o.priority}</span></div>
            <div><span className="font-medium text-gray-600">Action:</span> <span className="capitalize">{o.suggested_action?.replace('_', ' ')}</span></div>
            <div><span className="font-medium text-gray-600">More Info Needed:</span> {o.needs_more_info ? '✅ Yes' : '❌ No'}</div>
          </div>
          <div><span className="font-medium text-gray-600">Summary:</span> <p className="text-gray-800 mt-1">{o.summary}</p></div>
          {o.required_skills?.length > 0 && (
            <div><span className="font-medium text-gray-600">Skills:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {o.required_skills.map((s, i) => <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">{s}</span>)}
              </div>
            </div>
          )}
          {o.keywords?.length > 0 && (
            <div><span className="font-medium text-gray-600">Keywords:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {o.keywords.map((k, i) => <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">{k}</span>)}
              </div>
            </div>
          )}
        </div>
      );
    }
    case 'assignment': {
      const o = output as AssignmentOutput;
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-600">Recommended:</span>
            <span className="px-3 py-1 bg-green-100 text-green-800 font-semibold rounded-full">@{o.recommended_assignee}</span>
            <span className="text-sm text-gray-500">({Math.round(o.confidence * 100)}% confidence)</span>
          </div>
          {o.reasons?.length > 0 && (
            <div>
              <span className="font-medium text-gray-600">Reasons:</span>
              <ul className="mt-1 space-y-1">
                {o.reasons.map((r, i) => (
                  <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                    <span className="text-green-500">•</span>
                    <span><strong>{r.factor}:</strong> {r.explanation} (score: {r.score})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {o.context_for_assignee && (
            <div><span className="font-medium text-gray-600">Context:</span> <p className="text-gray-700 mt-1 text-sm">{o.context_for_assignee}</p></div>
          )}
          {o.alternative_assignees?.length > 0 && (
            <div className="text-sm"><span className="font-medium text-gray-600">Alternatives:</span> {o.alternative_assignees.map(a => `@${a}`).join(', ')}</div>
          )}
        </div>
      );
    }
    case 'response': {
      const o = output as ResponseOutput;
      return (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="font-medium text-gray-600">Strategy:</span> <span className="capitalize">{o.strategy?.replace('_', ' ')}</span></div>
            <div><span className="font-medium text-gray-600">Confidence:</span> {Math.round(o.confidence * 100)}%</div>
            <div><span className="font-medium text-gray-600">Follow-up:</span> {o.follow_up_needed ? '✅ Yes' : '❌ No'}</div>
          </div>
          <div>
            <span className="font-medium text-gray-600">Draft Response:</span>
            <div className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-800 whitespace-pre-wrap">
              {o.response_text}
            </div>
          </div>
          {o.references?.length > 0 && (
            <div><span className="font-medium text-gray-600">References:</span>
              <ul className="mt-1 space-y-1">
                {o.references.map((r, i) => (
                  <li key={i} className="text-sm text-blue-600 hover:underline">{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );
    }
    case 'docs_gap': {
      const o = output as DocGapOutput;
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-600">Documentation Gap:</span>
            <span className={`px-2 py-0.5 rounded-full text-sm font-medium ${o.has_gap ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}`}>
              {o.has_gap ? '⚠️ Gap Found' : '✅ No Gap'}
            </span>
          </div>
          {o.has_gap && (
            <>
              <div><span className="font-medium text-gray-600">Topic:</span> {o.gap_topic}</div>
              <div><span className="font-medium text-gray-600">Priority:</span> <span className="capitalize">{o.priority}</span></div>
              <div><span className="font-medium text-gray-600">Suggested Path:</span> <code className="text-sm bg-gray-100 px-1 rounded">{o.suggested_doc_path}</code></div>
              {o.suggested_outline?.length > 0 && (
                <div>
                  <span className="font-medium text-gray-600">Suggested Outline:</span>
                  <ul className="mt-1 space-y-1 list-decimal list-inside text-sm text-gray-700">
                    {o.suggested_outline.map((item, i) => <li key={i}>{item}</li>)}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      );
    }
    case 'promotion': {
      const o = output as PromotionOutput;
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-600">Promotion Candidate:</span>
            <span className={`px-2 py-0.5 rounded-full text-sm font-medium ${o.is_candidate ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-600'}`}>
              {o.is_candidate ? '🚀 Recommended' : 'Not Yet'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="font-medium text-gray-600">Current Stage:</span> {o.current_stage}</div>
            <div><span className="font-medium text-gray-600">Suggested Stage:</span> <span className="text-purple-600 font-medium">{o.suggested_stage}</span></div>
            <div><span className="font-medium text-gray-600">Confidence:</span> {Math.round(o.confidence * 100)}%</div>
          </div>
          {o.evidence?.length > 0 && (
            <div>
              <span className="font-medium text-gray-600">Evidence:</span>
              <ul className="mt-1 space-y-1">
                {o.evidence.map((e, i) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <span className={e.status === 'met' || e.status === 'exceeds' ? 'text-green-500' : 'text-yellow-500'}>
                      {e.status === 'met' || e.status === 'exceeds' ? '✓' : '○'}
                    </span>
                    <span><strong>{e.criterion}:</strong> {e.detail} ({e.status})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {o.recommendation && (
            <div><span className="font-medium text-gray-600">Recommendation:</span> <p className="text-gray-700 mt-1 text-sm">{o.recommendation}</p></div>
          )}
        </div>
      );
    }
    default:
      return <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto">{JSON.stringify(output, null, 2)}</pre>;
  }
}

// Format decision trace
function DecisionTraceView({ steps }: { steps: DecisionStep[] }) {
  if (!steps || steps.length === 0) {
    return <p className="text-gray-400 text-sm">No decision trace available</p>;
  }

  return (
    <div className="space-y-3">
      {steps.map((step, idx) => (
        <div key={idx} className="border-l-2 border-indigo-300 pl-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs flex items-center justify-center font-bold">
              {step.step_number}
            </span>
            <span className="font-medium text-gray-800">{step.step_name}</span>
            <span className="text-xs text-gray-400">{step.timestamp}</span>
          </div>
          <div className="ml-8 text-sm text-gray-600">
            <p className="italic">{step.reasoning}</p>
            {step.input && Object.keys(step.input).length > 0 && (
              <details className="mt-1">
                <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">Input</summary>
                <pre className="text-xs bg-gray-50 p-2 rounded mt-1 overflow-auto max-h-32">{JSON.stringify(step.input, null, 2)}</pre>
              </details>
            )}
            {step.output && Object.keys(step.output).length > 0 && (
              <details className="mt-1">
                <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">Output</summary>
                <pre className="text-xs bg-gray-50 p-2 rounded mt-1 overflow-auto max-h-32">{JSON.stringify(step.output, null, 2)}</pre>
              </details>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// Single agent section
function AgentSection({ agentType, result, isLast }: { agentType: AgentType; result: AgentResult; isLast: boolean }) {
  const [expanded, setExpanded] = useState(result.status === 'completed' || result.status === 'running');
  const agentInfo = AGENTS[agentType];

  const getStatusBadge = () => {
    switch (result.status) {
      case 'pending':
        return <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded-full">Pending</span>;
      case 'running':
        return <span className="px-2 py-0.5 bg-blue-100 text-blue-600 text-xs rounded-full animate-pulse">Running...</span>;
      case 'completed':
        return <span className="px-2 py-0.5 bg-green-100 text-green-600 text-xs rounded-full">Completed</span>;
      case 'error':
        return <span className="px-2 py-0.5 bg-red-100 text-red-600 text-xs rounded-full">Error</span>;
      default:
        return null;
    }
  };

  const getBorderColor = () => {
    switch (result.status) {
      case 'running':
        return 'border-blue-400';
      case 'completed':
        return 'border-green-400';
      case 'error':
        return 'border-red-400';
      default:
        return 'border-gray-200';
    }
  };

  return (
    <div className="relative">
      {/* Vertical connector line */}
      {!isLast && (
        <div className="absolute left-6 top-14 w-0.5 h-full bg-gray-200 -z-10" />
      )}

      <div className={`border-2 ${getBorderColor()} rounded-lg bg-white overflow-hidden transition-all duration-300`}>
        {/* Header - always visible */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">{agentInfo.icon}</span>
            <div className="text-left">
              <h4 className="font-semibold text-gray-900">{agentInfo.name}</h4>
              <p className="text-xs text-gray-500">{agentInfo.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {result.durationMs && (
              <span className="text-xs text-gray-400">{(result.durationMs / 1000).toFixed(2)}s</span>
            )}
            {getStatusBadge()}
            <span className={`transform transition-transform ${expanded ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </div>
        </button>

        {/* Expanded content */}
        {expanded && (
          <div className="border-t border-gray-100">
            {/* Error display */}
            {result.status === 'error' && result.error && (
              <div className="px-4 py-3 bg-red-50 border-b border-red-100">
                <p className="text-sm text-red-700">{result.error}</p>
              </div>
            )}

            {/* Output section */}
            {result.status === 'completed' && result.output && (
              <div className="px-4 py-4">
                <h5 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <span>📤</span> Output
                </h5>
                {formatAgentOutput(agentType, result.output)}
              </div>
            )}

            {/* Decision Trace section */}
            {result.status === 'completed' && result.decisionTrace && result.decisionTrace.length > 0 && (
              <div className="px-4 py-4 border-t border-gray-100 bg-gray-50">
                <h5 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <span>🧠</span> Decision Trace
                </h5>
                <DecisionTraceView steps={result.decisionTrace} />
              </div>
            )}

            {/* Running indicator */}
            {result.status === 'running' && (
              <div className="px-4 py-8 flex flex-col items-center justify-center">
                <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-3"></div>
                <p className="text-sm text-gray-500">Processing...</p>
              </div>
            )}

            {/* Pending indicator */}
            {result.status === 'pending' && (
              <div className="px-4 py-4 text-center text-sm text-gray-400">
                Waiting for previous agents to complete...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AgentPipeline({ pipeline, onFeedbackSubmit }: AgentPipelineProps) {
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
          <h4 className="font-semibold text-gray-700">Pipeline Progress</h4>
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

      {/* Agent Sections - Vertical List */}
      <div className="px-6 py-4 space-y-4">
        {agentOrder.map((agentType, index) => (
          <AgentSection
            key={agentType}
            agentType={agentType}
            result={pipeline.agents[agentType] || { agent: agentType, status: 'pending' }}
            isLast={index === agentOrder.length - 1}
          />
        ))}
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
