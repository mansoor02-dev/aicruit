import { useState, useEffect, useRef } from 'react';

interface UseTimerOptions {
  initialTime?: number;
  onTimeout?: () => void;
  enabled?: boolean;
}

/**
 * Custom hook for managing a countdown timer
 * @param options - Timer configuration options
 * @returns Timer state and controls
 */
export function useTimer({ initialTime = 60, onTimeout, enabled = true }: UseTimerOptions = {}) {
  const [timer, setTimer] = useState(initialTime);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    setTimer(initialTime);
    intervalRef.current = setInterval(() => {
      setTimer((t) => {
        if (t <= 1) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          onTimeout?.();
          return 0;
        }
        return t - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, initialTime, onTimeout]);

  const reset = (newTime?: number) => {
    setTimer(newTime ?? initialTime);
  };

  return { timer, reset };
}

