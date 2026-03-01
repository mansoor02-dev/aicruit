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
} from 'lucide-react';
import { getAuthToken } from '@/lib/api';

const API_BASE_URL = 'http://localhost:8000';

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

  // Refs
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);

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
    let testStartTime = Date.now();

    const checkLevel = () => {
      analyser.getByteFrequencyData(dataArray);
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      const normalizedLevel = Math.min(100, (avg / 128) * 100);
      setMicLevel(normalizedLevel);

      if (normalizedLevel > maxLevel) maxLevel = normalizedLevel;

      // Pass if we detect meaningful audio within 5 seconds
      if (maxLevel > 15) {
        setMicTestPassed(true);
      }

      // Auto-stop after 5 seconds
      if (Date.now() - testStartTime > 5000) {
        setIsMicTesting(false);
        if (maxLevel > 15) {
          setMicTestPassed(true);
        }
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

      // Response is binary audio with metadata in headers
      const interviewId = response.headers.get('X-Interview-Id') || '';
      const questionText = response.headers.get('X-Question-Text') || '';
      const questionSequence = parseInt(response.headers.get('X-Question-Sequence') || '1', 10);
      const audioBlob = await response.blob();

      setCurrentQuestion({
        interviewId,
        questionText,
        questionSequence,
        audioBlob,
      });
      setQuestionCount(questionSequence);
      setPhase('interview');
      setRecordedBlob(null);
    } catch (err: any) {
      setError(err.message || 'Failed to start interview');
    } finally {
      setIsLoadingQuestion(false);
    }
  }, [applicationId]);

  // ─── Play Question Audio ──────────────────────────────────────────────

  const playQuestionAudio = useCallback(() => {
    if (!currentQuestion?.audioBlob) return;

    const url = URL.createObjectURL(currentQuestion.audioBlob);
    const audio = new Audio(url);
    audioPlayerRef.current = audio;

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
  }, [currentQuestion]);

  // ─── Recording ────────────────────────────────────────────────────────

  const startRecording = useCallback(async () => {
    try {
      // Request a fresh stream if we don't have one active
      let stream = audioStreamRef.current;
      if (!stream || stream.getTracks().some(t => t.readyState === 'ended')) {
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

      mediaRecorder.start(250); // Collect in 250ms chunks
      setIsRecording(true);
      setRecordedBlob(null);
    } catch (err) {
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

      // Parse next question from response
      const interviewId = response.headers.get('X-Interview-Id') || currentQuestion.interviewId;
      const questionText = response.headers.get('X-Question-Text') || '';
      const questionSequence = parseInt(response.headers.get('X-Question-Sequence') || '1', 10);
      const audioBlob = await response.blob();

      setCurrentQuestion({
        interviewId,
        questionText,
        questionSequence,
        audioBlob,
      });
      setQuestionCount(questionSequence);
      setRecordedBlob(null);
    } catch (err: any) {
      setError(err.message || 'Failed to submit response');
    } finally {
      setIsSubmitting(false);
    }
  }, [currentQuestion, recordedBlob]);

  // ─── Cleanup ──────────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(t => t.stop());
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
    };
  }, []);

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

                {/* Mic Level Visualization */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Microphone Level</span>
                    <span className="text-muted-foreground">{Math.round(micLevel)}%</span>
                  </div>
                  <Progress value={micLevel} className="h-3" />
                </div>

                {/* Mic Level Bars Animation */}
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
                    When you click &quot;Start Interview&quot;, the AI will generate your first question.
                    Listen to the audio, then record your response. Take your time and answer thoughtfully.
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

  // ─── Interview Render ─────────────────────────────────────────────────

  const renderInterview = () => {
    if (!currentQuestion) return null;

    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-3xl space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">AI Interview</h1>
              <p className="text-muted-foreground">Answer each question clearly and thoughtfully</p>
            </div>
            <Badge variant="outline" className="text-lg px-4 py-2">
              Question {currentQuestion.questionSequence}
            </Badge>
          </div>

          {/* Question Card */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-primary" />
                Question {currentQuestion.questionSequence}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Question Text */}
              <div className="p-4 rounded-lg bg-muted/10 border border-border">
                <p className="text-foreground text-base leading-relaxed">
                  {currentQuestion.questionText}
                </p>
              </div>

              {/* Play Audio Button */}
              <div className="flex justify-center">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={playQuestionAudio}
                  disabled={isPlayingAudio || !currentQuestion.audioBlob}
                  className="gap-2"
                >
                  {isPlayingAudio ? (
                    <>
                      <Volume2 className="w-5 h-5 animate-pulse text-primary" />
                      Playing Audio...
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-5 h-5" />
                      Play Question Audio
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Response Card */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Mic className="w-5 h-5 text-primary" />
                Your Response
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Recording Controls */}
              <div className="flex flex-col items-center gap-4">
                {!isRecording && !recordedBlob && (
                  <div className="text-center space-y-3">
                    <p className="text-muted-foreground text-sm">
                      Click the button below to start recording your response.
                    </p>
                    <Button
                      size="lg"
                      onClick={startRecording}
                      disabled={isSubmitting}
                      className="gap-2 bg-red-500 hover:bg-red-600 text-white"
                    >
                      <Mic className="w-5 h-5" />
                      Start Recording
                    </Button>
                  </div>
                )}

                {isRecording && (
                  <div className="text-center space-y-3">
                    {/* Recording indicator */}
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
                      <span className="text-red-500 font-medium">Recording...</span>
                    </div>

                    {/* Animated bars */}
                    <div className="flex items-end justify-center gap-1 h-12">
                      {Array.from({ length: 15 }).map((_, i) => (
                        <div
                          key={i}
                          className="w-2 bg-red-500 rounded-t animate-pulse"
                          style={{
                            height: `${Math.random() * 40 + 8}px`,
                            animationDelay: `${i * 0.1}s`,
                          }}
                        />
                      ))}
                    </div>

                    <Button
                      size="lg"
                      variant="destructive"
                      onClick={stopRecording}
                      className="gap-2"
                    >
                      <Square className="w-5 h-5" />
                      Stop Recording
                    </Button>
                  </div>
                )}

                {recordedBlob && !isRecording && (
                  <div className="w-full space-y-3">
                    <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                      <CheckCircle2 className="w-5 h-5 text-green-500" />
                      <p className="text-green-500 font-medium text-sm">Response recorded successfully!</p>
                    </div>

                    <div className="flex gap-3">
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={() => {
                          setRecordedBlob(null);
                        }}
                        disabled={isSubmitting}
                      >
                        <MicOff className="w-4 h-4 mr-2" />
                        Re-record
                      </Button>
                      <Button
                        className="flex-1"
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
                            Submit & Next Question
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              </div>

              {/* Error Display */}
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                  <p className="text-red-500 text-sm">{error}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  };

  // ─── Main Render ──────────────────────────────────────────────────────

  if (phase === 'lobby') return renderLobby();
  if (phase === 'interview') return renderInterview();

  return null;
}
