import { useState, useRef, useCallback } from 'react';
import type {
  ISpeechRecognition,
  ISpeechRecognitionEvent,
  ISpeechRecognitionErrorEvent,
} from '@/types';

interface UseSpeechRecognitionOptions {
  onError?: (error: string) => void;
}

/**
 * Custom hook for managing speech recognition
 * @param options - Configuration options
 * @returns Speech recognition state and controls
 */
export function useSpeechRecognition({ onError }: UseSpeechRecognitionOptions = {}) {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef<ISpeechRecognition | null>(null);

  const initSpeechRecognition = useCallback(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      const errorMsg =
        'SpeechRecognition API not supported. Please use Chrome/Edge on desktop.';
      onError?.(errorMsg);
      console.warn('SpeechRecognition not supported in this browser.');
      return false;
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
      setTranscript((t) =>
        final ? (t + ' ' + final).trim() : (t + ' ' + interim).trim()
      );
    };

    recognition.onerror = (ev: ISpeechRecognitionErrorEvent) => {
      console.error('Recognition error', ev);
      const errorMsg = 'Speech recognition error: ' + (ev.error || 'unknown');
      onError?.(errorMsg);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;
    return true;
  }, [onError]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current) {
      const initialized = initSpeechRecognition();
      if (!initialized || !recognitionRef.current) return;
    }
    try {
      recognitionRef.current.start();
      setListening(true);
    } catch (err) {
      console.warn(err);
    }
  }, [initSpeechRecognition]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setListening(false);
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript('');
  }, []);

  const setTranscriptManually = useCallback((text: string) => {
    setTranscript(text);
  }, []);

  return {
    listening,
    transcript,
    startListening,
    stopListening,
    resetTranscript,
    setTranscript: setTranscriptManually,
    initSpeechRecognition,
  };
}

