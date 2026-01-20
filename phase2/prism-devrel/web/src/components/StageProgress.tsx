'use client';

import { STAGES, StageName } from '@/types';

interface StageProgressProps {
  currentStage: string;
  suggestedStage: string;
  isCandidate: boolean;
}

const stageColors: Record<string, string> = {
  NEW: 'bg-gray-400',
  FIRST_TIMER: 'bg-blue-500',
  REGULAR: 'bg-green-500',
  CORE: 'bg-purple-500',
  MAINTAINER: 'bg-orange-500',
};

export function StageProgress({ currentStage, suggestedStage, isCandidate }: StageProgressProps) {
  const stages = Object.entries(STAGES).sort((a, b) => a[1].order - b[1].order);
  const currentIndex = stages.findIndex(([key]) => key === currentStage);
  const suggestedIndex = stages.findIndex(([key]) => key === suggestedStage);

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        {stages.map(([key, stage], index) => {
          const isActive = index <= currentIndex;
          const isSuggested = isCandidate && index === suggestedIndex;
          const isPast = index < currentIndex;

          return (
            <div key={key} className="flex flex-col items-center flex-1">
              <div className="relative">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500
                    ${isActive ? stageColors[key] + ' text-white' : 'bg-gray-200 text-gray-500'}
                    ${isSuggested ? 'ring-4 ring-yellow-400 ring-opacity-50 animate-pulse' : ''}
                  `}
                >
                  {index + 1}
                </div>
                {isSuggested && (
                  <div className="absolute -top-6 left-1/2 transform -translate-x-1/2">
                    <span className="text-xs bg-yellow-400 text-yellow-900 px-2 py-0.5 rounded-full whitespace-nowrap">
                      Suggested
                    </span>
                  </div>
                )}
              </div>
              <span className={`mt-1 text-xs ${isActive ? 'font-semibold text-gray-900' : 'text-gray-500'}`}>
                {stage.label}
              </span>
              <span className="text-[10px] text-gray-400">
                {stage.minPRs}+ PRs
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="relative h-2 bg-gray-200 rounded-full mt-4">
        <div
          className={`absolute h-full rounded-full transition-all duration-1000 ${stageColors[currentStage]}`}
          style={{ width: `${((currentIndex + 1) / stages.length) * 100}%` }}
        />
        {isCandidate && (
          <div
            className="absolute h-full rounded-full bg-yellow-400 opacity-50 animate-pulse"
            style={{
              left: `${((currentIndex + 1) / stages.length) * 100}%`,
              width: `${(1 / stages.length) * 100}%`
            }}
          />
        )}
      </div>
    </div>
  );
}
