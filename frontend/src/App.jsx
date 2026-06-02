import { useState } from "react";
import CalendarView from "./components/CalendarView.jsx";
import DayEntry from "./components/DayEntry.jsx";
import ContractsView from "./components/ContractsView.jsx";
import SettingsView from "./components/SettingsView.jsx";
import Login from "./components/Login.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";

export default function App() {
  const [auth, setAuth] = useState(() => {
    try { return JSON.parse(localStorage.getItem("bus_auth") || "null"); } catch { return null; }
  });
  const [mode, setMode] = useState(
    typeof window !== "undefined" && window.innerWidth < 768 ? "entry" : "calendar"
  );
  const [now] = useState(() => new Date());
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  if (!auth) return <Login onLogin={setAuth} />;

  const logout = () => { localStorage.removeItem("bus_auth"); setAuth(null); };

  return (
    <div className="min-h-full bg-slate-100 text-slate-800">
      <header className="sticky top-0 z-20 bg-[#1a3a5c] text-white shadow-lg">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-2 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">🚌</span>
            <div>
              <div className="text-sm font-extrabold leading-tight tracking-tight">Bestimetravel</div>
              <div className="text-[11px] text-sky-200">Gestion des Bus</div>
            </div>
          </div>
          <nav className="flex flex-wrap gap-1 rounded-xl bg-white/10 p-1">
            <Tab on={mode === "calendar"} onClick={() => setMode("calendar")}>📊 Calendrier</Tab>
            <Tab on={mode === "contracts"} onClick={() => setMode("contracts")}>📄 Contrats</Tab>
            <Tab on={mode === "entry"} onClick={() => setMode("entry")}>✏️ Saisie</Tab>
            <Tab on={mode === "settings"} onClick={() => setMode("settings")}>⚙️ Params</Tab>
          </nav>
          <button onClick={logout} title="Déconnexion" className="hidden rounded-lg px-2 py-1 text-xs text-sky-200 hover:bg-white/10 hover:text-white sm:block">
            {auth.username} ⏻
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-3 py-4 sm:px-4 sm:py-6">
        <ErrorBoundary key={mode}>
          {mode === "calendar" && <CalendarView year={year} month={month} setYear={setYear} setMonth={setMonth} />}
          {mode === "contracts" && <ContractsView />}
          {mode === "entry" && <DayEntry />}
          {mode === "settings" && <SettingsView />}
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
