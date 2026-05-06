'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  Square,
  ArrowRight,
  Monitor,
  Headphones,
  HelpCircle,
  Clock,
  PhoneOff,
  Camera,
  CameraOff,
  UserCheck,
  Sun,
  MonitorOff,
  Video,
  ScreenShare,
  Sparkles,
} from 'lucide-react';
import { getAuthToken } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const QUESTION_TIMER_SECONDS = 180; // 3 minutes per question

// ─── Types ───────────────────────────────────────────────────────────────────

type InterviewPhase = 'lobby' | 'interview' | 'finished';
type LobbyStep = 'instructions' | 'devices' | 'screenshare' | 'ready';

interface QuestionData {
  interviewId: string;
  questionText: string;
  questionSequence: number;
  audioBlob: Blob | null;
  category?: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function InterviewPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const { toast } = useToast();
  const applicationId = params.id as string;

  // Phase management
  const [phase, setPhase] = useState<InterviewPhase>('lobby');
  const [lobbyStep, setLobbyStep] = useState<LobbyStep>('instructions');

  // Device check (camera + mic, single getUserMedia call)
  const [deviceStatus, setDeviceStatus] = useState<'idle' | 'requesting' | 'ready' | 'denied' | 'error'>('idle');
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const [cameraLive, setCameraLive] = useState(false);
  const [micLive, setMicLive] = useState(false);
  const [micLevel, setMicLevel] = useState(0);

  // Screen share
  const [screenStatus, setScreenStatus] = useState<'idle' | 'requesting' | 'ready' | 'error'>('idle');
  const [screenError, setScreenError] = useState<string | null>(null);

  // Refs (media)
  const userMediaStreamRef = useRef<MediaStream | null>(null); // camera + mic combined
  const cameraStreamRef = useRef<MediaStream | null>(null); // video-only view of userMediaStream
  const audioStreamRef = useRef<MediaStream | null>(null); // audio-only view
  const screenStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Lobby video preview
  const lobbyVideoRef = useRef<HTMLVideoElement | null>(null);

  // Interview state
  const [currentQuestion, setCurrentQuestion] = useState<QuestionData | null>(null);
  const [totalQuestions, setTotalQuestions] = useState<number | null>(null);
  const [isFixedCount, setIsFixedCount] = useState<boolean | null>(null);
  const [isLoadingQuestion, setIsLoadingQuestion] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [questionCount, setQuestionCount] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [isInterviewEnded, setIsInterviewEnded] = useState(false);
  const [endReason, setEndReason] = useState('');

  // End interview dialog
  const [endDialogOpen, setEndDialogOpen] = useState(false);
  const [isEndingInterview, setIsEndingInterview] = useState(false);

  // Timer state
  const [timeRemaining, setTimeRemaining] = useState(QUESTION_TIMER_SECONDS);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Refs (audio playback / recording)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // ─── Timer ────────────────────────────────────────────────────────────────

  const startTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
    }
    setTimeRemaining(QUESTION_TIMER_SECONDS);

    timerIntervalRef.current = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          if (timerIntervalRef.current) {
            clearInterval(timerIntervalRef.current);
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
  }, []);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // ─── End Interview ────────────────────────────────────────────────────────

  const handleEndInterview = useCallback(
    async (reason: string = 'Interview completed.') => {
      stopTimer();
      setEndReason(reason);
      setIsInterviewEnded(true);
      setPhase('finished');

      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);

      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
    },
    [stopTimer]
  );

  // When timer hits 0, end the interview
  useEffect(() => {
    if (timeRemaining === 0 && phase === 'interview' && currentQuestion) {
      stopTimer();
      handleEndInterview('Time expired for the question.');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRemaining, phase]);

  const callEndInterviewAPI = useCallback(async () => {
    if (!currentQuestion?.interviewId) return;

    try {
      const token = getAuthToken();
      const formData = new FormData();
      formData.append('interview_id', currentQuestion.interviewId);

      const res = await fetch(`${API_BASE_URL}/interview/end`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      throw err;
    }
  }, [currentQuestion]);

  const stopAllMedia = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try {
        mediaRecorderRef.current.stop();
      } catch {}
    }
    if (audioPlayerRef.current) {
      try {
        audioPlayerRef.current.pause();
      } catch {}
    }
    // userMediaStreamRef owns the underlying camera+mic tracks.
    // cameraStreamRef/audioStreamRef are shadow MediaStream wrappers around
    // the SAME tracks — stopping userMediaStreamRef stops them too. Just null
    // out the refs to release references rather than calling .stop() again.
    if (userMediaStreamRef.current) {
      userMediaStreamRef.current.getTracks().forEach((t) => t.stop());
      userMediaStreamRef.current = null;
    }
    cameraStreamRef.current = null;
    audioStreamRef.current = null;
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach((t) => t.stop());
      screenStreamRef.current = null;
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {}
      audioContextRef.current = null;
    }
  }, []);

  const confirmEndInterview = useCallback(async () => {
    setIsEndingInterview(true);
    try {
      await callEndInterviewAPI();
      stopTimer();
      stopAllMedia();
      if (lobbyVideoRef.current) {
        lobbyVideoRef.current.srcObject = null;
      }
      setEndDialogOpen(false);
      setIsRecording(false);
      router.push(`/candidate/interview/thank-you?applicationId=${encodeURIComponent(applicationId)}`);
    } catch (err: any) {
      toast({
        title: 'Failed to end interview',
        description: err?.message || 'Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsEndingInterview(false);
    }
  }, [callEndInterviewAPI, stopAllMedia, stopTimer, router, toast, applicationId]);

  // ─── Device check (single getUserMedia for camera+mic) ──────────────────

  const requestDevices = useCallback(async () => {
    setDeviceStatus('requesting');
    setDeviceError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      userMediaStreamRef.current = stream;

      // Build per-track shadow streams so the recorder/preview/snapshot logic
      // can operate on focused video-only or audio-only views without
      // re-acquiring the underlying tracks.
      cameraStreamRef.current = new MediaStream(stream.getVideoTracks());
      audioStreamRef.current = new MediaStream(stream.getAudioTracks());

      // Camera live indicator: wait for the video element to start playing
      const videoTracks = stream.getVideoTracks();
      const audioTracks = stream.getAudioTracks();

      if (videoTracks[0]) {
        const t = videoTracks[0];
        const update = () => setCameraLive(t.readyState === 'live' && !t.muted);
        update();
        t.addEventListener('unmute', update);
        t.addEventListener('mute', update);
        t.addEventListener('ended', update);
      }
      if (audioTracks[0]) {
        const t = audioTracks[0];
        const update = () => setMicLive(t.readyState === 'live');
        update();
        t.addEventListener('ended', update);
      }

      // Set up analyser on the audio track for the live mic level meter
      try {
        const AC = window.AudioContext || (window as any).webkitAudioContext;
        const audioContext = new AC();
        audioContextRef.current = audioContext;
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(dataArray);
          const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
          const normalized = Math.min(100, (avg / 128) * 100);
          setMicLevel(normalized);
          animationFrameRef.current = requestAnimationFrame(tick);
        };
        animationFrameRef.current = requestAnimationFrame(tick);
      } catch (e) {
        // Mic level visualization is non-critical
      }

      setDeviceStatus('ready');
    } catch (err: any) {
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        setDeviceStatus('denied');
        setDeviceError('Camera/microphone access was denied. Please allow access in your browser settings and try again.');
      } else if (err?.name === 'NotFoundError' || err?.name === 'DevicesNotFoundError') {
        setDeviceStatus('error');
        setDeviceError('No camera or microphone detected. Please connect a device and try again.');
      } else if (err?.name === 'NotReadableError' || err?.name === 'TrackStartError') {
        setDeviceStatus('error');
        setDeviceError('Camera/microphone is in use by another application. Close other apps and try again.');
      } else {
        setDeviceStatus('error');
        setDeviceError(`Failed to access devices: ${err?.message || 'Unknown error'}`);
      }
    }
  }, []);

  // Attach the stream to the lobby preview video element when on devices step
  useEffect(() => {
    if (lobbyStep !== 'devices') return;
    const video = lobbyVideoRef.current;
    const stream = userMediaStreamRef.current;
    if (!video || !stream) return;
    video.srcObject = stream;
    video.muted = true;
    const onPlaying = () => setCameraLive(true);
    video.addEventListener('playing', onPlaying);
    video.play().catch(() => {});
    return () => {
      video.removeEventListener('playing', onPlaying);
    };
  }, [lobbyStep, deviceStatus]);

  // ─── Screen share (entire screen / monitor only) ─────────────────────────

  const requestScreenShare = useCallback(async () => {
    setScreenStatus('requesting');
    setScreenError(null);

    try {
      const screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: 'monitor' },
        // Non-standard but supported in Chromium/Edge
        monitorTypeSurfaces: 'include',
        selfBrowserSurface: 'exclude',
        surfaceSwitching: 'exclude',
        audio: false,
      } as MediaStreamConstraints);

      const [track] = screenStream.getVideoTracks();
      const settings = track?.getSettings ? track.getSettings() : ({} as MediaTrackSettings);
      const surface = (settings as any).displaySurface;

      if (surface && surface !== 'monitor') {
        try {
          track?.stop();
        } catch {}
        screenStream.getTracks().forEach((t) => t.stop());
        throw new Error('Please share your entire screen, not a single tab or window.');
      }

      // Detect user-stops-sharing → end the interview
      if (track) {
        track.addEventListener('ended', () => {
          if (phase === 'interview') {
            handleEndInterview('Screen sharing was stopped.');
          } else {
            // Reset the lobby state if the share is cancelled before starting
            screenStreamRef.current = null;
            setScreenStatus('idle');
          }
        });
      }

      screenStreamRef.current = screenStream;
      setScreenStatus('ready');
    } catch (err: any) {
      setScreenStatus('error');
      setScreenError(err?.message || 'Failed to capture screen. Please try again.');
    }
  }, [phase, handleEndInterview]);

  // ─── Proctoring snapshot polling (kept identical to before) ──────────────

  const takeAndUploadSnapshot = useCallback(async () => {
    if (!cameraStreamRef.current || !screenStreamRef.current || !currentQuestion?.interviewId) return;

    const takeSnapshot = async (
      stream: MediaStream,
      width: number,
      height: number
    ): Promise<string | null> => {
      const track = stream.getVideoTracks()[0];
      if (!track || track.readyState !== 'live') return null;

      const video = document.createElement('video');
      video.srcObject = stream;
      video.muted = true;
      await video.play().catch(() => {});

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;
      ctx.drawImage(video, 0, 0, width, height);

      video.pause();
      video.srcObject = null;

      return canvas.toDataURL('image/png');
    };

    const cameraBase64 = await takeSnapshot(cameraStreamRef.current, 320, 240);
    const screenBase64 = await takeSnapshot(screenStreamRef.current, 1280, 720);

    if (!cameraBase64 || !screenBase64) return;

    try {
      const token = getAuthToken();
      await fetch(`${API_BASE_URL}/snapshot/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          interview_id: currentQuestion.interviewId,
          client_timestamp: Date.now(),
          camera_image: cameraBase64,
          screen_image: screenBase64,
        }),
      });
    } catch (e) {
      console.error('Snapshot upload error', e);
    }
  }, [currentQuestion?.interviewId]);

  useEffect(() => {
    if (phase !== 'interview' || !currentQuestion?.interviewId) return;

    const poll = async () => {
      try {
        const token = getAuthToken();
        const res = await fetch(
          `${API_BASE_URL}/interview/${currentQuestion.interviewId}/instructions`,
          {
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
          }
        );

        if (!res.ok) return;

        const data = await res.json();

        if (data.terminate) {
          handleEndInterview('Interview terminated by proctoring system.');
          return;
        }

        if (data.take_snapshot) {
          takeAndUploadSnapshot();
        }
      } catch (e) {
        console.error('Polling error', e);
      }
    };

    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [phase, currentQuestion?.interviewId, handleEndInterview, takeAndUploadSnapshot]);

  // ─── Question audio playback ──────────────────────────────────────────────

  const playQuestionAudio = useCallback(
    (blob: Blob | null) => {
      if (!blob) return;

      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioPlayerRef.current = audio;
      audio.muted = isMuted;

      audio.onplay = () => setIsPlayingAudio(true);
      audio.onended = () => {
        setIsPlayingAudio(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setIsPlayingAudio(false);
        URL.revokeObjectURL(url);
      };

      audio.play().catch(() => setIsPlayingAudio(false));
    },
    [isMuted]
  );

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const newVal = !prev;
      if (audioPlayerRef.current) {
        audioPlayerRef.current.muted = newVal;
      }
      return newVal;
    });
  }, []);

  // ─── Start Interview ──────────────────────────────────────────────────────

  const startInterview = useCallback(async () => {
    setIsLoadingQuestion(true);
    setError(null);

    // Streams must already be acquired by the lobby. Bail out if not.
    if (!cameraStreamRef.current || !audioStreamRef.current) {
      setError('Camera/microphone not initialized. Please complete the device check.');
      setIsLoadingQuestion(false);
      return;
    }
    if (!screenStreamRef.current) {
      setError('Screen sharing is required. Please complete the screen share step.');
      setIsLoadingQuestion(false);
      return;
    }

    try {
      const token = getAuthToken();
      const response = await fetch(`${API_BASE_URL}/interview/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ application_id: applicationId }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const interviewId = response.headers.get('X-Interview-Id') || '';
      const questionText = response.headers.get('X-Question-Text') || '';
      const questionSequence = parseInt(response.headers.get('X-Question-Sequence') || '1', 10);
      const category = response.headers.get('X-Question-Category') || undefined;
      const totalHeader: string | null = response.headers.get('X-Total-Questions');
      const fixedHeader: string | null = response.headers.get('X-Fixed-Question-Count');
      if (totalHeader) {
        const n = parseInt(totalHeader, 10);
        if (Number.isFinite(n)) setTotalQuestions(n);
      }
      if (fixedHeader !== null) {
        setIsFixedCount(fixedHeader === 'true');
      }
      const audioBlob = await response.blob();

      const qData: QuestionData = {
        interviewId,
        questionText,
        questionSequence,
        audioBlob,
        category,
      };

      setCurrentQuestion(qData);
      setQuestionCount(questionSequence);
      setPhase('interview');
      setRecordedBlob(null);

      setTimeout(() => {
        playQuestionAudio(audioBlob);
        startTimer();
      }, 500);
    } catch (err: any) {
      setError(err.message || 'Failed to start interview');
    } finally {
      setIsLoadingQuestion(false);
    }
  }, [applicationId, playQuestionAudio, startTimer]);

  // ─── Recording ────────────────────────────────────────────────────────────

  const startRecording = useCallback(async () => {
    try {
      const stream = audioStreamRef.current;
      if (!stream || stream.getTracks().some((t) => t.readyState === 'ended')) {
        // The lobby is responsible for acquiring camera+mic. If the audio track
        // has ended by the time we try to record, surface an error instead of
        // silently re-prompting the user for permissions mid-interview.
        console.error('Audio stream unavailable or ended in startRecording');
        setError('Microphone is unavailable. Please refresh and complete the device check again.');
        return;
      }

      chunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm',
      });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setRecordedBlob(blob);
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setRecordedBlob(null);
    } catch {
      setError('Failed to start recording. Check microphone permissions.');
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  // ─── Submit Response & Get Next Question ─────────────────────────────────

  const submitAndGetNext = useCallback(async () => {
    if (!currentQuestion || !recordedBlob) return;

    setIsSubmitting(true);
    setError(null);
    stopTimer();

    try {
      const token = getAuthToken();
      const formData = new FormData();
      formData.append('interview_id', currentQuestion.interviewId);
      formData.append('question', currentQuestion.questionText);
      formData.append('response_audio', recordedBlob, 'response.webm');

      const response = await fetch(`${API_BASE_URL}/interview/evaluateAndGenerate`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const contentType = response.headers.get('content-type') || '';

      if (contentType.includes('application/json')) {
        const data = await response.json();
        if (data.is_interview_ended) {
          handleEndInterview(data.reason || 'Interview completed.');
          return;
        }
      }

      const interviewEnded = response.headers.get('X-Interview-Ended') === 'true';

      const interviewId = response.headers.get('X-Interview-Id') || currentQuestion.interviewId;
      const questionText = response.headers.get('X-Question-Text') || '';
      const questionSequence = parseInt(response.headers.get('X-Question-Sequence') || '1', 10);
      const category = response.headers.get('X-Question-Category') || undefined;
      const totalHeader: string | null = response.headers.get('X-Total-Questions');
      const fixedHeader: string | null = response.headers.get('X-Fixed-Question-Count');
      if (totalHeader) {
        const n = parseInt(totalHeader, 10);
        if (Number.isFinite(n)) setTotalQuestions(n);
      }
      if (fixedHeader !== null) {
        setIsFixedCount(fixedHeader === 'true');
      }
      const audioBlob = await response.blob();

      if (interviewEnded) {
        handleEndInterview('All questions answered. Interview completed.');
        return;
      }

      const qData: QuestionData = {
        interviewId,
        questionText,
        questionSequence,
        audioBlob,
        category,
      };

      setCurrentQuestion(qData);
      setQuestionCount(questionSequence);
      setRecordedBlob(null);

      setTimeout(() => {
        playQuestionAudio(audioBlob);
        startTimer();
      }, 500);
    } catch (err: any) {
      setError(err.message || 'Failed to submit response');
    } finally {
      setIsSubmitting(false);
    }
  }, [currentQuestion, recordedBlob, playQuestionAudio, startTimer, stopTimer, handleEndInterview]);

  // ─── Cleanup ──────────────────────────────────────────────────────────────

  useEffect(() => {
    const lobbyVideoEl = lobbyVideoRef.current;
    return () => {
      if (lobbyVideoEl) {
        lobbyVideoEl.srcObject = null;
      }
      stopAllMedia();
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, [stopAllMedia]);

  // ─── Lobby Render ─────────────────────────────────────────────────────────

  const renderLobby = () => {
    const steps: LobbyStep[] = ['instructions', 'devices', 'screenshare', 'ready'];
    const currentStepIndex = steps.indexOf(lobbyStep);

    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-2xl space-y-6">
          {/* Header */}
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold text-foreground">AI Interview</h1>
            <p className="text-muted-foreground mt-1">Please complete the setup before starting</p>
          </div>

          {/* Progress Steps */}
          <div className="flex items-center justify-center gap-2">
            {steps.map((step, i) => (
              <div key={step} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                    i < currentStepIndex
                      ? 'bg-success text-white'
                      : i === currentStepIndex
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted/30 text-muted-foreground'
                  }`}
                >
                  {i < currentStepIndex ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
                </div>
                {i < steps.length - 1 && (
                  <div className={`w-12 h-0.5 ${i < currentStepIndex ? 'bg-success' : 'bg-muted/30'}`} />
                )}
              </div>
            ))}
          </div>

          {/* Step 1: Instructions & proctoring consent */}
          {lobbyStep === 'instructions' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <HelpCircle className="w-5 h-5 text-primary" />
                  Interview & Proctoring Instructions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground text-sm">
                  Please read these guidelines carefully before continuing. The rules below are in
                  place to ensure a fair and secure interview.
                </p>

                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Monitor className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">AI-Powered Interview</p>
                      <p className="text-sm text-muted-foreground">
                        You will be asked questions by our AI interviewer. Each question is played
                        as audio. Listen carefully and respond clearly.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Clock className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">3 Minutes Per Question</p>
                      <p className="text-sm text-muted-foreground">
                        You have 3 minutes to answer each question. The interview ends automatically
                        if time runs out.{totalQuestions ? ` There are up to ${totalQuestions} questions.` : ''}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Headphones className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Camera, Microphone & Screen Share</p>
                      <p className="text-sm text-muted-foreground">
                        We require access to your camera, microphone, and an entire-screen share
                        for proctoring. All three must remain active for the whole interview.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <UserCheck className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">One Person Only</p>
                      <p className="text-sm text-muted-foreground">
                        Only you should be visible in the camera frame. Ensure no other person is
                        present in the background.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <MonitorOff className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Do Not Leave Full Screen</p>
                      <p className="text-sm text-muted-foreground">
                        Do not switch tabs, exit full screen, or stop screen sharing during the
                        interview. Doing so may end the session immediately.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Sun className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Proper Lighting</p>
                      <p className="text-sm text-muted-foreground">
                        Make sure your face is well lit and clearly visible. Avoid backlighting or
                        very dark environments.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Camera className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Periodic Snapshots</p>
                      <p className="text-sm text-muted-foreground">
                        Snapshots of your camera feed and screen will be taken periodically and
                        reviewed by recruiters as part of the proctoring process.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-warning/10 border border-yellow-500/20">
                    <AlertTriangle className="w-5 h-5 text-warning-foreground mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Suspicious Activity Warning</p>
                      <p className="text-sm text-muted-foreground">
                        Any suspicious behavior — using notes, having someone else present, or
                        using unauthorized tools — may lead to immediate cancellation of your
                        interview.
                      </p>
                    </div>
                  </div>
                </div>

                <Button className="w-full" size="lg" onClick={() => setLobbyStep('devices')}>
                  I Understand and Agree
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Step 2: Device check (single getUserMedia) */}
          {lobbyStep === 'devices' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Video className="w-5 h-5 text-primary" />
                  Device Check
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground text-sm">
                  We need access to your camera and microphone. Make sure your face is clearly
                  visible and speak briefly to confirm the mic is working.
                </p>

                {deviceStatus === 'idle' && (
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                      <Camera className="w-10 h-10 text-primary" />
                    </div>
                    <Button size="lg" onClick={requestDevices}>
                      Allow Camera & Microphone
                    </Button>
                  </div>
                )}

                {deviceStatus === 'requesting' && (
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                      <Loader2 className="w-10 h-10 text-primary animate-spin" />
                    </div>
                    <p className="text-muted-foreground font-medium">Requesting access…</p>
                    <p className="text-sm text-muted-foreground">
                      Please allow the permission in the browser popup.
                    </p>
                  </div>
                )}

                {deviceStatus === 'ready' && (
                  <div className="space-y-4">
                    <div className="relative rounded-lg overflow-hidden bg-black/90 aspect-video max-w-md mx-auto border border-border">
                      <video
                        ref={lobbyVideoRef}
                        autoPlay
                        muted
                        playsInline
                        className="w-full h-full object-cover"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div
                        className={`flex items-center gap-2 p-3 rounded-lg border ${
                          cameraLive
                            ? 'bg-success/10 border-green-500/20 text-success'
                            : 'bg-muted/10 border-border text-muted-foreground'
                        }`}
                      >
                        {cameraLive ? <CheckCircle2 className="w-5 h-5" /> : <Loader2 className="w-5 h-5 animate-spin" />}
                        <span className="text-sm font-medium">
                          {cameraLive ? 'Camera detected' : 'Detecting camera…'}
                        </span>
                      </div>
                      <div
                        className={`flex items-center gap-2 p-3 rounded-lg border ${
                          micLive
                            ? 'bg-success/10 border-green-500/20 text-success'
                            : 'bg-muted/10 border-border text-muted-foreground'
                        }`}
                      >
                        {micLive ? <CheckCircle2 className="w-5 h-5" /> : <Loader2 className="w-5 h-5 animate-spin" />}
                        <span className="text-sm font-medium">
                          {micLive ? 'Microphone detected' : 'Detecting microphone…'}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Microphone Level</span>
                        <span className="text-muted-foreground">{Math.round(micLevel)}%</span>
                      </div>
                      <Progress value={micLevel} className="h-3" />
                      <p className="text-xs text-muted-foreground">
                        Speak briefly — the bar should move when you talk.
                      </p>
                    </div>

                    <Button
                      className="w-full"
                      size="lg"
                      onClick={() => setLobbyStep('screenshare')}
                      disabled={!cameraLive || !micLive}
                    >
                      Continue
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                )}

                {(deviceStatus === 'denied' || deviceStatus === 'error') && (
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 rounded-full bg-destructive/10 flex items-center justify-center mx-auto">
                      {deviceStatus === 'denied' ? (
                        <CameraOff className="w-10 h-10 text-destructive" />
                      ) : (
                        <XCircle className="w-10 h-10 text-destructive" />
                      )}
                    </div>
                    <p className="text-destructive font-medium">
                      {deviceStatus === 'denied' ? 'Permission denied' : 'Device error'}
                    </p>
                    {deviceError && <p className="text-sm text-muted-foreground">{deviceError}</p>}
                    <Button variant="outline" onClick={requestDevices}>
                      Try Again
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Step 3: Screen share (entire screen / monitor only) */}
          {lobbyStep === 'screenshare' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ScreenShare className="w-5 h-5 text-primary" />
                  Share Your Entire Screen
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground text-sm">
                  We will record your entire screen for proctoring. When the browser prompts you,
                  please share your <strong>entire screen</strong> — not a single tab or window.
                  Sharing only a tab or window will not be accepted.
                </p>

                {screenStatus !== 'ready' && (
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                      {screenStatus === 'requesting' ? (
                        <Loader2 className="w-10 h-10 text-primary animate-spin" />
                      ) : (
                        <ScreenShare className="w-10 h-10 text-primary" />
                      )}
                    </div>
                    <Button size="lg" onClick={requestScreenShare} disabled={screenStatus === 'requesting'}>
                      {screenStatus === 'requesting' ? 'Requesting…' : 'Share Screen'}
                    </Button>
                  </div>
                )}

                {screenStatus === 'ready' && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-success/10 border border-green-500/20">
                    <CheckCircle2 className="w-5 h-5 text-success" />
                    <p className="text-success font-medium">Entire screen is being shared.</p>
                  </div>
                )}

                {screenStatus === 'error' && screenError && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-red-500/20">
                    <XCircle className="w-5 h-5 text-destructive flex-shrink-0" />
                    <p className="text-destructive text-sm">{screenError}</p>
                  </div>
                )}

                <Button
                  className="w-full"
                  size="lg"
                  onClick={() => setLobbyStep('ready')}
                  disabled={screenStatus !== 'ready'}
                >
                  Continue
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Step 4: Ready */}
          {lobbyStep === 'ready' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-success">
                  <CheckCircle2 className="w-5 h-5" />
                  Ready to Begin
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-success" />
                    <span>Camera ✓</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-success" />
                    <span>Microphone ✓</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-success" />
                    <span>Entire-screen share ✓</span>
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                  <p className="text-sm text-muted-foreground">
                    When you click &quot;Start Interview&quot;, the AI will ask your first question.
                    Audio plays automatically. You have 3 minutes per question. Record your response and submit.
                  </p>
                </div>

                <Button
                  className="w-full"
                  size="lg"
                  onClick={startInterview}
                  disabled={isLoadingQuestion}
                >
                  {isLoadingQuestion ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Starting Interview...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Start Interview
                    </>
                  )}
                </Button>

                {error && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-red-500/20">
                    <XCircle className="w-5 h-5 text-destructive flex-shrink-0" />
                    <p className="text-destructive text-sm">{error}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    );
  };

  // ─── Interview Render (Meeting UI) ───────────────────────────────────────

  const renderInterview = () => {
    if (!currentQuestion) return null;

    const timerPercent = (timeRemaining / QUESTION_TIMER_SECONDS) * 100;
    const isTimerCritical = timeRemaining <= 30;
    const candidateLabel = user?.name ? user.name.split(' ')[0] : 'You';

    return (
      <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 relative">
        {/* Subtle dotted background */}
        <div
          className="absolute inset-0 opacity-[0.06] pointer-events-none"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.6) 1px, transparent 0)',
            backgroundSize: '40px 40px',
          }}
        />

        {/* Top bar */}
        <header className="relative z-10 w-full px-4 sm:px-8 py-4 flex items-center justify-between border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" />
            <span className="text-sm font-medium text-slate-200">AI Interview in Progress</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <Badge
              variant="outline"
              className="text-xs sm:text-sm px-3 py-1 border-white/15 bg-white/5 text-slate-200"
            >
              {isFixedCount === false
                ? `Question ${questionCount}`
                : `Question ${questionCount}${totalQuestions ? ` of ${totalQuestions}` : ''}`}
            </Badge>
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5">
              <Clock
                className={`w-4 h-4 ${isTimerCritical ? 'text-destructive' : 'text-slate-300'}`}
              />
              <span
                className={`text-sm font-mono ${
                  isTimerCritical ? 'text-destructive animate-pulse' : 'text-slate-200'
                }`}
              >
                {formatTime(timeRemaining)}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleMute}
              className="text-slate-300 hover:text-white hover:bg-white/10"
              aria-label={isMuted ? 'Unmute interviewer' : 'Mute interviewer'}
            >
              {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
            </Button>
          </div>
        </header>

        {/* Timer bar */}
        <div className="relative z-10 w-full px-4 sm:px-8 pt-3">
          <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-linear ${
                isTimerCritical ? 'bg-destructive' : 'bg-primary'
              }`}
              style={{ width: `${timerPercent}%` }}
            />
          </div>
        </div>

        {/* Main stage — two large circular tiles */}
        <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 py-8 gap-8">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-8 sm:gap-12 lg:gap-20">
            {/* AI Interviewer */}
            <div className="flex flex-col items-center gap-4">
              <div className="relative">
                {isPlayingAudio && (
                  <>
                    <span className="absolute inset-0 rounded-full ring-4 ring-primary/40 animate-ping" />
                    <span
                      className="absolute inset-0 rounded-full ring-2 ring-primary/30 animate-ping"
                      style={{ animationDelay: '0.4s' }}
                    />
                  </>
                )}
                <div
                  className={`relative w-56 h-56 md:w-64 md:h-64 lg:w-72 lg:h-72 rounded-full flex items-center justify-center transition-all duration-300 bg-brand-gradient shadow-2xl ${
                    isPlayingAudio ? 'ring-4 ring-primary/60 shadow-primary/30' : 'ring-2 ring-white/10'
                  }`}
                >
                  <Sparkles className="w-24 h-24 md:w-28 md:h-28 lg:w-32 lg:h-32 text-white" />
                </div>
              </div>
              <div className="flex flex-col items-center gap-1">
                <span className="text-sm sm:text-base font-medium text-slate-100">AI Interviewer</span>
                {isPlayingAudio && (
                  <span className="text-xs text-primary font-medium animate-pulse">Speaking…</span>
                )}
              </div>
            </div>

            {/* Candidate camera */}
            <div className="flex flex-col items-center gap-4">
              <div className="relative">
                {isRecording && (
                  <>
                    <span className="absolute inset-0 rounded-full ring-4 ring-destructive/40 animate-ping" />
                    <span
                      className="absolute inset-0 rounded-full ring-2 ring-destructive/30 animate-ping"
                      style={{ animationDelay: '0.4s' }}
                    />
                  </>
                )}
                <div
                  className={`relative w-56 h-56 md:w-64 md:h-64 lg:w-72 lg:h-72 rounded-full overflow-hidden bg-slate-800 shadow-2xl transition-all duration-300 ${
                    isRecording
                      ? 'ring-4 ring-destructive/60 shadow-destructive/30'
                      : 'ring-2 ring-white/10'
                  }`}
                >
                  <video
                    ref={(el) => {
                      if (el && cameraStreamRef.current && el.srcObject !== cameraStreamRef.current) {
                        el.srcObject = cameraStreamRef.current;
                      }
                    }}
                    autoPlay
                    muted
                    playsInline
                    className="w-full h-full object-cover scale-x-[-1]"
                  />
                </div>
              </div>
              <div className="flex flex-col items-center gap-1">
                <span className="text-sm sm:text-base font-medium text-slate-100 max-w-[14rem] truncate">
                  {candidateLabel}
                </span>
                {isRecording && (
                  <span className="text-xs text-destructive font-medium animate-pulse">Recording…</span>
                )}
              </div>
            </div>
          </div>

          {/* Question card */}
          <Card className="w-full max-w-3xl bg-white/5 backdrop-blur border-white/10 text-slate-100 shadow-xl">
            <CardContent className="p-5 sm:p-6 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="bg-primary/15 text-primary border border-primary/30 hover:bg-primary/15">
                  {isFixedCount === false
                    ? `Q ${currentQuestion.questionSequence}`
                    : `Q ${currentQuestion.questionSequence}${totalQuestions ? `/${totalQuestions}` : ''}`}
                </Badge>
                {currentQuestion.category && (
                  <Badge
                    variant="outline"
                    className="border-white/15 bg-white/5 text-slate-200 capitalize"
                  >
                    {currentQuestion.category}
                  </Badge>
                )}
                <span className="ml-auto text-xs text-slate-400 sm:hidden">
                  {formatTime(timeRemaining)}
                </span>
              </div>
              <p className="text-base sm:text-lg leading-relaxed text-slate-100">
                {currentQuestion.questionText}
              </p>
            </CardContent>
          </Card>

          {error && (
            <div className="w-full max-w-3xl flex items-center gap-2 p-3 rounded-lg bg-destructive/15 border border-destructive/30">
              <XCircle className="w-5 h-5 text-destructive flex-shrink-0" />
              <p className="text-destructive text-sm">{error}</p>
            </div>
          )}
        </main>

        {/* Bottom action bar */}
        <footer className="sticky bottom-0 z-20 w-full border-t border-white/5 bg-slate-950/80 backdrop-blur px-4 sm:px-8 py-4">
          <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Primary controls (centered) */}
            <div className="flex-1 flex items-center justify-center gap-3 order-2 sm:order-1">
              {!isRecording && !recordedBlob && (
                <Button
                  size="lg"
                  onClick={startRecording}
                  disabled={isSubmitting}
                  className="gap-2 rounded-full px-6 h-12 bg-primary hover:bg-primary/90 text-primary-foreground"
                >
                  <Mic className="w-5 h-5" />
                  Record Answer
                </Button>
              )}

              {isRecording && (
                <Button
                  size="lg"
                  variant="destructive"
                  onClick={stopRecording}
                  className="gap-2 rounded-full px-6 h-12"
                >
                  <Square className="w-5 h-5" />
                  Stop Recording
                </Button>
              )}

              {recordedBlob && !isRecording && (
                <>
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() => setRecordedBlob(null)}
                    disabled={isSubmitting}
                    className="gap-2 rounded-full px-5 h-12 border-white/15 bg-white/5 text-slate-100 hover:bg-white/10 hover:text-white"
                  >
                    <MicOff className="w-4 h-4" />
                    Re-record
                  </Button>
                  <Button
                    size="lg"
                    onClick={submitAndGetNext}
                    disabled={isSubmitting}
                    className="gap-2 rounded-full px-6 h-12 bg-primary hover:bg-primary/90 text-primary-foreground"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Submitting…
                      </>
                    ) : (
                      <>
                        <ArrowRight className="w-4 h-4" />
                        Submit & Next
                      </>
                    )}
                  </Button>
                </>
              )}
            </div>

            {/* End interview (kept apart) */}
            <div className="order-1 sm:order-2 sm:ml-6">
              <Button
                variant="destructive"
                size="lg"
                onClick={() => setEndDialogOpen(true)}
                className="gap-2 rounded-full px-5 h-12"
              >
                <PhoneOff className="w-4 h-4" />
                End Interview
              </Button>
            </div>
          </div>
        </footer>

        <AlertDialog open={endDialogOpen} onOpenChange={(open) => !isEndingInterview && setEndDialogOpen(open)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>End interview?</AlertDialogTitle>
              <AlertDialogDescription>
                This cannot be undone. Your answers so far will be saved and submitted for evaluation.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isEndingInterview}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault();
                  confirmEndInterview();
                }}
                disabled={isEndingInterview}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {isEndingInterview ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Ending…
                  </>
                ) : (
                  'End Interview'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  };

  // ─── Finished Render ──────────────────────────────────────────────────────

  const renderFinished = () => {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-4">
        <div className="w-full max-w-lg text-center space-y-8">
          <div className="relative mx-auto w-28 h-28">
            <div className="absolute inset-0 rounded-full bg-success/10 animate-pulse" />
            <div className="relative w-28 h-28 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-green-500/20">
              <CheckCircle2 className="w-14 h-14 text-white" />
            </div>
          </div>

          <div className="space-y-3">
            <h1 className="text-3xl font-bold text-white">Interview Complete</h1>
            <p className="text-slate-400 text-lg">{endReason}</p>
            <p className="text-slate-500 text-sm">
              You answered {questionCount} question{questionCount !== 1 ? 's' : ''}.
              Your responses are being processed.
            </p>
          </div>

          <div className="space-y-3">
            <Button
              size="lg"
              className="w-full bg-destructive hover:bg-red-600 text-white rounded-xl h-14 text-base gap-2"
              onClick={async () => {
                await callEndInterviewAPI();
                window.close();
              }}
            >
              <PhoneOff className="w-5 h-5" />
              End Interview & Close
            </Button>

            <p className="text-xs text-slate-600">
              This will close the interview tab. Your results will be available shortly.
            </p>
          </div>
        </div>
      </div>
    );
  };

  // ─── Main Render ──────────────────────────────────────────────────────────

  if (phase === 'lobby') return renderLobby();
  if (phase === 'interview') return renderInterview();
  if (phase === 'finished') return renderFinished();

  return null;
}
