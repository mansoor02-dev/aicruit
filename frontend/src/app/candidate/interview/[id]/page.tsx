'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
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
  Shield,
  Monitor,
  Headphones,
  HelpCircle,
  User,
  Clock,
  PhoneOff,
} from 'lucide-react';
import { getAuthToken } from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const QUESTION_TIMER_SECONDS = 180; // 3 minutes per question
const MAX_QUESTIONS = 10;

// ─── Types ────────────────────────────────────────────────────────────────────

type InterviewPhase = 'lobby' | 'interview' | 'finished';
type LobbyStep = 'instructions' | 'permissions' | 'mictest' | 'ready';

interface QuestionData {
  interviewId: string;
  questionText: string;
  questionSequence: number;
  audioBlob: Blob | null;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function InterviewPage() {
  const params = useParams();
  const applicationId = params.id as string;

  // Phase management
  const [phase, setPhase] = useState<InterviewPhase>('lobby');
  const [lobbyStep, setLobbyStep] = useState<LobbyStep>('instructions');

  // Permissions & mic test
  const [micPermission, setMicPermission] = useState<'pending' | 'granted' | 'denied'>('pending');
  const [isMicTesting, setIsMicTesting] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [micTestPassed, setMicTestPassed] = useState(false);

  // Interview state
  const [currentQuestion, setCurrentQuestion] = useState<QuestionData | null>(null);
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

  // Timer state
  const [timeRemaining, setTimeRemaining] = useState(QUESTION_TIMER_SECONDS);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Refs
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // ─── Timer ──────────────────────────────────────────────────────────────

  const startTimer = useCallback(() => {
    // Clear any existing timer
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
    }
    setTimeRemaining(QUESTION_TIMER_SECONDS);

    timerIntervalRef.current = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          // Timer expired — end interview
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

  // When timer hits 0, end the interview
  useEffect(() => {
    if (timeRemaining === 0 && phase === 'interview' && currentQuestion) {
      stopTimer();
      handleEndInterview('Time expired for the question.');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRemaining, phase]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // ─── End Interview ──────────────────────────────────────────────────────

  const handleEndInterview = useCallback(
    async (reason: string = 'Interview completed.') => {
      stopTimer();
      setEndReason(reason);
      setIsInterviewEnded(true);
      setPhase('finished');

      // Stop recording if active
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);

      // Stop audio
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
    },
    [stopTimer]
  );

  const callEndInterviewAPI = useCallback(async () => {
    if (!currentQuestion?.interviewId) return;

    try {
      const token = getAuthToken();
      const formData = new FormData();
      formData.append('interview_id', currentQuestion.interviewId);

      await fetch(`${API_BASE_URL}/interview/end`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });
    } catch {
      // Silently fail — interview is already ended on UI
    }
  }, [currentQuestion]);

  // ─── Mic Permission ───────────────────────────────────────────────────

  const requestMicPermission = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      setMicPermission('granted');

      // Set up analyser for mic level visualization
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
    } catch {
      setMicPermission('denied');
    }
  }, []);

  // ─── Mic Test ─────────────────────────────────────────────────────────

  const startMicTest = useCallback(() => {
    if (!analyserRef.current) return;
    setIsMicTesting(true);
    setMicTestPassed(false);

    const analyser = analyserRef.current;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let maxLevel = 0;
    const testStartTime = Date.now();

    const checkLevel = () => {
      analyser.getByteFrequencyData(dataArray);
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      const normalizedLevel = Math.min(100, (avg / 128) * 100);
      setMicLevel(normalizedLevel);

      if (normalizedLevel > maxLevel) maxLevel = normalizedLevel;

      if (maxLevel > 15) {
        setMicTestPassed(true);
      }

      if (Date.now() - testStartTime > 5000) {
        setIsMicTesting(false);
        if (maxLevel > 15) setMicTestPassed(true);
        return;
      }

      animationFrameRef.current = requestAnimationFrame(checkLevel);
    };

    animationFrameRef.current = requestAnimationFrame(checkLevel);
  }, []);

  const stopMicTest = useCallback(() => {
    setIsMicTesting(false);
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
  }, []);

  // ─── Play Question Audio (auto-play) ──────────────────────────────────

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

  // Toggle mute
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const newVal = !prev;
      if (audioPlayerRef.current) {
        audioPlayerRef.current.muted = newVal;
      }
      return newVal;
    });
  }, []);

  // ─── Start Interview (call /interview/start) ──────────────────────────

  const startInterview = useCallback(async () => {
    setIsLoadingQuestion(true);
    setError(null);

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
      const audioBlob = await response.blob();

      const qData: QuestionData = {
        interviewId,
        questionText,
        questionSequence,
        audioBlob,
      };

      setCurrentQuestion(qData);
      setQuestionCount(questionSequence);
      setPhase('interview');
      setRecordedBlob(null);

      // Auto-play audio and start timer
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

  // ─── Recording ────────────────────────────────────────────────────────

  const startRecording = useCallback(async () => {
    try {
      let stream = audioStreamRef.current;
      if (!stream || stream.getTracks().some((t) => t.readyState === 'ended')) {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioStreamRef.current = stream;
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

  // ─── Submit Response & Get Next Question ──────────────────────────────

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

      // Check if this is a JSON response (interview ended)
      const contentType = response.headers.get('content-type') || '';

      if (contentType.includes('application/json')) {
        // Interview ended — JSON response
        const data = await response.json();
        if (data.is_interview_ended) {
          handleEndInterview(data.reason || 'Interview completed.');
          return;
        }
      }

      // Check X-Interview-Ended header for audio responses
      const interviewEnded = response.headers.get('X-Interview-Ended') === 'true';

      // Parse next question from response
      const interviewId = response.headers.get('X-Interview-Id') || currentQuestion.interviewId;
      const questionText = response.headers.get('X-Question-Text') || '';
      const questionSequence = parseInt(response.headers.get('X-Question-Sequence') || '1', 10);
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
      };

      setCurrentQuestion(qData);
      setQuestionCount(questionSequence);
      setRecordedBlob(null);

      // Auto-play audio and restart timer
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

  // ─── Cleanup ──────────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      stopTimer();
    };
  }, [stopTimer]);

  // ─── Lobby Render ─────────────────────────────────────────────────────

  const renderLobby = () => {
    const steps: LobbyStep[] = ['instructions', 'permissions', 'mictest', 'ready'];
    const currentStepIndex = steps.indexOf(lobbyStep);

    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-2xl space-y-6">
          {/* Header */}
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold text-foreground">AI Interview</h1>
            <p className="text-muted-foreground">Please complete the setup before starting</p>
          </div>

          {/* Progress Steps */}
          <div className="flex items-center justify-center gap-2">
            {steps.map((step, i) => (
              <div key={step} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                    i < currentStepIndex
                      ? 'bg-green-500 text-white'
                      : i === currentStepIndex
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted/30 text-muted-foreground'
                  }`}
                >
                  {i < currentStepIndex ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
                </div>
                {i < steps.length - 1 && (
                  <div className={`w-12 h-0.5 ${i < currentStepIndex ? 'bg-green-500' : 'bg-muted/30'}`} />
                )}
              </div>
            ))}
          </div>

          {/* Step Content */}
          {lobbyStep === 'instructions' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <HelpCircle className="w-5 h-5 text-primary" />
                  Interview Instructions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Monitor className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">AI-Powered Interview</p>
                      <p className="text-sm text-muted-foreground">
                        You will be asked questions by our AI interviewer. Each question will be
                        played as audio. Listen carefully and respond clearly.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Clock className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">3 Minutes Per Question</p>
                      <p className="text-sm text-muted-foreground">
                        You have 3 minutes to answer each question. The interview will end
                        automatically if time runs out. There are up to {MAX_QUESTIONS} questions.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Headphones className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Audio Required</p>
                      <p className="text-sm text-muted-foreground">
                        Ensure you are in a quiet environment with a working microphone.
                        Use headphones for the best experience.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
                    <Shield className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Fair Assessment</p>
                      <p className="text-sm text-muted-foreground">
                        Answer honestly and to the best of your ability. The AI will evaluate
                        your responses and adapt follow-up questions accordingly.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                    <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-foreground">Important</p>
                      <p className="text-sm text-muted-foreground">
                        Do not refresh or close this tab during the interview. Ensure your
                        internet connection is stable.
                      </p>
                    </div>
                  </div>
                </div>

                <Button className="w-full" size="lg" onClick={() => setLobbyStep('permissions')}>
                  Continue
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          )}

          {lobbyStep === 'permissions' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="w-5 h-5 text-primary" />
                  Microphone Permission
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                  We need access to your microphone to record your responses during the interview.
                </p>

                {micPermission === 'pending' && (
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                      <Mic className="w-10 h-10 text-primary" />
                    </div>
                    <Button size="lg" onClick={requestMicPermission}>
                      Allow Microphone Access
                    </Button>
                  </div>
                )}

                {micPermission === 'granted' && (
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center mx-auto">
                      <CheckCircle2 className="w-10 h-10 text-green-500" />
                    </div>
                    <p className="text-green-500 font-medium">Microphone access granted!</p>
                    <Button className="w-full" size="lg" onClick={() => setLobbyStep('mictest')}>
                      Continue to Mic Test
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                )}

                {micPermission === 'denied' && (
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center mx-auto">
                      <XCircle className="w-10 h-10 text-red-500" />
                    </div>
                    <p className="text-red-500 font-medium">Microphone access denied</p>
                    <p className="text-sm text-muted-foreground">
                      Please allow microphone access in your browser settings and reload the page.
                    </p>
                    <Button variant="outline" onClick={requestMicPermission}>
                      Try Again
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {lobbyStep === 'mictest' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Headphones className="w-5 h-5 text-primary" />
                  Microphone Test
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                  Click the button below and speak into your microphone to test it.
                </p>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Microphone Level</span>
                    <span className="text-muted-foreground">{Math.round(micLevel)}%</span>
                  </div>
                  <Progress value={micLevel} className="h-3" />
                </div>

                <div className="flex items-end justify-center gap-1 h-16">
                  {Array.from({ length: 20 }).map((_, i) => (
                    <div
                      key={i}
                      className="w-2 rounded-t transition-all duration-75"
                      style={{
                        height: `${Math.max(4, (micLevel / 100) * (Math.random() * 64 + (isMicTesting ? 8 : 4)))}px`,
                        backgroundColor: micLevel > 15 ? 'hsl(var(--primary))' : 'hsl(var(--muted))',
                        opacity: isMicTesting ? 1 : 0.3,
                      }}
                    />
                  ))}
                </div>

                <div className="flex gap-3 justify-center">
                  {!isMicTesting ? (
                    <Button size="lg" onClick={startMicTest}>
                      <Mic className="w-4 h-4 mr-2" />
                      Start Test
                    </Button>
                  ) : (
                    <Button size="lg" variant="destructive" onClick={stopMicTest}>
                      <Square className="w-4 h-4 mr-2" />
                      Stop Test
                    </Button>
                  )}
                </div>

                {micTestPassed && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                    <CheckCircle2 className="w-5 h-5 text-green-500" />
                    <p className="text-green-500 font-medium">Microphone is working correctly!</p>
                  </div>
                )}

                <Button
                  className="w-full"
                  size="lg"
                  onClick={() => setLobbyStep('ready')}
                  disabled={!micTestPassed}
                >
                  Continue
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          )}

          {lobbyStep === 'ready' && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-green-500">
                  <CheckCircle2 className="w-5 h-5" />
                  Ready to Begin
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span>Instructions reviewed</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span>Microphone permission granted</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span>Microphone tested and working</span>
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
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                    <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                    <p className="text-red-500 text-sm">{error}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    );
  };

  // ─── Interview Render (Call-style UI) ──────────────────────────────────

  const renderInterview = () => {
    if (!currentQuestion) return null;

    const timerPercent = (timeRemaining / QUESTION_TIMER_SECONDS) * 100;
    const isTimerCritical = timeRemaining <= 30;

    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 flex flex-col items-center justify-between p-4 relative overflow-hidden">
        {/* Subtle grid background */}
        <div
          className="absolute inset-0 opacity-5"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.15) 1px, transparent 0)`,
            backgroundSize: '40px 40px',
          }}
        />

        {/* Header bar */}
        <div className="w-full max-w-3xl flex items-center justify-between z-10 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-sm font-medium text-slate-300">AI Interview in Progress</span>
          </div>
          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className="text-sm px-3 py-1 border-slate-700 text-slate-300"
            >
              {questionCount} / {MAX_QUESTIONS}
            </Badge>

            {/* Mute/Unmute Button */}
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleMute}
              className="text-slate-400 hover:text-white hover:bg-slate-800"
            >
              {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
            </Button>
          </div>
        </div>

        {/* Timer Bar */}
        <div className="w-full max-w-3xl z-10 mb-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Clock className={`w-4 h-4 ${isTimerCritical ? 'text-red-400' : 'text-slate-400'}`} />
              <span
                className={`text-sm font-mono font-bold ${
                  isTimerCritical ? 'text-red-400 animate-pulse' : 'text-slate-300'
                }`}
              >
                {formatTime(timeRemaining)}
              </span>
            </div>
            <span className="text-xs text-slate-500">Time remaining</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-linear ${
                isTimerCritical
                  ? 'bg-gradient-to-r from-red-500 to-red-400'
                  : 'bg-gradient-to-r from-blue-500 to-cyan-400'
              }`}
              style={{ width: `${timerPercent}%` }}
            />
          </div>
        </div>

        {/* Center — AI Avatar with Ripple */}
        <div className="flex-1 flex flex-col items-center justify-center z-10 gap-6">
          <div className="relative">
            {/* Ripple rings when audio is playing */}
            {isPlayingAudio && (
              <>
                <div className="absolute inset-0 w-40 h-40 -m-4 rounded-full border-2 border-blue-400/30 animate-ping" />
                <div
                  className="absolute inset-0 w-40 h-40 -m-4 rounded-full border-2 border-cyan-400/20 animate-ping"
                  style={{ animationDelay: '0.3s' }}
                />
                <div
                  className="absolute inset-0 w-40 h-40 -m-4 rounded-full border-2 border-blue-300/10 animate-ping"
                  style={{ animationDelay: '0.6s' }}
                />
              </>
            )}

            {/* Glow behind avatar */}
            <div
              className={`absolute inset-0 w-32 h-32 rounded-full blur-xl transition-opacity duration-500 ${
                isPlayingAudio ? 'opacity-60' : 'opacity-20'
              }`}
              style={{
                background: 'radial-gradient(circle, rgba(59,130,246,0.5) 0%, transparent 70%)',
              }}
            />

            {/* Avatar circle */}
            <div
              className={`relative w-32 h-32 rounded-full flex items-center justify-center transition-all duration-300 ${
                isPlayingAudio
                  ? 'bg-gradient-to-br from-blue-500 to-cyan-500 shadow-lg shadow-blue-500/30'
                  : 'bg-gradient-to-br from-slate-700 to-slate-600'
              }`}
            >
              <User className={`w-16 h-16 ${isPlayingAudio ? 'text-white' : 'text-slate-300'}`} />
            </div>
          </div>

          {/* Speaking indicator */}
          {isPlayingAudio && (
            <div className="flex items-center gap-1.5">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="w-1 bg-blue-400 rounded-full animate-pulse"
                  style={{
                    height: `${12 + Math.random() * 16}px`,
                    animationDelay: `${i * 0.15}s`,
                    animationDuration: '0.6s',
                  }}
                />
              ))}
              <span className="text-blue-400 text-sm ml-2 font-medium">AI is speaking...</span>
            </div>
          )}

          {/* Question text */}
          <div className="w-full max-w-2xl">
            <div className="px-6 py-4 rounded-2xl bg-slate-800/60 backdrop-blur border border-slate-700/50 text-center">
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                Question {currentQuestion.questionSequence}
              </p>
              <p className="text-slate-200 text-base leading-relaxed">
                {currentQuestion.questionText}
              </p>
            </div>
          </div>
        </div>

        {/* Bottom — Recording Controls */}
        <div className="w-full max-w-3xl z-10 mt-6">
          <div className="bg-slate-800/60 backdrop-blur rounded-2xl border border-slate-700/50 p-6">
            <div className="flex flex-col items-center gap-4">
              {!isRecording && !recordedBlob && (
                <div className="text-center space-y-3">
                  <p className="text-slate-400 text-sm">
                    {isPlayingAudio
                      ? 'Listen to the question, then record your answer...'
                      : 'Click to start recording your response'}
                  </p>
                  <Button
                    size="lg"
                    onClick={startRecording}
                    disabled={isSubmitting}
                    className="gap-2 bg-red-500 hover:bg-red-600 text-white rounded-full px-8 h-14 text-base"
                  >
                    <Mic className="w-5 h-5" />
                    Record Answer
                  </Button>
                </div>
              )}

              {isRecording && (
                <div className="text-center space-y-3">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
                    <span className="text-red-400 font-medium">Recording...</span>
                  </div>

                  {/* Audio waveform visualization */}
                  <div className="flex items-end justify-center gap-1 h-12">
                    {Array.from({ length: 20 }).map((_, i) => (
                      <div
                        key={i}
                        className="w-1.5 bg-red-400 rounded-t animate-pulse"
                        style={{
                          height: `${Math.random() * 40 + 8}px`,
                          animationDelay: `${i * 0.08}s`,
                        }}
                      />
                    ))}
                  </div>

                  <Button
                    size="lg"
                    variant="destructive"
                    onClick={stopRecording}
                    className="gap-2 rounded-full px-8 h-14"
                  >
                    <Square className="w-5 h-5" />
                    Stop Recording
                  </Button>
                </div>
              )}

              {recordedBlob && !isRecording && (
                <div className="w-full space-y-3">
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 justify-center">
                    <CheckCircle2 className="w-5 h-5 text-green-500" />
                    <p className="text-green-500 font-medium text-sm">Response recorded!</p>
                  </div>

                  <div className="flex gap-3">
                    <Button
                      variant="outline"
                      className="flex-1 border-slate-600 text-slate-300 hover:bg-slate-700"
                      onClick={() => setRecordedBlob(null)}
                      disabled={isSubmitting}
                    >
                      <MicOff className="w-4 h-4 mr-2" />
                      Re-record
                    </Button>
                    <Button
                      className="flex-1 bg-blue-600 hover:bg-blue-700"
                      onClick={submitAndGetNext}
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <ArrowRight className="w-4 h-4 mr-2" />
                          Submit & Next
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {/* Error Display */}
              {error && (
                <div className="w-full flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ─── Finished Render ──────────────────────────────────────────────────

  const renderFinished = () => {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-4">
        <div className="w-full max-w-lg text-center space-y-8">
          {/* Success/End Icon */}
          <div className="relative mx-auto w-28 h-28">
            <div className="absolute inset-0 rounded-full bg-green-500/10 animate-pulse" />
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
              className="w-full bg-red-500 hover:bg-red-600 text-white rounded-xl h-14 text-base gap-2"
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

  // ─── Main Render ──────────────────────────────────────────────────────

  if (phase === 'lobby') return renderLobby();
  if (phase === 'interview') return renderInterview();
  if (phase === 'finished') return renderFinished();

  return null;
}
