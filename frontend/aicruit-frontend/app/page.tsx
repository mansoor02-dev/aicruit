/*
AIcruit - Interview Page (Frontend)

This Next.js / React component implements a single-page interview flow:
- Drag & drop resume upload (PDF/DOCX)
- Sends resume to backend: POST /upload-file?file_type=resume
- Receives file upload confirmation with file_url
- Fetches/receives adaptive questions from backend: POST /api/start-interview
- Displays one question at a time with 60s timer
- Speech-to-text using Web Speech API (SpeechRecognition) with fallback instructions
- Sends transcribed answers to backend: POST /api/submit-answer
- Handles interview completion and basic UX states

Tailwind CSS is used for styling.
*/
"use client";

import React, { useState, useRef, useEffect } from 'react';
import type { 
  ParsedResumeData, 
  Question, 
  InterviewResponse, 
  SubmitAnswerPayload,
  UploadFileResponse,
  ISpeechRecognition,
  ISpeechRecognitionEvent,
  ISpeechRecognitionErrorEvent
} from '@/types';
import { getApiUrl, API_CONFIG } from '@/config/api';

export default function InterviewPage() {
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [parsedData, setParsedData] = useState<ParsedResumeData | null>(null);

  const [interviewState, setInterviewState] = useState<'idle' | 'ready' | 'running' | 'finished'>('idle');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [timer, setTimer] = useState(60);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [processingAnswer, setProcessingAnswer] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  // Drag & Drop handlers
  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }
  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  }
  function handleFile(f: File) {
    const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!allowed.includes(f.type)) {
      setErrorMsg('Only PDF or DOCX files are allowed.');
      return;
    }
    setResumeFile(f);
    setErrorMsg(null);
  }

  async function uploadResume() {
  if (!resumeFile) return;

  setUploadStatus("uploading");
  setErrorMsg(null);

  try {
    const form = new FormData();
    form.append("file", resumeFile);

    // API expects file_type as query parameter
    const url = `${getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD_RESUME)}?file_type=resume`;

    const res = await fetch(url, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      throw new Error(errData?.message || "File upload failed");
    }

    const data: UploadFileResponse = await res.json();

    // API already returns `id` so no need to extract from file_url
    const fileId = data.id;

    setParsedData({
      id: fileId,
      file_url: data.file_url,
      status: data.status,
      message: data.message
    });

    setUploadStatus("success");
    setInterviewState("ready");

  } catch (err) {
    console.error(err);
    setUploadStatus("error");
    setErrorMsg(err instanceof Error ? err.message : "Upload failed");
  }
}


  // Start interview: request questions from backend using parsedData (or resume file id)
  async function startInterview() {
    setInterviewState('running');
    setProcessingAnswer(false);
    try {
      const res = await fetch('/api/start-interview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resumeId: parsedData?.id || null }),
      });
      if (!res.ok) throw new Error('Failed to start interview');
      const payload: InterviewResponse = await res.json();
      const qs = payload.questions || [];
      setQuestions(qs);
      setCurrentIndex(0);
      setCurrentQuestion(qs[0] || null);
      setTimer(60);
      // initialize speech recognition
      initSpeechRecognition();
    } catch (err) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Could not start interview');
      setInterviewState('idle');
    }
  }

  // Speech Recognition setup
  function initSpeechRecognition() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      // Browser doesn't support; you'll need to send audio to backend with MediaRecorder
      console.warn('SpeechRecognition not supported in this browser.');
      setErrorMsg('SpeechRecognition API not supported. Please use Chrome/Edge on desktop.');
      return;
    }
    const recognition = new SpeechRecognition() as ISpeechRecognition;
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = (ev: ISpeechRecognitionEvent) => {
      let interim = '';
      let final = '';
      for (let i = ev.resultIndex; i < ev.results.length; ++i) {
        const res = ev.results[i];
        if (res.isFinal) final += res[0].transcript;
        else interim += res[0].transcript;
      }
      setTranscript((t) => (final ? (t + ' ' + final).trim() : t + ' ' + interim).trim());
    };
    recognition.onerror = (ev: ISpeechRecognitionErrorEvent) => {
      console.error('Recognition error', ev);
      setErrorMsg('Speech recognition error: ' + (ev.error || 'unknown'));
    };
    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;
  }

  function startListening() {
    if (!recognitionRef.current) {
      initSpeechRecognition();
      if (!recognitionRef.current) return;
    }
    try {
      recognitionRef.current.start();
      setListening(true);
    } catch (err) {
      console.warn(err);
    }
  }
  function stopListening() {
    if (recognitionRef.current) recognitionRef.current.stop();
    setListening(false);
  }

  // Timer effect per question
  useEffect(() => {
    if (interviewState !== 'running' || !currentQuestion) return;
    setTimer(60);
    const id = setInterval(() => {
      setTimer((t) => {
        if (t <= 1) {
          clearInterval(id);
          // auto-submit current transcript and move to next question
          handleSubmitAnswer();
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentQuestion, interviewState]);

  // Submit answer to backend and fetch next question
  async function handleSubmitAnswer() {
    // Stop recognition before submitting
    stopListening();
    setProcessingAnswer(true);
    try {
      const payload: SubmitAnswerPayload = {
        questionId: currentQuestion?.id || null,
        answerText: transcript,
        resumeId: parsedData?.id || null,
      };
      const res = await fetch('/api/submit-answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to submit answer');
      const data: InterviewResponse = await res.json();
      const nextQ = data.nextQuestion || null;
      setTranscript('');
      setProcessingAnswer(false);
      if (nextQ) {
        // advance
        setCurrentIndex((i) => i + 1);
        setCurrentQuestion(nextQ);
        setTimer(60);
      } else {
        // interview finished
        setInterviewState('finished');
        setCurrentQuestion(null);
      }
    } catch (err) {
      console.error(err);
      setProcessingAnswer(false);
      setErrorMsg(err instanceof Error ? err.message : 'Submit failed');
    }
  }

  // UI components  
  return (
  <div className="min-h-screen bg-gradient-to-br from-blue-100 via-blue-50 to-blue-100 flex justify-center items-start p-3">
    <div className="w-full max-w-3xl bg-white rounded-3xl shadow-2xl p-10 mt-5 text-center">
      <h1 className="text-4xl font-extrabold text-blue-800 mb-8">AIcruit — Interview Page</h1>

      {/* Resume Upload Section */}
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-6 text-blue-700">Upload Your Resume</h2>
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          className="border-2 border-dashed border-blue-300 p-8 rounded-2xl flex flex-col items-center justify-center hover:border-blue-500 transition-colors duration-300 bg-gradient-to-br from-white to-blue-50 shadow-lg"
        >
          <p className="mb-2 text-gray-600 text-lg">Drag & drop your resume here</p>
          <p className="text-sm text-gray-400 mb-4">Accepted formats: PDF, DOCX</p>

          {/* Custom Centered File Input */}
          <div className="mb-4 w-full flex justify-center">
            <label className="relative cursor-pointer inline-block w-full max-w-xs">
              <input
                type="file"
                accept=".pdf,.docx"
                onChange={handleFileSelect}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="px-6 py-3 bg-white text-gray-700 border border-gray-300 rounded-full shadow-md hover:bg-gray-100 transition text-center">
                {resumeFile ? resumeFile.name : "Choose File"}
              </div>
            </label>
          </div>

          <div className="mt-4">
            <button
              className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full font-semibold shadow-md disabled:opacity-50 transition"
              onClick={uploadResume}
              disabled={!resumeFile || uploadStatus === "uploading"}
            >
              {uploadStatus === "uploading" ? "Uploading..." : "Upload Resume"}
            </button>
          </div>

          {uploadStatus === "success" && (
            <div className="mt-3 text-green-600 font-medium">Resume parsed successfully!</div>
          )}
          {uploadStatus === "error" && (
            <div className="mt-3 text-red-600 font-medium">Error uploading resume.</div>
          )}
        </div>
      </section>

      {/* Interview Control */}
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-4 text-blue-700">Interview Controls</h2>
        <div className="flex flex-col md:flex-row justify-center gap-4 items-center">
          <button
            className="px-8 py-3 bg-green-500 hover:bg-green-600 text-white rounded-full font-semibold shadow-md disabled:opacity-50 transition"
            onClick={startInterview}
            disabled={interviewState !== "ready"}
          >
            Start Interview
          </button>
          <div className="text-gray-600 font-medium">State: {interviewState}</div>
          {interviewState === "running" && (
            <div className="text-gray-600 font-medium">Question {currentIndex + 1} / {questions.length}</div>
          )}
        </div>
      </section>

      {/* Question & Recorder */}
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-4 text-blue-700">Current Question</h2>
        <div className="border rounded-2xl p-6 bg-gradient-to-br from-blue-50 to-white shadow-inner text-center">
          {interviewState === "idle" && <p className="text-gray-500 text-lg">Upload resume to start.</p>}
          {interviewState === "ready" && <p className="text-gray-500 text-lg">Ready. Click <strong>Start Interview</strong>.</p>}
          {interviewState === "running" && currentQuestion && (
            <>
              <div className="mb-4 text-xl font-semibold text-blue-800">{currentQuestion.text}</div>

              <div className="flex flex-wrap justify-center gap-4 items-center mb-4">
                <div className="px-5 py-2 bg-white rounded-full shadow-md text-gray-700 font-medium">Timer: {timer}s</div>
                {!listening ? (
                  <button
                    className="px-5 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-full font-medium shadow-md"
                    onClick={startListening}
                  >
                    Start Mic
                  </button>
                ) : (
                  <button
                    className="px-5 py-2 bg-red-500 hover:bg-red-600 text-white rounded-full font-medium shadow-md"
                    onClick={stopListening}
                  >
                    Stop Mic
                  </button>
                )}
                <button
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full font-medium shadow-md"
                  onClick={handleSubmitAnswer}
                  disabled={processingAnswer}
                >
                  {processingAnswer ? "Submitting..." : "Submit Answer"}
                </button>
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">Transcript (editable)</label>
                <textarea
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                  rows={5}
                  className="w-full p-3 border rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
            </>
          )}
          {interviewState === "finished" && (
            <div className="text-green-600 font-semibold text-lg">Interview complete. Thank you!</div>
          )}
        </div>
      </section>

      {/* Errors */}
      {errorMsg && <div className="mt-4 text-red-600 font-medium">{errorMsg}</div>}
    </div>
  </div>
);


}