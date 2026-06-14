import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmtTND } from "../colors.js";
import { useAutoRefresh } from "../useAutoRefresh.js";

const MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
const YEARS = (() => { const a = []; for (let y = 2025; y <= new Date().getFullYear() + 1; y++) a.push(y); return a; })();

// Per-vehicle time-utilization + performance, derived from the calendar payload.
function analyzeBus(bus) {
  const covered = bus.covered_days || [];
  let working = 0, unavailable = 0, idle = 0;
  for (const d of covered) {
    const c = bus.days[d];
    if (!c) idle++;
    else if (c === "red") unavailable++;
    else working++;
  }
  const cov = covered.length;
  const util = cov ? Math.round((working / cov) * 100) : 0;
  const net = bus.net;
  const rev = bus.contract?.revenue ?? 0;
  const loyer = bus.contract?.loyer ?? 0;
  const inRed = net != null && net < 0;
  const underused = cov > 0 && util < 50;
  let reason = null;
  if (inRed) {
    if (util < 55) reason = "Sous-utilisé — trop de jours sans location";
    else if (rev < loyer) reason = "Recettes trop basses pour le loyer";
    else reason = "Loyer + carburant > recettes";
  }
  return { ...bus, working, unavailable, idle, cov, util, net, rev, loyer, inRed, underused, reason };
}

export default function AnalyticsView({ year, month, setYear, setMonth }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("util"); // util | net

  const reload = () => api.calendar(year, month).then(setData).catch(() => {});
  useEffect(() => { setLoading(true); reload().finally(() => setLoading(false)); }, [year, month]);
  useAutoRefresh(reload);

  const s = useMemo(() => {
    if (!data) return null;
    const buses = data.buses.map(analyzeBus);
    const n = buses.length;
    const avgUtil = n ? Math.round(buses.reduce((a, b) => a + b.util, 0) / n) : 0;
    const profitable = buses.filter((b) => b.net != null && b.net >= 0).length;
    const red = buses.filter((b) => b.inRed);
    const underused = buses.filter((b) => b.underused);
    const reasonCounts = {};
    red.forEach((b) => { if (b.reason) reasonCounts[b.reason] = (reasonCounts[b.reason] || 0) + 1; });
    const topReason = Object.entries(reasonCounts).sort((a, b) => b[1] - a[1])[0];
    const sorted = [...buses].sort((a, b) => (sort === "util" ? a.util - b.util : (a.net ?? 0) - (b.net ?? 0)));
    const best = buses.filter((b) => b.net != null).sort((a, b) => b.net - a.net)[0];
    const mostIdle = [...buses].sort((a, b) => b.idle - a.idle)[0];
    return { buses, sorted, n, avgUtil, profitable, red, underused, topReason, best, mostIdle, totalNet: data.summary.total.net };
  }, [data, sort]);

  const prev = () => { if (month === 1) { setMonth(12); setYear(year - 1); } else setMonth(month - 1); };
  const next = () => { if (month === 12) { setMonth(1); setYear(year + 1); } else setMonth(month + 1); };

  return (
    <div className="space-y-5">
      {/* header + month picker */}
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">📈 Analyse de performance</h1>
        <div className="flex items-center gap-1.5">
          <button onClick={prev} className="rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow hover:bg-slate-50">←</button>
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="cursor-pointer rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm font-bold text-[#1a3a5c] shadow-sm outline-none focus:border-amber-400">
            {MONTHS_FR.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="cursor-pointer rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm font-bold text-[#1a3a5c] shadow-sm outline-none focus:border-amber-400">
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <button onClick={next} className="rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow hover:bg-slate-50">→</button>
        </div>
      </div>

      {loading && <div className="animate-pulse space-y-3"><div className="h-28 rounded-2xl bg-slate-100" /><div className="h-64 rounded-2xl bg-slate-100" /></div>}

      {!loading && s && s.n === 0 && (
        <div className="rounded-2xl bg-white px-6 py-14 text-center shadow ring-1 ring-slate-200">
          <div className="text-3xl">📊</div>
          <div className="mt-2 font-semibold text-slate-600">Aucun véhicule sous contrat ce mois-ci</div>
        </div>
      )}

      {!loading && s && s.n > 0 && (
        <>
          {/* fleet KPI cards */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Utilisation moyenne" big={`${s.avgUtil}%`} sub="du temps sous contrat" tone={s.avgUtil >= 70 ? "good" : s.avgUtil >= 45 ? "warn" : "bad"}>
              <Bar pct={s.avgUtil} tone={s.avgUtil >= 70 ? "good" : s.avgUtil >= 45 ? "warn" : "bad"} />
            </Kpi>
            <Kpi label="Véhicules rentables" big={`${s.profitable}/${s.n}`} sub={`${s.n - s.profitable} en perte`} tone={s.profitable >= s.n / 2 ? "good" : "bad"} />
            <Kpi label="Sous-utilisés" big={`${s.underused.length}`} sub="< 50% du temps loué" tone={s.underused.length ? "warn" : "good"} />
            <Kpi label="Résultat net flotte" big={fmtTND(s.totalNet)} sub={data.label} tone={s.totalNet >= 0 ? "good" : "bad"} />
          </div>

          {/* insight banners */}
          {s.underused.length > 0 && (
            <Insight tone="warn">
              ⚠️ <b>{s.underused.length} véhicule{s.underused.length > 1 ? "s" : ""}</b> loué{s.underused.length > 1 ? "s" : ""} mais utilisé{s.underused.length > 1 ? "s" : ""} moins de la moitié du temps — ce sont des locations qui ne « travaillent » pas assez.
            </Insight>
          )}
          {s.topReason && (
            <Insight tone="bad">
              💰 Cause principale de perte : <b>{s.topReason[0]}</b> ({s.topReason[1]} véhicule{s.topReason[1] > 1 ? "s" : ""}).
            </Insight>
          )}

          {/* sort */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Trier par :</span>
            <button onClick={() => setSort("util")} className={`rounded-lg px-3 py-1 font-semibold ${sort === "util" ? "bg-[#1a3a5c] text-white" : "bg-white text-slate-600 shadow-sm"}`}>Utilisation</button>
            <button onClick={() => setSort("net")} className={`rounded-lg px-3 py-1 font-semibold ${sort === "net" ? "bg-[#1a3a5c] text-white" : "bg-white text-slate-600 shadow-sm"}`}>Résultat net</button>
          </div>

          {/* per-bus list */}
          <div className="space-y-2">
            {s.sorted.map((b) => <BusRow key={b.id} b={b} />)}
          </div>

          {/* highlights */}
          <div className="grid gap-3 sm:grid-cols-2">
            {s.best && <Highlight emoji="🏆" title="Meilleur résultat" name={s.best.name} value={fmtTND(s.best.net)} good />}
            {s.mostIdle && s.mostIdle.idle > 0 && <Highlight emoji="💤" title="Plus de jours inactifs" name={s.mostIdle.name} value={`${s.mostIdle.idle} j inactifs`} />}
          </div>
        </>
      )}
    </div>
  );
}

function BusRow({ b }) {
  const cov = b.cov || 1;
  const w = (b.working / cov) * 100, u = (b.unavailable / cov) * 100, i = (b.idle / cov) * 100;
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-bold text-slate-700">{b.name}</div>
          <div className="text-[11px] text-slate-400">{b.region} · {b.type}</div>
        </div>
        <div className="flex items-center gap-2">
          {b.inRed && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-700">En perte</span>}
          {b.underused && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700">Sous-utilisé</span>}
          {b.net != null && (
            <span className={`rounded-md px-2 py-0.5 text-sm font-extrabold ${b.net >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>{fmtTND(b.net)}</span>
          )}
        </div>
      </div>

      {/* utilization bar */}
      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-bold text-[#1a3a5c]">{b.util}% utilisé</span>
          <span className="text-slate-400">{b.working} j travaillés · {b.idle} j inactifs{b.unavailable ? ` · ${b.unavailable} j indispo` : ""}</span>
        </div>
        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div className="bg-emerald-500" style={{ width: `${w}%` }} />
          <div className="bg-rose-400" style={{ width: `${u}%` }} />
          <div className="bg-slate-200" style={{ width: `${i}%` }} />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <span>Recettes <b className="text-slate-700">{fmtTND(b.rev)}</b></span>
        <span>Loyer <b className="text-slate-700">{fmtTND(b.loyer)}</b></span>
        {b.reason && <span className="text-rose-500">⚠️ {b.reason}</span>}
      </div>
    </div>
  );
}

const TONE = {
  good: "text-emerald-600", warn: "text-amber-600", bad: "text-rose-600",
};
function Kpi({ label, big, sub, tone = "good", children }) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-lg ring-1 ring-slate-200">
      <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-extrabold ${TONE[tone]}`}>{big}</div>
      <div className="text-[11px] text-slate-400">{sub}</div>
      {children}
    </div>
  );
}
function Bar({ pct, tone }) {
  const c = tone === "good" ? "bg-emerald-500" : tone === "warn" ? "bg-amber-400" : "bg-rose-500";
  return <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100"><div className={c} style={{ width: `${Math.max(0, Math.min(100, pct))}%`, height: "100%" }} /></div>;
}
function Insight({ tone, children }) {
  const c = tone === "bad" ? "bg-rose-50 text-rose-800 ring-rose-100" : "bg-amber-50 text-amber-800 ring-amber-100";
  return <div className={`rounded-2xl px-4 py-3 text-sm ring-1 ${c}`}>{children}</div>;
}
function Highlight({ emoji, title, name, value, good }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="text-2xl">{emoji}</div>
      <div className="min-w-0 flex-1">
        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{title}</div>
        <div className="truncate font-bold text-slate-700">{name}</div>
      </div>
      <div className={`font-extrabold ${good ? "text-emerald-600" : "text-slate-500"}`}>{value}</div>
    </div>
  );
}
