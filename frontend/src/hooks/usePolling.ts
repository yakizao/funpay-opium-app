import { useEffect, useRef, useCallback } from 'react';

/**
 * Smart polling hook with:
 * - Configurable interval
 * - Pauses when tab is hidden (Page Visibility API)
 * - Immediate refetch when tab becomes visible again
 * - Immediate refetch on window.focus
 * - Deduplication (skips tick if previous fetch still running)
 * - Minimum 3s gap between fetches to avoid rapid-fire on focus/visibility events
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs = 10000,
  enabled = true,
) {
  const savedCallback = useRef(callback);
  const runningRef = useRef(false);
  const lastRunRef = useRef(0);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  const tick = useCallback(async () => {
    if (runningRef.current) return;
    if (Date.now() - lastRunRef.current < 3000) return; // min 3s between fetches
    runningRef.current = true;
    lastRunRef.current = Date.now();
    try {
      await savedCallback.current();
    } catch {
      // Errors handled by the callback itself
    } finally {
      runningRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const iv = setInterval(() => {
      if (!document.hidden) tick();
    }, intervalMs);

    const onVisibility = () => {
      if (!document.hidden) tick();
    };

    const onFocus = () => tick();
    const onOnline = () => tick();

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('focus', onFocus);
    window.addEventListener('online', onOnline);

    return () => {
      clearInterval(iv);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('focus', onFocus);
      window.removeEventListener('online', onOnline);
    };
  }, [tick, intervalMs, enabled]);
}
