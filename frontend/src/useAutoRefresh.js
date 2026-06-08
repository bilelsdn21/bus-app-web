import { useEffect, useRef } from "react";

// Re-run `fn` whenever the app regains focus / becomes visible / comes back online.
// Fixes mobile: reopening the app (after the phone suspends it) now reloads fresh
// data instead of showing the stale/empty screen from when it was backgrounded.
export function useAutoRefresh(fn) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    const run = () => { if (document.visibilityState !== "hidden") ref.current?.(); };
    window.addEventListener("focus", run);
    window.addEventListener("online", run);
    document.addEventListener("visibilitychange", run);
    return () => {
      window.removeEventListener("focus", run);
      window.removeEventListener("online", run);
      document.removeEventListener("visibilitychange", run);
    };
  }, []);
}
