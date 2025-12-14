import { useState, useCallback } from 'react';
import type { Question, ParsedResumeData, SubmitAnswerPayload } from '@/types';
import { startInterview, submitAnswer } from '@/lib/api/interview';

type InterviewState = 'idle' | 'ready' | 'running' | 'finished';

interface UseInterviewOptions {
  parsedData: ParsedResumeData | null;
  jobDescription?: string;
  onError?: (error: string) => void;
}

/**
 * Custom hook for managing interview state and flow
 * @param options - Interview configuration
 * @returns Interview state and controls
 */
export function useInterview({ parsedData, jobDescription = '', onError }: UseInterviewOptions) {
  const [interviewState, setInterviewState] = useState<InterviewState>('idle');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [processingAnswer, setProcessingAnswer] = useState(false);

  const handleStartInterview = useCallback(async () => {
    setInterviewState('running');
    setProcessingAnswer(false);

    try {
      const payload = await startInterview(parsedData?.id || null, jobDescription);
      const qs = payload.questions || [];
      setQuestions(qs);
      setCurrentIndex(0);
      setCurrentQuestion(qs[0] || null);
    } catch (err) {
      console.error(err);
      const errorMsg = err instanceof Error ? err.message : 'Could not start interview';
      onError?.(errorMsg);
      setInterviewState('idle');
    }
  }, [parsedData, jobDescription, onError]);

  const handleSubmitAnswer = useCallback(
    async (answerText: string) => {
      setProcessingAnswer(true);

      try {
        const payload: SubmitAnswerPayload = {
          questionId: currentQuestion?.id || null,
          answerText,
          resumeId: parsedData?.id || null,
        };

        const data = await submitAnswer(payload);
        const nextQ = data.nextQuestion || null;

        setProcessingAnswer(false);

        if (nextQ) {
          // Advance to next question
          setCurrentIndex((i) => i + 1);
          setCurrentQuestion(nextQ);
          return true; // Indicates there's a next question
        } else {
          // Interview finished
          setInterviewState('finished');
          setCurrentQuestion(null);
          return false; // Indicates interview is complete
        }
      } catch (err) {
        console.error(err);
        setProcessingAnswer(false);
        const errorMsg = err instanceof Error ? err.message : 'Submit failed';
        onError?.(errorMsg);
        return false;
      }
    },
    [currentQuestion, parsedData, onError]
  );

  const reset = useCallback(() => {
    setInterviewState('idle');
    setQuestions([]);
    setCurrentIndex(0);
    setCurrentQuestion(null);
    setProcessingAnswer(false);
  }, []);

  // Update state to ready when resume is uploaded
  const setReady = useCallback(() => {
    setInterviewState('ready');
  }, []);

  return {
    interviewState,
    questions,
    currentIndex,
    currentQuestion,
    processingAnswer,
    handleStartInterview,
    handleSubmitAnswer,
    reset,
    setReady,
  };
}

