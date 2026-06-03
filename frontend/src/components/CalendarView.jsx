import { useEffect, useState } from "react";
import { api } from "../api.js";
import { DOT, fmtTND } from "../colors.js";
import ExcursionEditor from "./ExcursionEditor.jsx";

export default function CalendarView({ year, month, setYear, setMonth, readOnly = false }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dests, setDests] = useState([]);
  const [editor, setEditor] = useState(null); // {bus, iso}

  const reload = () => {
    setError("");
    return api.calendar(year, month).then(setData).catch((e) => setError(e.message));
  };

  useEffect(() => {
    let alive = true;
    setLoading(true);
    reload().finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [year, month]);

  useEffect(() => { api.destinations().then(setDests).catch(() => {}); }, []);

  const prev = () => { if (month === 1) { setMonth(12); setYear(year - 1); } else setMonth(month - 1); };
  const next = () => { if (month === 12) { setMonth(1); setYear(year + 1); } else setMonth(month + 1); };

  const openDay = (bus, day) => {
    const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    setEditor({ bus, iso });
  };

  let region = null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <button onClick={prev} className="rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow hover:bg-slate-50">← Préc.</button>
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">{data?.label || `${month}/${year}`}</h1>
        <button onClick={next} className="rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow hover:bg-slate-50">Suiv. →</button>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
        {Object.entries(DOT).map(([k, v]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className={`inline-block h-3 w-3 rounded-full ${v.bg}`} /> {v.label}
          </span>
        ))}
        <span className="text-slate-400">· cliquez une case jour pour {readOnly ? "voir" : "ajouter / modifier"} les excursions</span>
      </div>

      {error && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</div>}
      {loading && <div className="py-10 text-center text-slate-400">Chargement…</div>}

      {data && !loading && (
        <>
          <div className="overflow-x-auto rounded-2xl bg-white shadow-lg ring-1 ring-slate-200">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="bg-[#1a3a5c] text-white">
                  <th className="sticky left-0 z-10 bg-[#1a3a5c] px-3 py-2 text-left font-semibold min-w-[190px]">Véhicule</th>
                  {Array.from({ length: data.days_in_month }, (_, i) => (
                    <th key={i} className="w-7 px-0.5 py-2 text-center font-medium">{i + 1}</th>
                  ))}
                  <th className="px-3 py-2 text-right font-semibold min-w-[120px]">Net Mois</th>
                  <th className="px-3 py-2 text-center font-semibold min-w-[70px]">%</th>
                  <th className="px-3 py-2 text-right font-semibold min-w-[90px]">Distance</th>
                </tr>
              </thead>
              <tbody>
                {data.buses.map((bus) => {
                  const sep = bus.region !== region;
                  region = bus.region;
                  const net = bus.net;
                  return (
                    <>
                      {sep && (
                        <tr key={`r-${bus.region}`}>
                          <td colSpan={data.days_in_month + 4}
                              className="bg-sky-700 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-white">
                            {bus.region}
                          </td>
                        </tr>
                      )}
                      <tr key={bus.id} className="border-b border-slate-100 odd:bg-slate-50/60 hover:bg-sky-50">
                        <td className="sticky left-0 z-10 bg-inherit px-3 py-1.5 font-semibold text-slate-700 truncate max-w-[190px]" title={bus.name}>
                          {bus.name}
                        </td>
                        {Array.from({ length: data.days_in_month }, (_, i) => {
                          const c = bus.days[i + 1];
                          return (
                            <td key={i} className="px-0.5 py-1.5 text-center">
                              {c ? (
                                <button onClick={() => openDay(bus, i + 1)} title={`${DOT[c]?.label} — voir le détail`}
                                  className={`inline-block h-3.5 w-3.5 rounded-full ${DOT[c]?.bg || "bg-slate-300"} transition hover:scale-150 hover:ring-2 hover:ring-sky-300`} />
                              ) : (
                                <button onClick={() => openDay(bus, i + 1)} className="block h-3.5 w-3.5 opacity-0 hover:opacity-100" aria-label="jour" />
                              )}
                            </td>
                          );
                        })}
                        <td className="px-3 py-1.5 text-right">
                          <span className={`rounded-md px-2 py-0.5 font-bold ${net >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
                            {fmtTND(net)}
                          </span>
                          {bus.is_estimated && <span className="ml-1 align-middle text-[9px] font-bold uppercase text-amber-500" title="Carburant estimé">est</span>}
                        </td>
                        <td className={`px-3 py-1.5 text-center font-semibold ${net >= 0 ? "text-emerald-600" : "text-rose-600"}`}>{bus.pct}</td>
                        <td className="px-3 py-1.5 text-right text-slate-500">{bus.distance > 0 ? `${bus.distance.toLocaleString("fr-FR")} km` : "—"}</td>
                      </tr>
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {data.summary.regions.map((r) => <SummaryCard key={r.region} r={r} />)}
            <SummaryCard r={data.summary.total} grand />
          </div>
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
