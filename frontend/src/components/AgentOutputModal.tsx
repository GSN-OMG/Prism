'use client';

import { AgentResult, AgentType, AGENTS, IssueAnalysisOutput, AssignmentOutput, ResponseOutput, DocGapOutput, PromotionOutput } from '@/types';

interface AgentOutputModalProps {
  agent: AgentType;
  result: AgentResult;
  onClose: () => void;
}

export function AgentOutputModal({ agent, result, onClose }: AgentOutputModalProps) {
  const agentInfo = AGENTS[agent];

  const renderOutput = () => {
    if (!result.output) {
      return <p className="text-gray-500">No output available</p>;
    }

    switch (agent) {
      case 'issue_analysis':
        return <IssueAnalysisView output={result.output as IssueAnalysisOutput} />;
      case 'assignment':
        return <AssignmentView output={result.output as AssignmentOutput} />;
      case 'response':
        return <ResponseView output={result.output as ResponseOutput} />;
      case 'docs_gap':
        return <DocGapView output={result.output as DocGapOutput} />;
      case 'promotion':
        return <PromotionView output={result.output as PromotionOutput} />;
      default:
        return <pre className="text-xs bg-gray-100 p-4 rounded overflow-auto">{JSON.stringify(result.output, null, 2)}</pre>;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-500 to-purple-500 px-6 py-4 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">{agentInfo.icon}</span>
              <div>
                <h3 className="text-xl font-bold">{agentInfo.name} Output</h3>
                <p className="text-white/80 text-sm">{agentInfo.description}</p>
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
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {renderOutput()}
        </div>

        {/* Decision Trace */}
        {result.decisionTrace && result.decisionTrace.length > 0 && (
          <div className="border-t px-6 py-4 bg-gray-50">
            <h4 className="font-semibold text-gray-700 mb-3">Decision Trace</h4>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {result.decisionTrace.map((step, idx) => (
                <div key={idx} className="text-xs p-2 bg-white rounded border">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-indigo-600">Step {step.step_number}</span>
                    <span className="text-gray-700">{step.step_name}</span>
                  </div>
                  <p className="text-gray-600">{step.reasoning}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="border-t px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function IssueAnalysisView({ output }: { output: IssueAnalysisOutput }) {
  const priorityColors: Record<string, string> = {
    critical: 'bg-red-100 text-red-800',
    high: 'bg-orange-100 text-orange-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-green-100 text-green-800',
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Issue Type</label>
          <p className="font-semibold capitalize">{output.issue_type.replace('_', ' ')}</p>
        </div>
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Priority</label>
          <span className={`inline-block px-2 py-1 rounded text-sm font-semibold ${priorityColors[output.priority]}`}>
            {output.priority.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Summary</label>
        <p className="text-sm">{output.summary}</p>
      </div>

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Required Skills</label>
        <div className="flex flex-wrap gap-1 mt-1">
          {output.required_skills.map((skill, idx) => (
            <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
              {skill}
            </span>
          ))}
        </div>
      </div>

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Keywords</label>
        <div className="flex flex-wrap gap-1 mt-1">
          {output.keywords.map((kw, idx) => (
            <span key={idx} className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-xs">
              {kw}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Needs More Info</label>
          <p className="font-semibold">{output.needs_more_info ? 'Yes' : 'No'}</p>
        </div>
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Suggested Action</label>
          <p className="font-semibold capitalize">{output.suggested_action.replace('_', ' ')}</p>
        </div>
      </div>
    </div>
  );
}

function AssignmentView({ output }: { output: AssignmentOutput }) {
  return (
    <div className="space-y-4">
      <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
        <label className="text-xs text-indigo-600">Recommended Assignee</label>
        <p className="text-2xl font-bold text-indigo-800">@{output.recommended_assignee}</p>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-sm text-indigo-600">Confidence:</span>
          <div className="flex-1 h-2 bg-indigo-200 rounded-full">
            <div
              className="h-full bg-indigo-500 rounded-full"
              style={{ width: `${output.confidence * 100}%` }}
            />
          </div>
          <span className="text-sm font-bold text-indigo-800">{(output.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Assignment Reasons</label>
        <div className="space-y-2 mt-2">
          {output.reasons.map((reason, idx) => (
            <div key={idx} className="flex items-center justify-between p-2 bg-white rounded border">
              <div>
                <span className="font-medium text-sm">{reason.factor}</span>
                <p className="text-xs text-gray-500">{reason.explanation}</p>
              </div>
              <span className="text-sm font-bold text-green-600">{(reason.score * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>

      {output.alternative_assignees.length > 0 && (
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Alternative Assignees</label>
          <div className="flex flex-wrap gap-2 mt-1">
            {output.alternative_assignees.map((assignee, idx) => (
              <span key={idx} className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-sm">
                @{assignee}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Context for Assignee</label>
        <pre className="text-xs mt-1 whitespace-pre-wrap">{output.context_for_assignee}</pre>
      </div>
    </div>
  );
}

function ResponseView({ output }: { output: ResponseOutput }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Strategy</label>
          <p className="font-semibold capitalize">{output.strategy.replace('_', ' ')}</p>
        </div>
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Confidence</label>
          <p className="font-semibold">{(output.confidence * 100).toFixed(0)}%</p>
        </div>
      </div>

      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
        <label className="text-xs text-blue-600">Generated Response</label>
        <p className="text-sm mt-2 whitespace-pre-wrap">{output.response_text}</p>
      </div>

      {output.references.length > 0 && (
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">References</label>
          <ul className="list-disc list-inside text-sm mt-1">
            {output.references.map((ref, idx) => (
              <li key={idx} className="text-blue-600">{ref}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Follow-up Needed</label>
        <p className="font-semibold">{output.follow_up_needed ? 'Yes' : 'No'}</p>
      </div>
    </div>
  );
}

function DocGapView({ output }: { output: DocGapOutput }) {
  const priorityColors: Record<string, string> = {
    critical: 'bg-red-100 text-red-800',
    high: 'bg-orange-100 text-orange-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-green-100 text-green-800',
  };

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-lg border-2 border-dashed border-orange-300 bg-orange-50">
        <div className="flex items-center justify-between">
          <div>
            <label className="text-xs text-orange-600">Documentation Gap Detected</label>
            <p className="text-xl font-bold text-orange-800">{output.gap_topic}</p>
          </div>
          <span className={`px-3 py-1 rounded text-sm font-semibold ${priorityColors[output.priority]}`}>
            {output.priority.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Suggested Doc Path</label>
        <code className="block mt-1 p-2 bg-gray-800 text-green-400 rounded text-sm">
          {output.suggested_doc_path}
        </code>
      </div>

      <div className="p-3 bg-gray-50 rounded-lg">
        <label className="text-xs text-gray-500">Suggested Outline</label>
        <ol className="list-decimal list-inside text-sm mt-1 space-y-1">
          {output.suggested_outline.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ol>
      </div>

      {output.affected_issues.length > 0 && (
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Affected Issues</label>
          <div className="flex flex-wrap gap-2 mt-1">
            {output.affected_issues.map((issue, idx) => (
              <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm">
                #{issue}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PromotionView({ output }: { output: PromotionOutput }) {
  return (
    <div className="space-y-4">
      <div className={`p-4 rounded-lg border-2 ${
        output.is_candidate
          ? 'border-green-500 bg-green-50'
          : 'border-gray-300 bg-gray-50'
      }`}>
        <div className="flex items-center justify-between">
          <div>
            <label className="text-xs text-gray-500">Promotion Decision</label>
            <p className={`text-xl font-bold ${output.is_candidate ? 'text-green-700' : 'text-gray-700'}`}>
              {output.is_candidate ? '✨ Promotion Candidate' : 'Not Ready for Promotion'}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-500">Confidence</p>
            <p className="text-2xl font-bold">{(output.confidence * 100).toFixed(0)}%</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Current Stage</label>
          <p className="font-semibold">{output.current_stage}</p>
        </div>
        <div className="p-3 bg-gray-50 rounded-lg">
          <label className="text-xs text-gray-500">Suggested Stage</label>
          <p className="font-semibold">{output.suggested_stage}</p>
        </div>
      </div>

      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
        <label className="text-xs text-blue-600">Recommendation</label>
        <p className="text-sm mt-1">{output.recommendation}</p>
      </div>
    </div>
  );
}
