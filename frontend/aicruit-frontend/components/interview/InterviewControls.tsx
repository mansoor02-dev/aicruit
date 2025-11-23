import React from 'react';

type InterviewState = 'idle' | 'ready' | 'running' | 'finished';

interface InterviewControlsProps {
  interviewState: InterviewState;
  currentIndex: number;
  totalQuestions: number;
  onStartInterview: () => void;
}

export function InterviewControls({
  interviewState,
  currentIndex,
  totalQuestions,
  onStartInterview,
}: InterviewControlsProps) {
  return (
    <section className="mb-10">
      <h2 className="text-2xl font-semibold mb-4 text-blue-700">Interview Controls</h2>
      <div className="flex flex-col md:flex-row justify-center gap-4 items-center">
        <button
          className="px-8 py-3 bg-green-500 hover:bg-green-600 text-white rounded-full font-semibold shadow-md disabled:opacity-50 transition"
          onClick={onStartInterview}
          disabled={interviewState !== 'ready'}
        >
          Start Interview
        </button>
        <div className="text-gray-600 font-medium">State: {interviewState}</div>
        {interviewState === 'running' && (
          <div className="text-gray-600 font-medium">
            Question {currentIndex + 1} / {totalQuestions}
          </div>
        )}
      </div>
    </section>
  );
}

