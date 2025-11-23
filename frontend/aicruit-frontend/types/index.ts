// Type definitions for AIcruit Interview Application

// Speech Recognition API types
export interface ISpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: ISpeechRecognitionEvent) => void) | null;
  onerror: ((event: ISpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

export interface ISpeechRecognitionEvent {
  resultIndex: number;
  results: ISpeechRecognitionResultList;
}

export interface ISpeechRecognitionResultList {
  length: number;
  item(index: number): ISpeechRecognitionResult;
  [index: number]: ISpeechRecognitionResult;
}

export interface ISpeechRecognitionResult {
  isFinal: boolean;
  length: number;
  item(index: number): ISpeechRecognitionAlternative;
  [index: number]: ISpeechRecognitionAlternative;
}

export interface ISpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

export interface ISpeechRecognitionErrorEvent {
  error: string;
  message?: string;
}

declare global {
  interface Window {
    SpeechRecognition: {
      new (): ISpeechRecognition;
    };
    webkitSpeechRecognition: {
      new (): ISpeechRecognition;
    };
  }
}

// Application types
export interface ParsedResumeData {
  id?: string;
  name?: string;
  email?: string;
  skills?: string[];
  experience?: string;
  [key: string]: unknown;
}

// Backend API response types
export interface UploadFileResponse {
  status: string;
  file_url: string;
  message: string;
  id: string;
}

export interface Question {
  id: string;
  text: string;
  type?: string;
  [key: string]: unknown;
}

export interface InterviewResponse {
  questions?: Question[];
  nextQuestion?: Question | null;
  message?: string;
  [key: string]: unknown;
}

export interface SubmitAnswerPayload {
  questionId: string | null;
  answerText: string;
  resumeId: string | null;
}

