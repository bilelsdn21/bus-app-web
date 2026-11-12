import { Fragment, useEffect, useRef, useState } from "react";
import { api, downloadBlob } from "../api.js";
import { DOT, fmtTND } from "../colors.js";
import ExcursionEditor from "./ExcursionEditor.jsx";
import { useAutoRefresh } from "../useAutoRefresh.js";

// French weekday abbreviations, indexed by JS getDay() (0=Sunday … 6=Saturday)
const WEEKDAYS_FR = ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"];
const MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
// Selectable years: from 2025 up to next year (extends automatically over time).
const YEARS = (() => { const a = []; for (let y = 2025; y <= new Date().getFullYear() + 1; y++) a.push(y); return a; })();
// "2026-06-18" -> "18/06"
const dm = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

export default function CalendarView({ year, month, setYear, setMonth, readOnly = false, username = "", onOpenContract }) {
  // paint instantly from the last known answer (if any), then refresh in the background
  const [data, setData] = useState(() => api.peek.calendar(year, month));
  const [loading, setLoading] = useState(() => !api.peek.calendar(year, month));
  const [error, setError] = useState("");
  const [dests, setDests] = useState(() => api.peek.destinations() || []);
  const [editor, setEditor] = useState(null); // {bus, iso}

  const reload = () => {
    setError("");
    return api.calendar(year, month).then(setData).catch((e) => setError(e.message));
  };

  useEffect(() => {
    let alive = true;
    const known = api.peek.calendar(year, month);
    if (known) { setData(known); setLoading(false); } else setLoading(true);
    reload().finally(() => alive && setLoading(false));
    // warm the neighbouring months so the arrows feel instant
    const t = setTimeout(() => {
      const py = month === 1 ? year - 1 : year, pm = month === 1 ? 12 : month - 1;
      const ny = month === 12 ? year + 1 : year, nm = month === 12 ? 1 : month + 1;
      api.calendar(ny, nm).catch(() => {});
      api.calendar(py, pm).catch(() => {});
    }, 1200);
    return () => { alive = false; clearTimeout(t); };
  }, [year, month]);

  useEffect(() => { api.destinations().then(setDests).catch(() => {}); }, []);
  useAutoRefresh(reload);   // refetch when the app regains focus / reconnects (mobile)

  const prev = () => { if (month === 1) { setMonth(12); setYear(year - 1); } else setMonth(month - 1); };
  const next = () => { if (month === 12) { setMonth(1); setYear(year + 1); } else setMonth(month + 1); };

  const [exporting, setExporting] = useState(false);
  const exportExcel = async () => {
    setExporting(true); setError("");
    try {
      const blob = await api.exportCalendar(year, month);
      downloadBlob(blob, `Calendrier_${MONTHS_FR[month - 1]}_${year}.xlsx`);
    } catch (e) { setError(e.message); }
    finally { setExporting(false); }
  };

  const openDay = (bus, day) => {
    const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    setEditor({ bus, iso });
  };

  // today's day number when the viewed month is the current one (else null)
  const nowD = new Date();
  const todayDay = data && data.year === nowD.getFullYear() && data.month === nowD.getMonth() + 1 ? nowD.getDate() : null;

  // on a phone the table is wider than the screen: open it scrolled to today
  const scroller = useRef(null);
  useEffect(() => {
    const box = scroller.current;
    if (!box || loading || !todayDay) return;
    const th = box.querySelector(`th[data-day="${todayDay}"]`);
    const first = box.querySelector("th");
    if (th && first) box.scrollLeft = Math.max(0, th.offsetLeft - first.offsetWidth - th.offsetWidth * 2);
  }, [loading, data?.year, data?.month, todayDay]);

  let region = null;
  const todayLabel = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const monthNet = data?.summary?.total?.net;

  return (
    <div className="space-y-5">
      {/* personalized cockpit band */}
      <div className="overflow-hidden rounded-2xl bg-gradient-to-r from-[#13294a] via-[#1a3a5c] to-[#21507e] px-5 py-4 text-white shadow-lg ring-1 ring-amber-400/20">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-base font-bold sm:text-lg">Bonjour {username || ""} <span className="text-amber-300">👋</span></div>
            <div className="text-[11px] capitalize text-sky-200">{todayLabel}</div>
          </div>
          {monthNet != null && (
            <div className="text-right">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-amber-300">{data.label} · Net</div>
              <div className={`text-xl font-extrabold ${monthNet >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{fmtTND(monthNet)}</div>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button onClick={prev} title="Mois précédent" className="rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow hover:bg-slate-50">←</button>
          <div className="flex items-center gap-1.5">
            <select value={month} onChange={(e) => setMonth(Number(e.target.value))}
              className="cursor-pointer rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm font-bold text-[#1a3a5c] shadow-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100 sm:text-base">
              {MONTHS_FR.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </select>
            <select value={year} onChange={(e) => setYear(Number(e.target.value))}
              className="cursor-pointer rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm font-bold text-[#1a3a5c] shadow-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100 sm:text-base">
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <button onClick={next} title="Mois suivant" className="rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow hover:bg-slate-50">→</button>
        </div>
        <button onClick={exportExcel} disabled={exporting || !data}
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow hover:bg-emerald-700 disabled:opacity-50">
          {exporting ? "Export…" : "⬇️ Exporter Excel"}
        </button>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
        {Object.entries(DOT).map(([k, v]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className={`inline-block h-3 w-3 rounded-full ${v.bg}`} /> {v.label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="cell-out inline-block h-3 w-3 rounded ring-1 ring-slate-200" /> Hors contrat
        </span>
        <span className="text-slate-400">· touchez une case jour pour {readOnly ? "voir" : "ajouter / modifier"} les excursions</span>
      </div>

      {error && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</div>}
      {loading && <CalendarSkeleton />}

      {data && !loading && data.buses.length === 0 && (
        <div className="rounded-2xl bg-white px-6 py-14 text-center shadow ring-1 ring-slate-200">
          <div className="text-3xl">🗓️</div>
          <div className="mt-2 font-semibold text-slate-600">Aucun véhicule sous contrat ce mois-ci</div>
          <div className="mt-1 text-sm text-slate-400">Créez un contrat (onglet Contrats) couvrant cette période pour afficher un véhicule ici.</div>
        </div>
      )}

      {data && !loading && data.buses.length > 0 && (
        <>
          <div ref={scroller} className="scroll-x max-h-[72vh] overflow-auto rounded-2xl bg-white shadow-lg ring-1 ring-slate-200">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="text-white">
                  <th className="sticky left-0 top-0 z-30 border-r border-white/20 bg-[#1a3a5c] px-3 py-2 text-left font-semibold min-w-[128px] sm:min-w-[190px]">Véhicule</th>
                  {Array.from({ length: data.days_in_month }, (_, i) => {
                    const day = i + 1;
                    const dow = new Date(data.year, data.month - 1, day).getDay(); // 0=dim … 6=sam
                    const weekend = dow === 0 || dow === 6;
                    return (
                      <th key={i} data-day={day} className={`sticky top-0 z-20 w-9 min-w-[36px] border-r border-white/10 px-0.5 py-1 text-center font-medium sm:w-7 sm:min-w-0 ${day === todayDay ? "bg-amber-500 text-[#13294a]" : weekend ? "bg-[#24507a]" : "bg-[#1a3a5c]"}`}>
                        <div className={`text-[9px] font-semibold uppercase leading-none ${weekend ? "text-amber-300" : "text-sky-300"}`}>{WEEKDAYS_FR[dow]}</div>
                        <div className="leading-tight">{day}</div>
                      </th>
                    );
                  })}
                  <th className="sticky top-0 z-20 border-l border-white/20 bg-[#1a3a5c] px-3 py-2 text-right font-semibold min-w-[120px]">Net Mois</th>
                  <th className="sticky top-0 z-20 bg-[#1a3a5c] px-3 py-2 text-center font-semibold min-w-[70px]">%</th>
                  <th className="sticky top-0 z-20 bg-[#1a3a5c] px-3 py-2 text-right font-semibold min-w-[90px]">Distance</th>
                </tr>
              </thead>
              <tbody>
                {data.buses.map((bus) => {
                  const sep = bus.region !== region;
                  region = bus.region;
                  const net = bus.net;
                  const covered = bus.covered_days ? new Set(bus.covered_days) : null;
                  const seg = bus.segment;   // set only when the vehicle changed region
                  return (
                    <Fragment key={bus.key || bus.id}>
                      {sep && (
                        <tr key={`r-${bus.region}`}>
                          <td colSpan={data.days_in_month + 4}
                              className="bg-sky-700 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-white">
                            {bus.region}
                          </td>
                        </tr>
                      )}
                      <tr className="border-b border-slate-200 bg-white odd:bg-slate-50 hover:bg-sky-50">
                        <td className="sticky left-0 z-10 max-w-[128px] border-r border-slate-300 bg-inherit p-0 sm:max-w-[190px]">
                          <button onClick={() => onOpenContract?.(bus.id)} title={`Voir le contrat — ${bus.name}`}
                            className="block w-full truncate px-2 py-2.5 text-left text-[11px] font-semibold text-slate-700 sm:px-3 sm:py-1.5 sm:text-xs transition hover:bg-sky-50 hover:text-sky-700">
                            {bus.name}
                            {seg && (
                              <span className="mt-0.5 flex items-center gap-1 text-[9px] font-bold uppercase tracking-wide text-amber-600"
                                    title={seg.contract_change ? `Changement de contrat/région : ${seg.region} du ${dm(seg.from)} au ${dm(seg.to)} (${seg.days} j). Cette ligne ne contient que ce contrat.` : `Ce véhicule a changé de région : il est resté à ${seg.region} du ${dm(seg.from)} au ${dm(seg.to)} (${seg.days} j). Cette ligne ne contient que ces jours-là.`}>
                                <span className="rounded bg-amber-100 px-1 py-px text-amber-700">{seg.index + 1}/{seg.count}</span>
                                {dm(seg.from)}→{dm(seg.to)}
                                {seg.next_region && <span className="text-slate-400">↷ {seg.next_region}</span>}
                                {seg.prev_region && <span className="text-slate-400">↶ {seg.prev_region}</span>}
                              </span>
                            )}
                          </button>
                        </td>
                        {Array.from({ length: data.days_in_month }, (_, i) => {
                          const day = i + 1;
                          const c = bus.days[day];
                          const elsewhere = seg && (day < seg.day_from || day > seg.day_to);  // autre région
                          const out = covered && !covered.has(day);   // hors contrat
                          const dow = new Date(data.year, data.month - 1, day).getDay();
                          const weekend = dow === 0 || dow === 6;
                          // amber rule exactly on the move date, so the switch is visible at a glance
                          const edge = seg && !elsewhere
                            ? (seg.index > 0 && day === seg.day_from ? "border-l-2 border-l-amber-400"
                              : seg.index < seg.count - 1 && day === seg.day_to ? "border-r-2 border-r-amber-400" : "")
                            : "";
                          const outTitle = elsewhere
                            ? `Hors région — le véhicule était à ${day < seg.day_from ? seg.prev_region : seg.next_region} ce jour-là`
                            : "Hors contrat";
                          return (
                            <td key={i} className={`border-r border-slate-200 px-0.5 py-2 text-center sm:py-1.5 ${edge} ${out ? "cell-out" : day === todayDay ? "today-col" : weekend ? "bg-slate-100/50" : ""}`}>
                              {c ? (
                                <button onClick={() => openDay(bus, day)} title={`${DOT[c]?.label} — voir le détail`}
                                  className={`inline-block h-4 w-4 rounded-full sm:h-3.5 sm:w-3.5 ${DOT[c]?.bg || "bg-slate-300"} transition active:scale-125 hover:scale-150 hover:ring-2 hover:ring-sky-300`} />
                              ) : out ? (
                                <span className="inline-block h-3.5 w-3.5" title={outTitle} aria-hidden="true" />
                              ) : (
                                <button onClick={() => openDay(bus, day)} className="mx-auto block h-5 w-5 opacity-0 hover:opacity-100 active:opacity-100 sm:h-3.5 sm:w-3.5" aria-label="jour" />
                              )}
                            </td>
                          );
                        })}
                        <td className="border-l border-slate-300 px-3 py-1.5 text-right">
                          {net == null ? (
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-400" title="Aucun contrat pour ce mois">Pas de contrat</span>
                          ) : (
                            <span className={`rounded-md px-2 py-0.5 font-bold ${net >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}
                              title={seg ? (seg.prorated
                                ? `Part ${seg.region} du ${dm(seg.from)} au ${dm(seg.to)} : revenu ${fmtTND(bus.revenue)} (sorties de ces jours-là) − loyer ${fmtTND(bus.loyer)} − carburant ${fmtTND(bus.fuel)}. Loyer et carburant au prorata des ${seg.days} jours ; total du contrat : ${fmtTND(bus.contract.net)}.`
                                : `Contrat ${dm(seg.from)} → ${dm(seg.to)} (${seg.region}) : revenu ${fmtTND(bus.revenue)} − loyer ${fmtTND(bus.loyer)} − carburant ${fmtTND(bus.fuel)}.`) : undefined}>
                              {fmtTND(net)}
                            </span>
                          )}
                          {seg?.prorated && <span className="ml-1 align-middle text-[9px] font-bold uppercase text-amber-500" title="Part de la période — loyer et carburant au prorata des jours">part</span>}
                          {bus.is_estimated && <span className="ml-1 align-middle text-[9px] font-bold uppercase text-amber-500" title="Carburant estimé">est</span>}
                        </td>
                        <td className={`px-3 py-1.5 text-center font-semibold ${net == null ? "text-slate-300" : net >= 0 ? "text-emerald-600" : "text-rose-600"}`}>{bus.pct}</td>
                        <td className="px-3 py-1.5 text-right text-slate-500">{bus.distance > 0 ? `${bus.distance.toLocaleString("fr-FR")} km` : "—"}</td>
                      </tr>
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {data.summary.regions.map((r) => <SummaryCard key={r.region} r={r} />)}
            <SummaryCard r={data.summary.total} grand />
          </div>

          {data.summary.shared > 0 && (
            <div className="rounded-xl bg-slate-50 px-4 py-3 text-[11px] text-slate-500 ring-1 ring-slate-200">
              <span className="font-bold text-amber-600">↷ {data.summary.shared} véhicule{data.summary.shared > 1 ? "s ont" : " a"} changé de région ce mois-ci.</span>{" "}
              Chacun apparaît une fois par région, sur ses jours à lui uniquement. Le revenu est affecté à la date
              exacte de chaque sortie — rien n'est déplacé rétroactivement ; le loyer et le carburant sont répartis
              au prorata des jours (mention <span className="font-bold uppercase text-amber-500">part</span>).
              Les deux lignes additionnées redonnent exactement le total du contrat.
            </div>
          )}

          {data.summary.rentals && data.summary.rentals.total > 0 && (
            <div className="rounded-2xl bg-amber-50 p-4 shadow ring-1 ring-amber-200">
              <div className="text-xs font-bold uppercase tracking-wider text-amber-700">
                🚐 Location de véhicules supplémentaires
              </div>
              <p className="mt-0.5 text-[11px] text-amber-600">Pour information — n'affecte pas le Net ci-dessus (véhicules loués en renfort, hors flotte, voir l'onglet Loués).</p>
              <div className="mt-3 flex flex-wrap gap-4">
                {data.summary.rentals.by_region.map((r) => (
                  <div key={r.region}>
                    <div className="text-[11px] font-semibold text-amber-600">{r.region}</div>
                    <div className="text-sm font-bold text-amber-800">− {fmtTND(r.cost)}</div>
                  </div>
                ))}
                <div className="ml-auto text-right">
                  <div className="text-[11px] font-semibold text-amber-600">Total</div>
                  <div className="text-sm font-extrabold text-amber-800">− {fmtTND(data.summary.rentals.total)}</div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {editor && (
        <ExcursionEditor
          bus={editor.bus} dayISO={editor.iso} dests={dests} readOnly={readOnly}
          onClose={() => setEditor(null)}
          onChanged={reload}
        />
      )}
    </div>
  );
}

function DayDetail({ d, onClose }) {
  const books = (d.rows || []).filter((r) => r.type === "Booking");
  const unavail = (d.rows || []).filter((r) => r.type !== "Booking");
  const totalRevenue = books.reduce((s, r) => s + (r.total || 0), 0);
  const dateLabel = new Date(d.iso + "T00:00:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between rounded-t-2xl bg-[#1a3a5c] px-5 py-4 text-white">
          <div>
            <div className="text-sm font-bold">{d.bus.name}</div>
            <div className="text-xs capitalize text-sky-200">{dateLabel}</div>
          </div>
          <button onClick={onClose} className="text-white/70 hover:text-white">✕</button>
        </div>

        <div className="max-h-[70vh] space-y-3 overflow-y-auto p-5">
          {d.loading && <div className="py-6 text-center text-slate-400">Chargement…</div>}
          {!d.loading && d.rows?.length === 0 && (
            <div className="rounded-xl bg-slate-50 py-6 text-center text-sm text-slate-400">Aucune activité ce jour.</div>
          )}

          {unavail.map((r, i) => (
            <div key={`u${i}`} className="rounded-xl border-l-4 border-rose-400 bg-rose-50 px-4 py-3">
              <div className="text-sm font-bold text-rose-700">🔴 Indisponible — {r.destination}</div>
              {r.heure_debut && <div className="text-xs text-rose-600">{r.heure_debut}{r.heure_fin ? ` → ${r.heure_fin}` : ""}</div>}
            </div>
          ))}

          {books.map((r, i) => (
            <div key={`b${i}`} className="rounded-xl border-l-4 border-emerald-400 bg-white px-4 py-3 shadow-sm ring-1 ring-slate-100">
              <div className="flex items-center justify-between">
                <div className="text-sm font-bold text-slate-700">{r.destination || "—"}</div>
                <div className="text-sm font-extrabold text-emerald-600">{fmtTND(r.total || 0)}</div>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                {(r.heure_debut || r.heure_fin) && <span>🕐 {r.heure_debut || "?"} → {r.heure_fin || "?"}</span>}
                {r.client && <span>👤 {r.client}</span>}
                {r.pax > 0 && <span>👥 {r.pax} pax</span>}
                {r.unit_price > 0 && <span>💵 {fmtTND(r.unit_price)}</span>}
              </div>
              {r.notes && <div className="mt-1 text-xs italic text-slate-400">{r.notes}</div>}
            </div>
          ))}

          {books.length > 0 && (
            <div className="flex items-center justify-between rounded-xl bg-[#1a3a5c] px-4 py-3 text-white">
              <span className="text-sm font-semibold">Total du jour</span>
              <span className="text-base font-extrabold">{fmtTND(totalRevenue)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ r, grand }) {
  const pos = r.net >= 0;
  return (
    <div className={`rounded-2xl p-4 shadow-lg ring-1 ${grand ? "bg-[#1a3a5c] text-white ring-[#1a3a5c]" : "bg-white ring-slate-200"}`}>
      <div className={`text-xs font-bold uppercase tracking-wider ${grand ? "text-sky-200" : "text-slate-400"}`}>{r.region}</div>
      <div className="mt-2 flex items-end justify-between">
        <div>
          <div className={`text-[11px] ${grand ? "text-sky-200" : "text-slate-400"}`}>Loyers</div>
          <div className="text-sm font-semibold">{fmtTND(r.loyer)}</div>
        </div>
        <div className="text-right">
          <div className={`text-[11px] ${grand ? "text-sky-200" : "text-slate-400"}`}>Net</div>
          <div className={`text-lg font-extrabold ${grand ? (pos ? "text-emerald-300" : "text-rose-300") : (pos ? "text-emerald-600" : "text-rose-600")}`}>
            {fmtTND(r.net)} <span className="text-xs font-semibold">({r.pct})</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function CalendarSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="overflow-hidden rounded-2xl bg-white shadow-lg ring-1 ring-slate-200">
        <div className="h-11 bg-slate-200" />
        <div className="space-y-3 p-4">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="h-4 w-44 rounded bg-slate-200" />
              <div className="h-3 flex-1 rounded bg-slate-100" />
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-24 rounded-2xl bg-slate-100" />)}
      </div>
    </div>
  );
}
