import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmtTND } from "../colors.js";
import { useAutoRefresh } from "../useAutoRefresh.js";

const MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
const YEARS = (() => { const a = []; for (let y = 2025; y <= new Date().getFullYear() + 1; y++) a.push(y); return a; })();

const covTone = (c) => (c == null ? "warn" : c >= 150 ? "good" : c >= 100 ? "warn" : "bad");
const occTone = (o) => (o >= 70 ? "good" : o >= 40 ? "warn" : "bad");

export default function AnalyticsView({ year, month, setYear, setMonth }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [sort, setSort] = useState("occ"); // occ | cov | net

  const reload = () => api.analytics(year, month).then((d) => { setData(d); setErr(""); }).catch((e) => setErr(e.message));
  useEffect(() => { setLoading(true); reload().finally(() => setLoading(false)); }, [year, month]);
  useAutoRefresh(reload);

  const s = useMemo(() => {
    if (!data) return null;
    const buses = data.buses;
    const n = buses.length;
    const withLoyer = buses.filter((b) => b.coverage != null);
    const avgCov = withLoyer.length ? Math.round(withLoyer.reduce((a, b) => a + b.coverage, 0) / withLoyer.length) : 0;
    const avgOcc = n ? Math.round(buses.reduce((a, b) => a + b.day_occ, 0) / n) : 0;
    const profitable = buses.filter((b) => b.net != null && b.net >= 0).length;
    const below = buses.filter((b) => b.coverage != null && b.coverage < 100);
    const underused = buses.filter((b) => b.day_occ < 40);
    const incomplete = buses.filter((b) => !b.time_complete);
    const totalNet = buses.reduce((a, b) => a + (b.net || 0), 0);
    const key = sort === "cov" ? (a) => (a.coverage ?? 9999) : sort === "net" ? (a) => (a.net ?? 0) : (a) => a.day_occ;
    const sorted = [...buses].sort((a, b) => key(a) - key(b));
    const best = buses.filter((b) => b.net != null).sort((a, b) => b.net - a.net)[0];
    const worst = [...buses].sort((a, b) => a.day_occ - b.day_occ)[0];
    return { buses, sorted, n, avgCov, avgOcc, profitable, below, underused, incomplete, totalNet, best, worst };
  }, [data, sort]);

  const prev = () => { if (month === 1) { setMonth(12); setYear(year - 1); } else setMonth(month - 1); };
  const next = () => { if (month === 12) { setMonth(1); setYear(year + 1); } else setMonth(month + 1); };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">📈 Analyse</h1>
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

      <p className="text-xs text-slate-400">
        Deux mesures exactes par véhicule : la <b>rentabilité</b> (recettes ÷ loyer) et l'<b>occupation</b> (jours travaillés ÷ jours sous contrat, + heures réelles d'après les horaires saisis).
      </p>

      {err && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{err}</div>}
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
            <Kpi label="Occupation moyenne" big={`${s.avgOcc}%`} sub="jours travaillés / sous contrat" tone={occTone(s.avgOcc)}>
              <Bar pct={s.avgOcc} tone={occTone(s.avgOcc)} />
            </Kpi>
            <Kpi label="Couverture moyenne du loyer" big={`${s.avgCov}%`} sub="recettes ÷ loyer" tone={covTone(s.avgCov)}>
              <Bar pct={Math.min(s.avgCov, 200) / 2} tone={covTone(s.avgCov)} />
            </Kpi>
            <Kpi label="Véhicules rentables" big={`${s.profitable}/${s.n}`} sub={`${s.below.length} sous le loyer`} tone={s.profitable >= s.n / 2 ? "good" : "bad"} />
            <Kpi label="Résultat net flotte" big={fmtTND(s.totalNet)} sub={data.label} tone={s.totalNet >= 0 ? "good" : "bad"} />
          </div>

          {s.underused.length > 0 && (
            <Insight tone="bad">
              🅿️ <b>{s.underused.length} véhicule{s.underused.length > 1 ? "s" : ""}</b> sous-utilisé{s.underused.length > 1 ? "s" : ""} (occupation &lt; 40 %) — loué{s.underused.length > 1 ? "s" : ""} mais souvent à l'arrêt.
              {s.worst && <> Le plus faible : <b>{s.worst.name}</b> ({s.worst.day_occ}%).</>}
            </Insight>
          )}
          {s.incomplete.length > 0 && (
            <Insight tone="warn">
              ⏱️ {s.incomplete.length} véhicule{s.incomplete.length > 1 ? "s ont" : " a"} des sorties sans horaire saisi — l'occupation en <b>jours</b> reste exacte, mais les <b>heures</b> de ces sorties ne sont pas comptées.
            </Insight>
          )}

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-400">Trier par :</span>
            {[["occ", "Occupation"], ["cov", "Couverture du loyer"], ["net", "Résultat net"]].map(([k, l]) => (
              <button key={k} onClick={() => setSort(k)} className={`rounded-lg px-3 py-1 font-semibold ${sort === k ? "bg-[#1a3a5c] text-white" : "bg-white text-slate-600 shadow-sm"}`}>{l}</button>
            ))}
          </div>

          <div className="space-y-2">{s.sorted.map((b) => <BusRow key={b.id} b={b} />)}</div>

          <div className="grid gap-3 sm:grid-cols-2">
            {s.best && <Highlight emoji="🏆" title="Meilleur résultat" name={s.best.name} value={fmtTND(s.best.net)} good />}
            {s.worst && <Highlight emoji="🅿️" title="Plus faible occupation" name={s.worst.name} value={`${s.worst.day_occ}% des jours`} />}
          </div>
        </>
      )}
    </div>
  );
}

function BusRow({ b }) {
  const oc = occTone(b.day_occ), cc = covTone(b.coverage);
  const ocBar = oc === "good" ? "bg-emerald-500" : oc === "warn" ? "bg-amber-400" : "bg-rose-500";
  const ccBar = cc === "good" ? "bg-emerald-500" : cc === "warn" ? "bg-amber-400" : "bg-rose-500";
  const inRed = b.net != null && b.net < 0;
  const belowRent = b.coverage != null && b.coverage < 100;
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-bold text-slate-700">{b.name}</div>
          <div className="text-[11px] text-slate-400">{b.region} · {b.type} · {b.trips} sortie{b.trips > 1 ? "s" : ""}</div>
        </div>
        <div className="flex items-center gap-2">
          {inRed && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-700">En perte</span>}
          {belowRent && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700">Sous le loyer</span>}
          {b.day_occ < 40 && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-700">Sous-utilisé</span>}
          {b.net != null && <span className={`rounded-md px-2 py-0.5 text-sm font-extrabold ${b.net >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>{fmtTND(b.net)}{b.is_estimated ? " *" : ""}</span>}
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {/* occupation (time) */}
        <div>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-bold text-[#1a3a5c]">Occupation {b.day_occ}%</span>
            <span className="text-slate-400">{b.worked_days}/{b.covered_days} jours</span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div className={ocBar} style={{ width: `${Math.min(b.day_occ, 100)}%`, height: "100%" }} />
          </div>
        </div>
        {/* rent coverage */}
        <div>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-bold text-[#1a3a5c]">{b.coverage != null ? `Loyer couvert ${b.coverage}%` : "Loyer non défini"}</span>
            <span className="text-slate-400">{fmtTND(b.revenue)} / {fmtTND(b.loyer)}</span>
          </div>
          <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div className={ccBar} style={{ width: `${Math.min(b.coverage ?? 0, 200) / 2}%`, height: "100%" }} />
            <div className="absolute top-0 h-full w-0.5 bg-slate-500/60" style={{ left: "50%" }} title="100 % = loyer remboursé" />
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        {b.avg_hours != null && <span>⏱️ {b.avg_hours} h/jour en moyenne</span>}
        {b.timed_hours > 0 && <span>{b.timed_hours} h d'activité</span>}
        {b.multi_days > 0 && <span>📅 {b.multi_days} j en circuit</span>}
        {!b.time_complete && <span className="text-amber-500">⏱️ {b.missing_time} sortie(s) sans horaire</span>}
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
