import { useState } from "react";
import CalendarView from "./components/CalendarView.jsx";
import DayEntry from "./components/DayEntry.jsx";
import ContractsView from "./components/ContractsView.jsx";
import SettingsView from "./components/SettingsView.jsx";
import JournalView from "./components/JournalView.jsx";
import Login from "./components/Login.jsx";
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
      <header className="sticky top-0 z-40 bg-[#1a3a5c] text-white shadow-lg">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-2 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <BusLogo />
            <div>
              <div className="text-sm font-extrabold leading-tight tracking-tight">Bestimetravel</div>
              <div className="text-[11px] text-sky-200">Gestion des Bus</div>
            </div>
          </div>
          <nav className="flex flex-wrap gap-1 rounded-xl bg-white/10 p-1">
            {tabs.map(([key, label]) => (
              <Tab key={key} on={effMode === key} onClick={() => setMode(key)}>{label}</Tab>
            ))}
          </nav>
          <button onClick={logout} title="Déconnexion" className="hidden items-center gap-1 rounded-lg px-2 py-1 text-xs text-sky-200 hover:bg-white/10 hover:text-white sm:flex">
            {auth.username}{!isAdmin && <span className="rounded bg-white/15 px-1.5 py-0.5 text-[10px] font-bold uppercase">lecture</span>} ⏻
          </button>
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

function BusLogo() {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-black/5">
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-label="Bus">
        {/* body */}
        <rect x="3" y="4.5" width="18" height="12" rx="2.6" fill="#f59e0b" />
        {/* window strip */}
        <rect x="4.6" y="6.4" width="14.8" height="3.7" rx="1" fill="#bae6fd" />
        {/* window dividers */}
        <line x1="9.3" y1="6.4" x2="9.3" y2="10.1" stroke="#f59e0b" strokeWidth="1" />
        <line x1="14" y1="6.4" x2="14" y2="10.1" stroke="#f59e0b" strokeWidth="1" />
        {/* headlight */}
        <circle cx="20.2" cy="12" r="0.7" fill="#fff7ed" />
        {/* wheels */}
        <circle cx="8" cy="17" r="2.1" fill="#1a3a5c" />
        <circle cx="8" cy="17" r="0.8" fill="#e2e8f0" />
        <circle cx="16" cy="17" r="2.1" fill="#1a3a5c" />
        <circle cx="16" cy="17" r="0.8" fill="#e2e8f0" />
      </svg>
    </span>
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
