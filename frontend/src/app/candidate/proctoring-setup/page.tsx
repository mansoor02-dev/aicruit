'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Camera,
  CameraOff,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  Shield,
  Eye,
  Sun,
  MonitorOff,
  UserCheck,
  Video,
  RefreshCw,
} from 'lucide-react';

// ─── Types ──────────────────────────────────────────────────────────────────

type SetupStep = 'instructions' | 'permission' | 'preview' | 'ready';
type CameraStatus = 'idle' | 'requesting' | 'granted' | 'denied' | 'error';

// ─── Component ──────────────────────────────────────────────────────────────

export default function ProctoringSetupPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const applicationId = searchParams.get('applicationId');

  const [currentStep, setCurrentStep] = useState<SetupStep>('instructions');
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isCameraWorking, setIsCameraWorking] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // ─── Step Definitions ───────────────────────────────────────────────────

  const steps: SetupStep[] = ['instructions', 'permission', 'preview', 'ready'];
  const currentStepIndex = steps.indexOf(currentStep);

  const stepLabels: Record<SetupStep, string> = {
    instructions: 'Instructions',
    permission: 'Camera Access',
    preview: 'Camera Test',
    ready: 'Ready',
  };

  // ─── Camera Permission ─────────────────────────────────────────────────

  const requestCameraPermission = useCallback(async () => {
    setCameraStatus('requesting');
    setCameraError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      setCameraStatus('granted');
    } catch (err: any) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCameraStatus('denied');
        setCameraError('Camera access was denied. Please allow camera access in your browser settings and try again.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setCameraStatus('error');
        setCameraError('No camera detected. Please connect a camera and try again.');
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        setCameraStatus('error');
        setCameraError('Camera is in use by another application. Please close other apps using the camera and try again.');
      } else {
        setCameraStatus('error');
        setCameraError(`Failed to access camera: ${err.message || 'Unknown error'}`);
      }
    }
  }, []);

  // ─── Attach Stream to Video ─────────────────────────────────────────────

  useEffect(() => {
    if (currentStep === 'preview' && streamRef.current && videoRef.current) {
      const video = videoRef.current;
      video.srcObject = streamRef.current;

      const handlePlaying = () => {
        setIsCameraWorking(true);
      };

      video.addEventListener('playing', handlePlaying);
      video.play().catch(() => {
        setCameraError('Failed to play camera preview.');
      });

      return () => {
        video.removeEventListener('playing', handlePlaying);
      };
    }
  }, [currentStep]);

  // ─── Cleanup on Unmount ─────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      // Don't stop stream on unmount — it may be passed forward
      // Only stop if navigating away from the flow entirely
    };
  }, []);

  // ─── Navigation ─────────────────────────────────────────────────────────

  const goToPermission = () => setCurrentStep('permission');

  const goToPreview = () => {
    if (cameraStatus === 'granted') {
      setCurrentStep('preview');
    }
  };

  const goToReady = () => {
    if (isCameraWorking) {
      setCurrentStep('ready');
    }
  };

  const handleContinueToInterview = () => {
    // Store camera-ready flags so the interview lobby can skip the camera step
    sessionStorage.setItem('proctoring_camera_ready', 'true');
    if (applicationId) {
      sessionStorage.setItem('proctoring_app_id', applicationId);
    }

    // Stop the camera stream — the interview page will re-acquire if needed
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    // Navigate to the interview lobby
    if (applicationId) {
      router.push(`/candidate/interview/${applicationId}`);
    } else {
      // Fallback: go back if no applicationId was provided
      window.history.back();
    }
  };

  // ─── Render: Step Progress Bar ──────────────────────────────────────────

  const renderStepProgress = () => (
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
  );

  // ─── Render: Instructions Step ──────────────────────────────────────────

  const renderInstructions = () => (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-primary" />
          Proctoring Instructions
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground text-sm">
          Please read the following guidelines carefully before proceeding. These rules are in place to ensure a fair and secure interview.
        </p>

        <div className="space-y-3">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
            <UserCheck className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-foreground">One Person Only</p>
              <p className="text-sm text-muted-foreground">
                Only you should be visible in the camera frame. Ensure no other person is present in the background.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
            <MonitorOff className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-foreground">Do Not Switch Tabs</p>
              <p className="text-sm text-muted-foreground">
                Switching tabs, opening other applications, or leaving the screen is not allowed during the interview.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
            <Sun className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-foreground">Proper Lighting</p>
              <p className="text-sm text-muted-foreground">
                Ensure your face is well lit and clearly visible. Avoid backlighting or overly dark environments.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/10">
            <Video className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-foreground">Camera Must Stay On</p>
              <p className="text-sm text-muted-foreground">
                Your camera must remain active for the entire duration of the interview. Do not cover, disable, or disconnect it.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
            <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-foreground">Suspicious Activity Warning</p>
              <p className="text-sm text-muted-foreground">
                Any suspicious behavior — such as using notes, having someone else present, or using unauthorized tools — may lead to immediate cancellation of your interview.
              </p>
            </div>
          </div>
        </div>

        <Button className="w-full" size="lg" onClick={goToPermission}>
          I Understand, Continue
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </CardContent>
    </Card>
  );

  // ─── Render: Camera Permission Step ─────────────────────────────────────

  const renderPermission = () => (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Camera className="w-5 h-5 text-primary" />
          Camera Permission
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground">
          We need access to your camera for proctoring during the interview. Your camera feed is used to ensure interview integrity.
        </p>

        {cameraStatus === 'idle' && (
          <div className="text-center space-y-4">
            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
              <Camera className="w-10 h-10 text-primary" />
            </div>
            <Button size="lg" onClick={requestCameraPermission}>
              Allow Camera Access
            </Button>
          </div>
        )}

        {cameraStatus === 'requesting' && (
          <div className="text-center space-y-4">
            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
              <Loader2 className="w-10 h-10 text-primary animate-spin" />
            </div>
            <p className="text-muted-foreground font-medium">Requesting camera access…</p>
            <p className="text-sm text-muted-foreground">
              Please allow the camera permission in the browser popup.
            </p>
          </div>
        )}

        {cameraStatus === 'granted' && (
          <div className="text-center space-y-4">
            <div className="w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-10 h-10 text-green-500" />
            </div>
            <p className="text-green-500 font-medium">Camera access granted!</p>
            <Button className="w-full" size="lg" onClick={goToPreview}>
              Continue to Camera Test
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        )}

        {(cameraStatus === 'denied' || cameraStatus === 'error') && (
          <div className="text-center space-y-4">
            <div className="w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center mx-auto">
              {cameraStatus === 'denied' ? (
                <CameraOff className="w-10 h-10 text-red-500" />
              ) : (
                <XCircle className="w-10 h-10 text-red-500" />
              )}
            </div>
            <p className="text-red-500 font-medium">
              {cameraStatus === 'denied' ? 'Camera access denied' : 'Camera error'}
            </p>
            {cameraError && (
              <p className="text-sm text-muted-foreground">{cameraError}</p>
            )}
            <Button variant="outline" onClick={requestCameraPermission}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );

  // ─── Render: Camera Preview Step ────────────────────────────────────────

  const renderPreview = () => (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Eye className="w-5 h-5 text-primary" />
          Camera Preview
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground">
          Check your camera feed below. Make sure your face is clearly visible and well lit.
        </p>

        <div className="relative rounded-lg overflow-hidden bg-black/90 aspect-video max-w-md mx-auto border border-border">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="w-full h-full object-cover"
          />

          {!isCameraWorking && (
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-white animate-spin" />
            </div>
          )}
        </div>

        {isCameraWorking && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
            <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
            <p className="text-green-500 font-medium">Camera is working correctly!</p>
          </div>
        )}

        {cameraError && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-red-500 text-sm">{cameraError}</p>
          </div>
        )}

        <Button
          className="w-full"
          size="lg"
          onClick={goToReady}
          disabled={!isCameraWorking}
        >
          Continue
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </CardContent>
    </Card>
  );

  // ─── Render: Ready Step ─────────────────────────────────────────────────

  const renderReady = () => (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-green-500">
          <CheckCircle2 className="w-5 h-5" />
          Ready to Continue
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
            <span>Camera permission granted</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="w-4 h-4 text-green-500" />
            <span>Camera tested and working</span>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
          <p className="text-sm text-muted-foreground">
            Your camera is set up and ready. Click the button below to continue to the interview. Your camera will remain active throughout the session for proctoring purposes.
          </p>
        </div>

        <Button className="w-full" size="lg" onClick={handleContinueToInterview}>
          Continue to Interview
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </CardContent>
    </Card>
  );

  // ─── Main Render ────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-foreground">Proctoring Setup</h1>
          <p className="text-muted-foreground">
            Complete the steps below to set up your camera before the interview
          </p>
        </div>

        {/* Progress Steps */}
        {renderStepProgress()}

        {/* Step Content */}
        {currentStep === 'instructions' && renderInstructions()}
        {currentStep === 'permission' && renderPermission()}
        {currentStep === 'preview' && renderPreview()}
        {currentStep === 'ready' && renderReady()}
      </div>
    </div>
  );
}
