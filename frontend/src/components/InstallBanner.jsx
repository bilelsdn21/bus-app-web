import { useEffect, useState } from "react";

const KEY = "bus_install_dismissed";
const standalone = typeof window !== "undefined" &&
  (window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true);

// Android/Chrome: offers "install the app" (home-screen icon, full screen, faster to open).
export default function InstallBanner() {
  const [evt, setEvt] = useState(null);
  const [hidden, setHidden] = useState(() => {
    try { return Date.now() - Number(localStorage.getItem(KEY) || 0) < 14 * 864e5; } catch { return false; }
  });

  useEffect(() => {
    const on = (e) => { e.preventDefault(); setEvt(e); };
    window.addEventListener("beforeinstallprompt", on);
    window.addEventListener("appinstalled", () => setEvt(null));
    return () => window.removeEventListener("beforeinstallprompt", on);
  }, []);

  if (!evt || hidden || standalone) return null;
  const later = () => { try { localStorage.setItem(KEY, String(Date.now())); } catch {} setHidden(true); };
  const install = async () => { evt.prompt(); await evt.userChoice.catch(() => {}); setEvt(null); };

  return (
    <div className="mb-4 flex items-center gap-3 rounded-2xl bg-white p-3 shadow ring-1 ring-amber-300 sm:hidden">
      <span className="text-2xl">📲</span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-bold text-[#1a3a5c]">Installer l'application</div>
        <div className="text-[11px] text-slate-500">Accès direct depuis l'écran d'accueil, plein écran.</div>
      </div>
      <button onClick={install} className="h-10 rounded-lg bg-amber-500 px-3 text-sm font-bold text-[#13294a] active:scale-95">Installer</button>
      <button onClick={later} aria-label="Plus tard" className="h-10 px-1 text-slate-400">✕</button>
    </div>
  );
}
