import { useEffect, useRef, useState } from 'react';

interface UseSmartPollingOptions {
  isComplete: boolean;
  maxPollTime?: number; // ms
  maxPolls?: number;
  onTimeout?: () => void;
}

export function useSmartPolling(
  callback: () => void,
  options: UseSmartPollingOptions
) {
  const {
    isComplete,
    maxPollTime = 240000, // 4 min default
    maxPolls = 30,
    onTimeout,
  } = options;

  const [pollCount, setPollCount] = useState(0);
  const [hasTimedOut, setHasTimedOut] = useState(false);
  const startTimeRef = useRef<number>(Date.now());
  const pollKeyRef = useRef<string>(`poll_${Math.random()}`);

  useEffect(() => {
    if (isComplete || hasTimedOut) return;

    const getBackoffDelay = (count: number) => {
      const delays = [2000, 4000, 8000, 16000];
      return delays[Math.min(count, delays.length - 1)];
    };

    const pollTimer = setTimeout(() => {
      const elapsedTime = Date.now() - startTimeRef.current;

      if (elapsedTime > maxPollTime || pollCount >= maxPolls) {
        setHasTimedOut(true);
        onTimeout?.();
        return;
      }

      callback();
      setPollCount((c) => c + 1);
    }, getBackoffDelay(pollCount));

    return () => clearTimeout(pollTimer);
  }, [isComplete, hasTimedOut, pollCount, callback, maxPollTime, maxPolls, onTimeout]);

  return { pollCount, hasTimedOut };
}
