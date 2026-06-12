import { useState } from "react";
import CalendarView from "./components/CalendarView.jsx";
import DayEntry from "./components/DayEntry.jsx";
import ContractsView from "./components/ContractsView.jsx";
import SettingsView from "./components/SettingsView.jsx";
import JournalView from "./components/JournalView.jsx";
import Login from "./components/Login.jsx";
import NotifyButton from "./components/NotifyButton.jsx";
import Logo from "./components/Logo.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";

export default function App() {
  const [auth, setAuth] = useState(() => {
    try { return JSON.parse(localStorage.getItem("bus_auth") || "null"); } catch { return null; }
  });
  const isAdmin = auth?.role === "admin";

  const [mode, setMode] = useState(
    typeof window !== "undefined" && window.innerWidth < 768 ? "entry" : "calendar"
  );
  const [now] = useState(() => new Date());
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  if (!auth) return <Login onLogin={setAuth} />;

  const logout = () => { localStorage.removeItem("bus_auth"); setAuth(null); };

  // tabs allowed per role. Viewer sees Calendrier + Contrats + Params (all read-only);
  // Saisie (data entry) and Journal (audit log) stay admin-only.
  const tabs = isAdmin
    ? [["calendar", "📊 Calendrier"], ["contracts", "📄 Contrats"], ["entry", "✏️ Saisie"], ["settings", "⚙️ Params"], ["journal", "🧾 Journal"]]
    : [["calendar", "📊 Calendrier"], ["contracts", "📄 Contrats"], ["settings", "⚙️ Params"]];

  // if a viewer somehow has an admin-only mode selected, fall back to calendar
  const effMode = tabs.some(([k]) => k === mode) ? mode : "calendar";

  return (
    <div className="min-h-full bg-slate-100 text-slate-800">
      <header className="sticky top-0 z-40 border-b border-amber-400/30 bg-gradient-to-r from-[#13294a] via-[#1a3a5c] to-[#1f4a76] text-white shadow-lg">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-2 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15">
              <Logo className="h-6 w-6" />
            </span>
            <div>
              <div className="text-sm font-extrabold leading-tight tracking-tight">Bestimetravel</div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-300/90">Gestion des Bus</div>
            </div>
          </div>
          <nav className="flex flex-wrap gap-1 rounded-xl bg-white/10 p-1">
            {tabs.map(([key, label]) => (
              <Tab key={key} on={effMode === key} onClick={() => setMode(key)}>{label}</Tab>
            ))}
          </nav>
          <div className="flex shrink-0 items-center gap-1">
          <NotifyButton />
          <button onClick={logout} title="Déconnexion" className="flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-xs text-sky-200 hover:bg-white/10 hover:text-white">
            <span className="hidden sm:inline">{auth.username}{!isAdmin && <span className="ml-1 rounded bg-white/15 px-1.5 py-0.5 text-[10px] font-bold uppercase">lecture</span>}</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-label="Déconnexion">
              <path d="M18.36 6.64a9 9 0 1 1-12.73 0" />
              <line x1="12" y1="2" x2="12" y2="12" />
            </svg>
          </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-3 py-4 sm:px-4 sm:py-6">
        <ErrorBoundary key={effMode}>
          {effMode === "calendar" && <CalendarView year={year} month={month} setYear={setYear} setMonth={setMonth} readOnly={!isAdmin} />}
          {effMode === "contracts" && <ContractsView readOnly={!isAdmin} />}
          {effMode === "entry" && <DayEntry />}
          {effMode === "settings" && <SettingsView readOnly={!isAdmin} />}
          {effMode === "journal" && <JournalView />}
        </ErrorBoundary>
      </main>
    </div>
  );
}

function Tab({ on, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition ${on ? "bg-white text-[#1a3a5c] shadow" : "text-white/80 hover:text-white"}`}>
      {children}
    </button>
  );
}
