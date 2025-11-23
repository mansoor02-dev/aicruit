/*
AIcruit - Interview Page (Frontend)

This Next.js / React component implements a single-page interview flow:
- Drag & drop resume upload (PDF/DOCX)
- Sends resume to backend: POST /api/upload-resume
- Receives parsed resume confirmation
- Fetches/receives adaptive questions from backend: POST /api/start-interview
- Displays one question at a time with 60s timer
- Speech-to-text using Web Speech API (SpeechRecognition) with fallback instructions
- Sends transcribed answers to backend: POST /api/submit-answer
- Handles interview completion and basic UX states

Tailwind CSS is used for styling.
*/
"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useResumeUpload } from '@/hooks/useResumeUpload';
import { useInterview } from '@/hooks/useInterview';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { useTimer } from '@/hooks/useTimer';
import { ResumeUploadSection } from '@/components/interview/ResumeUploadSection';
import { InterviewControls } from '@/components/interview/InterviewControls';
import { QuestionDisplay } from '@/components/interview/QuestionDisplay';
import { ErrorDisplay } from '@/components/interview/ErrorDisplay';

export default function InterviewPage() {
  // Resume upload hook
  const {
    resumeFile,
    uploadStatus,
    parsedData,
    errorMsg: uploadErrorMsg,
    parsing,
    handleFileSelect,
    handleDrop,
    handleUpload,
    handleParse,
  } = useResumeUpload();

  // Error state management
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Interview hook
  const {
    interviewState,
    questions,
    currentIndex,
    currentQuestion,
    processingAnswer,
    handleStartInterview,
    handleSubmitAnswer,
    setReady,
  } = useInterview({
    parsedData,
    onError: setErrorMsg,
  });

  // Speech recognition hook
  const {
    listening,
    transcript,
    startListening,
    stopListening,
    resetTranscript,
    setTranscript,
    initSpeechRecognition,
  } = useSpeechRecognition({
    onError: setErrorMsg,
  });

  // Timer hook - auto-submit on timeout (matches original behavior)
  const handleTimeout = useCallback(() => {
    if (interviewState === 'running' && currentQuestion) {
      // Stop listening before submitting (original behavior)
      stopListening();
      handleSubmitAnswer(transcript).then((hasNext) => {
        if (hasNext) {
          resetTranscript();
        }
      });
    }
  }, [interviewState, currentQuestion, transcript, handleSubmitAnswer, resetTranscript, stopListening]);

  const { timer, reset: resetTimer } = useTimer({
    initialTime: 60,
    onTimeout: handleTimeout,
    enabled: interviewState === 'running' && currentQuestion !== null,
  });

  // Set interview to ready when resume upload succeeds
  useEffect(() => {
    if (uploadStatus === 'success' && parsedData) {
      setReady();
    }
  }, [uploadStatus, parsedData, setReady]);

  // Initialize speech recognition when interview starts
  useEffect(() => {
    if (interviewState === 'running') {
      initSpeechRecognition();
    }
  }, [interviewState, initSpeechRecognition]);

  // Reset timer when question changes
  useEffect(() => {
    if (interviewState === 'running' && currentQuestion) {
      resetTimer(60);
    }
  }, [currentQuestion, interviewState, resetTimer]);

  // Handle answer submission
  const handleAnswerSubmit = useCallback(async () => {
    stopListening();
    const hasNext = await handleSubmitAnswer(transcript);
    if (hasNext) {
      resetTranscript();
      resetTimer(60);
    }
  }, [transcript, handleSubmitAnswer, stopListening, resetTranscript, resetTimer]);

  // Combine error messages
  const displayError = errorMsg || uploadErrorMsg;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-100 via-blue-50 to-blue-100 flex justify-center items-start p-3">
      <div className="w-full max-w-3xl bg-white rounded-3xl shadow-2xl p-10 mt-5 text-center">
        <h1 className="text-4xl font-extrabold text-blue-800 mb-8">AIcruit — Interview Page</h1>

        <ResumeUploadSection
          resumeFile={resumeFile}
          uploadStatus={uploadStatus}
          onFileSelect={handleFileSelect}
          onDrop={handleDrop}
          onUpload={handleUpload}
          parsedData={parsedData}
          onParse={handleParse}
          parsing={parsing}
        />

        <InterviewControls
          interviewState={interviewState}
          currentIndex={currentIndex}
          totalQuestions={questions.length}
          onStartInterview={handleStartInterview}
        />

        <QuestionDisplay
          interviewState={interviewState}
          currentQuestion={currentQuestion}
          timer={timer}
          listening={listening}
          transcript={transcript}
          processingAnswer={processingAnswer}
          onStartListening={startListening}
          onStopListening={stopListening}
          onSubmitAnswer={handleAnswerSubmit}
          onTranscriptChange={setTranscript}
        />

        <ErrorDisplay errorMsg={displayError} />
      </div>
    </div>
  );
}