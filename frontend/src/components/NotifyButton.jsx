import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

const supported =
  typeof window !== "undefined" &&
  "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

// iPhone/iPad only allow web push once the app is added to the home screen
const isIOS = typeof navigator !== "undefined" && /iphone|ipad|ipod/i.test(navigator.userAgent);
const standalone = typeof window !== "undefined" &&
  (window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true);

const CHANGED = "bus-push-changed";
const DISMISS_KEY = "bus_push_dismissed";

// Shared push state so the header bell and the prompt always agree.
function usePush() {
  const [state, setState] = useState("loading"); // loading | unsupported | off | on | denied | working

  const refresh = useCallback(() => {
    if (!supported) { setState("unsupported"); return; }
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => setState(sub ? "on" : (Notification.permission === "denied" ? "denied" : "off")))
      .catch(() => setState("off"));
  }, []);

  useEffect(() => {
    refresh();
    window.addEventListener(CHANGED, refresh);
    return () => window.removeEventListener(CHANGED, refresh);
  }, [refresh]);

  const enable = async () => {
    setState("working");
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { setState("denied"); alert("Notifications refusées. Activez-les dans les réglages du navigateur/téléphone."); return; }
      const reg = await navigator.serviceWorker.ready;
      const { key } = await api.pushKey();
      if (!key) { setState("off"); alert("Le service de notifications n'est pas encore configuré côté serveur."); return; }
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) });
      const j = sub.toJSON();
      await api.pushSubscribe({ endpoint: j.endpoint, keys: j.keys });
      setState("on");
      window.dispatchEvent(new Event(CHANGED));
    } catch (e) {
      setState("off");
      alert("Échec de l'activation : " + (e?.message || e));
    }
  };

  const disable = async () => {
    setState("working");
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) { await api.pushUnsubscribe({ endpoint: sub.endpoint, keys: sub.toJSON().keys }); await sub.unsubscribe(); }
      setState("off");
      window.dispatchEvent(new Event(CHANGED));
    } catch { setState("on"); }
  };

  return { state, enable, disable };
}

// Header bell: big enough to tap, and turning notifications OFF asks first.
export default function NotifyButton() {
  const { state, enable, disable } = usePush();
  if (state === "unsupported" || state === "loading") return null;

  const on = state === "on";
  const onClick = () => {
    if (!on) return enable();
    if (window.confirm("Désactiver les notifications sur cet appareil ?")) disable();
  };
  return (
    <button
      onClick={onClick}
      disabled={state === "working"}
      aria-label={on ? "Notifications activées" : "Activer les notifications"}
      title={on ? "Notifications activées — toucher pour désactiver" : "Activer les notifications"}
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-xl leading-none hover:bg-white/10 disabled:opacity-50 ${on ? "text-amber-300" : "text-sky-200 hover:text-white"}`}
    >
      {on ? "🔔" : "🔕"}
    </button>
  );
}

// Banner at the bottom of the screen (thumb reach) until the user turns notifications on
// or says "plus tard" (asked again after a week).
export function NotifyPrompt() {
  const { state, enable } = usePush();
  const [hidden, setHidden] = useState(() => {
    try { return Date.now() - Number(localStorage.getItem(DISMISS_KEY) || 0) < 7 * 864e5; } catch { return false; }
  });
  const later = () => {
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch {}
    setHidden(true);
  };

  if (hidden || state === "loading" || state === "on" || state === "denied") return null;

  // iPhone in a normal Safari tab cannot receive push: explain how to install the app instead
  if (state === "unsupported") {
    if (!(isIOS && !standalone)) return null;
    return (
      <div className="fixed inset-x-3 bottom-20 z-40 rounded-2xl bg-white p-4 shadow-2xl ring-1 ring-slate-200 sm:hidden">
        <div className="text-sm font-bold text-[#1a3a5c]">🔔 Recevoir les notifications sur iPhone</div>
        <p className="mt-1 text-xs text-slate-600">
          Touchez <b>Partager</b> (le carré avec la flèche) puis <b>« Sur l'écran d'accueil »</b>, ouvrez l'application depuis l'icône, et activez la cloche.
        </p>
        <button onClick={later} className="mt-3 h-10 w-full rounded-lg bg-slate-100 text-sm font-semibold text-slate-600">OK, plus tard</button>
      </div>
    );
  }

  return (
    <div className="fixed inset-x-3 bottom-20 z-40 rounded-2xl bg-white p-4 shadow-2xl ring-1 ring-slate-200 sm:inset-x-auto sm:bottom-4 sm:right-4 sm:w-80">
      <div className="text-sm font-bold text-[#1a3a5c]">🔔 Restez informé</div>
      <p className="mt-1 text-xs text-slate-600">Recevez le résumé du mois et les nouveautés de l'application directement sur ce téléphone.</p>
      <div className="mt-3 flex gap-2">
        <button onClick={enable} disabled={state === "working"}
          className="h-11 flex-1 rounded-lg bg-amber-500 text-sm font-bold text-[#13294a] shadow active:scale-95 disabled:opacity-60">
          {state === "working" ? "…" : "Activer"}
        </button>
        <button onClick={later} className="h-11 rounded-lg bg-slate-100 px-4 text-sm font-semibold text-slate-600">Plus tard</button>
      </div>
    </div>
  );
}
