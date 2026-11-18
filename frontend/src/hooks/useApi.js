import { useCallback, useEffect, useRef, useState } from "react";
import { api, describeError } from "../api/client";

/**
 * GET helper with loading/error state, polling and manual refresh.
 * - The next poll is scheduled `interval` ms after the LAST attempt (so manual refresh restarts the clock).
 * - Previous data stays visible during background refreshes and after a failed refresh.
 * - When a hidden browser tab becomes visible again and the data is older than `interval`, it reloads at once.
 */
export function useApi(path, params = {}, { interval = 0, enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled, updatedAt: null, attemptedAt: null });
  const seq = useRef(0);
  const lastKey = useRef("");
  const attemptRef = useRef(0);
  const key = path + JSON.stringify(params);

  const load = useCallback(
    async (silent = false) => {
      if (!enabled) return;
      const id = ++seq.current;
      if (!silent) setState((s) => ({ ...s, loading: true, error: null }));
      try {
        const r = await api.get(path, { params });
        if (id !== seq.current) return;
        attemptRef.current = Date.now();
        setState({ data: r.data, error: null, loading: false, updatedAt: new Date(), attemptedAt: Date.now() });
      } catch (e) {
        if (id !== seq.current) return;
        attemptRef.current = Date.now();
        setState((s) => ({ ...s, error: describeError(e), loading: false, attemptedAt: Date.now() }));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, enabled]
  );

  // initial load / reload when the request changes (e.g. another city)
  useEffect(() => {
    if (lastKey.current !== key) {
      lastKey.current = key;
      setState({ data: null, error: null, loading: enabled, updatedAt: null, attemptedAt: null });
    }
    load(false);
  }, [load, key, enabled]);

  // polling: schedule the next silent refresh after every attempt
  useEffect(() => {
    if (!interval || !enabled || state.attemptedAt === null) return;
    const t = setTimeout(() => load(true), interval);
    return () => clearTimeout(t);
  }, [load, interval, enabled, state.attemptedAt]);

  // catch up when the tab returns to the foreground
  useEffect(() => {
    if (!interval || !enabled) return;
    const onVis = () => {
      if (document.visibilityState === "visible" && Date.now() - attemptRef.current > interval) load(true);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [load, interval, enabled]);

  return { ...state, refresh: () => load(false) };
}
