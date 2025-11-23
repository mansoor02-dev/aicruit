import React from 'react';
import type { Question } from '@/types';

type InterviewState = 'idle' | 'ready' | 'running' | 'finished';

interface QuestionDisplayProps {
  interviewState: InterviewState;
  currentQuestion: Question | null;
  timer: number;
  listening: boolean;
  transcript: string;
  processingAnswer: boolean;
  onStartListening: () => void;
  onStopListening: () => void;
  onSubmitAnswer: () => void;
  onTranscriptChange: (text: string) => void;
}

export function QuestionDisplay({
  interviewState,
  currentQuestion,
  timer,
  listening,
  transcript,
  processingAnswer,
  onStartListening,
  onStopListening,
  onSubmitAnswer,
  onTranscriptChange,
}: QuestionDisplayProps) {
  return (
    <section className="mb-10">
      <h2 className="text-2xl font-semibold mb-4 text-blue-700">Current Question</h2>
      <div className="border rounded-2xl p-6 bg-gradient-to-br from-blue-50 to-white shadow-inner text-center">
        {interviewState === 'idle' && (
          <p className="text-gray-500 text-lg">Upload resume to start.</p>
        )}
        {interviewState === 'ready' && (
          <p className="text-gray-500 text-lg">
            Ready. Click <strong>Start Interview</strong>.
          </p>
        )}
        {interviewState === 'running' && currentQuestion && (
          <>
            <div className="mb-4 text-xl font-semibold text-blue-800">{currentQuestion.text}</div>

            <div className="flex flex-wrap justify-center gap-4 items-center mb-4">
              <div className="px-5 py-2 bg-white rounded-full shadow-md text-gray-700 font-medium">
                Timer: {timer}s
              </div>
              {!listening ? (
                <button
                  className="px-5 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-full font-medium shadow-md"
                  onClick={onStartListening}
                >
                  Start Mic
                </button>
              ) : (
                <button
                  className="px-5 py-2 bg-red-500 hover:bg-red-600 text-white rounded-full font-medium shadow-md"
                  onClick={onStopListening}
                >
                  Stop Mic
                </button>
              )}
              <button
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full font-medium shadow-md"
                onClick={onSubmitAnswer}
                disabled={processingAnswer}
              >
                {processingAnswer ? 'Submitting...' : 'Submit Answer'}
              </button>
            </div>

            <div>
              <label className="block text-sm text-gray-600 mb-1">Transcript (editable)</label>
              <textarea
                value={transcript}
                onChange={(e) => onTranscriptChange(e.target.value)}
                rows={5}
                className="w-full p-3 border rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
          </>
        )}
        {interviewState === 'finished' && (
          <div className="text-green-600 font-semibold text-lg">
            Interview complete. Thank you!
          </div>
        )}
      </div>
    </section>
  );
}

