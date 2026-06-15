import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmtTND } from "../colors.js";
import { useAutoRefresh } from "../useAutoRefresh.js";

const MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
const YEARS = (() => { const a = []; for (let y = 2025; y <= new Date().getFullYear() + 1; y++) a.push(y); return a; })();

// Financial performance per vehicle — 100% precise from recorded revenue + loyer
// (no trip durations needed). Headline = "rent coverage" (revenue / loyer).
function analyzeBus(bus) {
  const c = bus.contract || {};
  const rev = c.revenue ?? 0, loyer = c.loyer ?? 0, fuel = c.fuel ?? 0;
  const net = bus.net;
  let activeDays = 0;                       // days with at least one trip (precise)
  for (const d of bus.covered_days || []) { const cc = bus.days[d]; if (cc && cc !== "red") activeDays++; }
  const coverage = loyer > 0 ? Math.round((rev / loyer) * 100) : null;  // % of rent covered
  const revPerDay = activeDays ? Math.round(rev / activeDays) : 0;
  const belowRent = coverage != null && coverage < 100;
  const inRed = net != null && net < 0;
  let reason = null;
  if (inRed || belowRent) {
    if (rev < loyer * 0.4) reason = "Très peu de recettes face au loyer";
    else if (rev < loyer) reason = "Recettes sous le niveau du loyer";
    else reason = "Carburant + loyer dépassent les recettes";
  }
  return { ...bus, rev, loyer, fuel, net, activeDays, coverage, revPerDay, belowRent, inRed, reason };
}

const covTone = (c) => (c == null ? "warn" : c >= 150 ? "good" : c >= 100 ? "warn" : "bad");

export default function AnalyticsView({ year, month, setYear, setMonth }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("cov"); // cov | net

  const reload = () => api.calendar(year, month).then(setData).catch(() => {});
  useEffect(() => { setLoading(true); reload().finally(() => setLoading(false)); }, [year, month]);
  useAutoRefresh(reload);

  const s = useMemo(() => {
    if (!data) return null;
    const buses = data.buses.map(analyzeBus);
    const n = buses.length;
    const withLoyer = buses.filter((b) => b.coverage != null);
    const avgCov = withLoyer.length ? Math.round(withLoyer.reduce((a, b) => a + b.coverage, 0) / withLoyer.length) : 0;
    const profitable = buses.filter((b) => b.net != null && b.net >= 0).length;
    const below = buses.filter((b) => b.belowRent);
    const sorted = [...buses].sort((a, b) => (sort === "cov" ? (a.coverage ?? 9999) - (b.coverage ?? 9999) : (a.net ?? 0) - (b.net ?? 0)));
    const best = buses.filter((b) => b.net != null).sort((a, b) => b.net - a.net)[0];
    const worst = [...withLoyer].sort((a, b) => a.coverage - b.coverage)[0];
    return { buses, sorted, n, avgCov, profitable, below, best, worst, totalNet: data.summary.total.net };
  }, [data, sort]);

  const prev = () => { if (month === 1) { setMonth(12); setYear(year - 1); } else setMonth(month - 1); };
  const next = () => { if (month === 12) { setMonth(1); setYear(year + 1); } else setMonth(month + 1); };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">📈 Analyse de rentabilité</h1>
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

      <p className="text-xs text-slate-400">La <b>couverture du loyer</b> = recettes ÷ loyer. Au-dessus de 100 %, le véhicule rembourse son loyer ; en dessous, il coûte plus qu'il ne rapporte. Chiffres exacts, calculés sur les recettes réelles.</p>

      {loading && <div className="animate-pulse space-y-3"><div className="h-28 rounded-2xl bg-slate-100" /><div className="h-64 rounded-2xl bg-slate-100" /></div>}

      {!loading && s && s.n === 0 && (
        <div className="rounded-2xl bg-white px-6 py-14 text-center shadow ring-1 ring-slate-200">
          <div className="text-3xl">📊</div>
          <div className="mt-2 font-semibold text-slate-600">Aucun véhicule sous contrat ce mois-ci</div>
        </div>
      )}

      {!loading && s && s.n > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Couverture moyenne du loyer" big={`${s.avgCov}%`} sub="recettes ÷ loyer" tone={covTone(s.avgCov)}>
              <Bar pct={Math.min(s.avgCov, 200) / 2} tone={covTone(s.avgCov)} />
            </Kpi>
            <Kpi label="Véhicules rentables" big={`${s.profitable}/${s.n}`} sub={`${s.n - s.profitable} en perte`} tone={s.profitable >= s.n / 2 ? "good" : "bad"} />
            <Kpi label="Ne couvrent pas leur loyer" big={`${s.below.length}`} sub="recettes < loyer" tone={s.below.length ? "bad" : "good"} />
            <Kpi label="Résultat net flotte" big={fmtTND(s.totalNet)} sub={data.label} tone={s.totalNet >= 0 ? "good" : "bad"} />
          </div>

          {s.below.length > 0 && (
            <Insight tone="bad">
              💸 <b>{s.below.length} véhicule{s.below.length > 1 ? "s" : ""}</b> ne couvre{s.below.length > 1 ? "nt" : ""} pas son loyer ce mois — il{s.below.length > 1 ? "s" : ""} coûte{s.below.length > 1 ? "nt" : ""} plus qu'il{s.below.length > 1 ? "s ne rapportent" : " ne rapporte"}.
              {s.worst && <> Le plus faible : <b>{s.worst.name}</b> ({s.worst.coverage}% du loyer).</>}
            </Insight>
          )}

          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Trier par :</span>
            <button onClick={() => setSort("cov")} className={`rounded-lg px-3 py-1 font-semibold ${sort === "cov" ? "bg-[#1a3a5c] text-white" : "bg-white text-slate-600 shadow-sm"}`}>Couverture du loyer</button>
            <button onClick={() => setSort("net")} className={`rounded-lg px-3 py-1 font-semibold ${sort === "net" ? "bg-[#1a3a5c] text-white" : "bg-white text-slate-600 shadow-sm"}`}>Résultat net</button>
          </div>

          <div className="space-y-2">
            {s.sorted.map((b) => <BusRow key={b.id} b={b} />)}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {s.best && <Highlight emoji="🏆" title="Meilleur résultat" name={s.best.name} value={fmtTND(s.best.net)} good />}
            {s.worst && <Highlight emoji="⚠️" title="Plus faible couverture" name={s.worst.name} value={`${s.worst.coverage}% du loyer`} />}
          </div>
        </>
      )}
    </div>
  );
}

function BusRow({ b }) {
  const tone = covTone(b.coverage);
  const c = tone === "good" ? "bg-emerald-500" : tone === "warn" ? "bg-amber-400" : "bg-rose-500";
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-bold text-slate-700">{b.name}</div>
          <div className="text-[11px] text-slate-400">{b.region} · {b.type}</div>
        </div>
        <div className="flex items-center gap-2">
          {b.inRed && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-700">En perte</span>}
          {b.belowRent && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700">Sous le loyer</span>}
          {b.net != null && <span className={`rounded-md px-2 py-0.5 text-sm font-extrabold ${b.net >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>{fmtTND(b.net)}</span>}
        </div>
      </div>

      {/* rent-coverage bar with a break-even marker at 100% */}
      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-bold text-[#1a3a5c]">{b.coverage != null ? `${b.coverage}% du loyer couvert` : "Loyer non défini"}</span>
          <span className="text-slate-400">{b.activeDays} jour{b.activeDays > 1 ? "s" : ""} avec sortie</span>
        </div>
        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div className={c} style={{ width: `${Math.min(b.coverage ?? 0, 200) / 2}%`, height: "100%" }} />
          <div className="absolute top-0 h-full w-0.5 bg-slate-500/60" style={{ left: "50%" }} title="100 % = loyer remboursé" />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <span>Recettes <b className="text-slate-700">{fmtTND(b.rev)}</b></span>
        <span>Loyer <b className="text-slate-700">{fmtTND(b.loyer)}</b></span>
        {b.activeDays > 0 && <span>Recette/jour <b className="text-slate-700">{fmtTND(b.revPerDay)}</b></span>}
        {b.reason && <span className="text-rose-500">⚠️ {b.reason}</span>}
      </div>
    </div>
  );
}

const TONE = { good: "text-emerald-600", warn: "text-amber-600", bad: "text-rose-600" };
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
