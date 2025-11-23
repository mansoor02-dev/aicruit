import type { InterviewResponse, SubmitAnswerPayload } from '@/types';

/**
 * Starts an interview session and fetches initial questions
 * @param resumeId - The ID of the parsed resume
 * @returns Promise with interview response containing questions
 */
export async function startInterview(resumeId: string | null): Promise<InterviewResponse> {
  const res = await fetch('/api/start-interview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resumeId }),
  });

  if (!res.ok) {
    throw new Error('Failed to start interview');
  }

  return res.json();
}

/**
 * Submits an answer to a question and fetches the next question
 * @param payload - The answer payload containing questionId, answerText, and resumeId
 * @returns Promise with interview response containing next question
 */
export async function submitAnswer(payload: SubmitAnswerPayload): Promise<InterviewResponse> {
  const res = await fetch('/api/submit-answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error('Failed to submit answer');
  }

  return res.json();
}

