import React from 'react';

type InterviewState = 'idle' | 'ready' | 'running' | 'finished';

interface InterviewControlsProps {
  interviewState: InterviewState;
  currentIndex: number;
  totalQuestions: number;
  jobDescription: string;
  onJobDescriptionChange: (description: string) => void;
  onStartInterview: () => void;
}

export function InterviewControls({
  interviewState,
  currentIndex,
  totalQuestions,
  jobDescription,
  onJobDescriptionChange,
  onStartInterview,
}: InterviewControlsProps) {
  return (
    <section className="mb-10">
      <h2 className="text-2xl font-semibold mb-4 text-blue-700">Interview Controls</h2>
      
      {/* Job Description Input */}
      {interviewState === 'ready' && (
        <div className="mb-6 w-full max-w-2xl mx-auto">
          <label className="block text-sm font-semibold text-gray-700 mb-2">Job Description</label>
          <textarea
            value={jobDescription}
            onChange={(e) => onJobDescriptionChange(e.target.value)}
            placeholder="Paste the job description here..."
            rows={4}
            className="w-full p-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

      <div className="flex flex-col md:flex-row justify-center gap-4 items-center">
        <button
          className="px-8 py-3 bg-green-500 hover:bg-green-600 text-white rounded-full font-semibold shadow-md disabled:opacity-50 transition"
          onClick={onStartInterview}
          disabled={interviewState !== 'ready' || !jobDescription.trim()}
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

