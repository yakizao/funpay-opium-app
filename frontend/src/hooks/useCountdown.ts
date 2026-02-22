import { useState, useEffect, useCallback } from 'react';

/**
 * Hook for live countdown timer. Ticks every second.
 * Use with `formatRemaining()` to display time left.
 */
export function useCountdown() {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(iv);
  }, []);

  const formatRemaining = useCallback((endTime: string): string => {
    const end = new Date(endTime).getTime();
    const diff = end - now;
    if (diff <= 0) return 'expired';
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    return `${h}h ${m}m ${s}s`;
  }, [now]);

  const isExpiringSoon = useCallback((endTime: string, thresholdMs = 3600000): boolean => {
    const end = new Date(endTime).getTime();
    const diff = end - now;
    return diff > 0 && diff < thresholdMs;
  }, [now]);

  return { now, formatRemaining, isExpiringSoon };
}
