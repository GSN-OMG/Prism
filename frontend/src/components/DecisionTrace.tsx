'use client';

import { useState } from 'react';
import { DecisionStep } from '@/types';

interface DecisionTraceProps {
  steps: DecisionStep[];
  modelUsed: string;
  durationMs: number;
}

export function DecisionTrace({ steps, modelUsed, durationMs }: DecisionTraceProps) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const getStepIcon = (stepName: string): string => {
    if (stepName.includes('Load')) return '📥';
    if (stepName.includes('Infer') || stepName.includes('Stage')) return '🎯';
    if (stepName.includes('Evaluate') || stepName.includes('Criteria')) return '📊';
    if (stepName.includes('Determine') || stepName.includes('Eligibility')) return '✅';
    if (stepName.includes('Calculate') || stepName.includes('Confidence')) return '🔢';
    if (stepName.includes('Generate') || stepName.includes('Recommendation')) return '💡';
    return '⚙️';
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h4 className="font-semibold text-gray-900 flex items-center gap-2">
          <span>🔍</span> Decision Trace
        </h4>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="bg-gray-200 px-2 py-1 rounded">Model: {modelUsed}</span>
          <span className="bg-gray-200 px-2 py-1 rounded">Duration: {durationMs}ms</span>
        </div>
      </div>

      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-300" />

        <div className="space-y-3">
          {steps.map((step, index) => (
            <div
              key={step.step_number}
              className={`relative pl-10 animate-fade-in`}
              style={{ animationDelay: `${index * 150}ms` }}
            >
              {/* Step number circle */}
              <div className="absolute left-0 w-8 h-8 rounded-full bg-primary-500 text-white flex items-center justify-center text-sm font-bold shadow-md">
                {step.step_number}
              </div>

              <div
                className={`bg-white rounded-lg border border-gray-200 overflow-hidden cursor-pointer transition-all hover:shadow-md ${
                  expandedStep === step.step_number ? 'ring-2 ring-primary-500' : ''
                }`}
                onClick={() => setExpandedStep(expandedStep === step.step_number ? null : step.step_number)}
              >
                {/* Header */}
                <div className="px-4 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{getStepIcon(step.step_name)}</span>
                    <span className="font-medium text-gray-900">{step.step_name}</span>
                  </div>
                  <svg
                    className={`w-5 h-5 text-gray-400 transition-transform ${
                      expandedStep === step.step_number ? 'rotate-180' : ''
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>

                {/* Reasoning preview */}
                <div className="px-4 pb-3 text-sm text-gray-600">
                  {step.reasoning}
                </div>

                {/* Expanded content */}
                {expandedStep === step.step_number && (
                  <div className="border-t border-gray-100 bg-gray-50 px-4 py-3 space-y-3">
                    {/* Input */}
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase">Input</span>
                      <pre className="mt-1 text-xs bg-white p-2 rounded border border-gray-200 overflow-x-auto">
                        {JSON.stringify(step.input, null, 2)}
                      </pre>
                    </div>

                    {/* Output */}
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase">Output</span>
                      <pre className="mt-1 text-xs bg-white p-2 rounded border border-gray-200 overflow-x-auto">
                        {JSON.stringify(step.output, null, 2)}
                      </pre>
                    </div>

                    {/* Timestamp */}
                    <div className="text-xs text-gray-400">
                      Timestamp: {new Date(step.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
