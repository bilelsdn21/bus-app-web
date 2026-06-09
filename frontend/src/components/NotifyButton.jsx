import { useEffect, useState } from "react";
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

// Header bell: lets a logged-in user opt into (or out of) weekly push notifications.
export default function NotifyButton() {
  const [state, setState] = useState("loading"); // loading | off | on | denied | working

  useEffect(() => {
    if (!supported) { setState("unsupported"); return; }
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => setState(sub ? "on" : (Notification.permission === "denied" ? "denied" : "off")))
      .catch(() => setState("off"));
  }, []);

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
      alert("Notifications activées ✅ — vous recevrez le résumé chaque semaine.");
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
    } catch { setState("on"); }
  };

  if (state === "unsupported" || state === "loading") return null;

  const on = state === "on";
  return (
    <button
      onClick={on ? disable : enable}
      disabled={state === "working"}
      title={on ? "Notifications activées — cliquez pour désactiver" : "Activer les notifications hebdomadaires"}
      className={`flex shrink-0 items-center rounded-lg px-2 py-1 text-base leading-none hover:bg-white/10 disabled:opacity-50 ${on ? "text-amber-300" : "text-sky-200 hover:text-white"}`}
    >
      {on ? "🔔" : "🔕"}
    </button>
  );
}
