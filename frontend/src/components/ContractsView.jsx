import { useEffect, useMemo, useState } from "react";
import { api, downloadBlob } from "../api.js";
import { fmtTND } from "../colors.js";
import { useAutoRefresh } from "../useAutoRefresh.js";
import RegionAssignModal from "./RegionAssignModal.jsx";

const MONTHS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jui", "Aoû", "Sep", "Oct", "Nov", "Déc"];

export default function ContractsView({ readOnly = false, initialBusId = null }) {
  const [buses, setBuses] = useState([]);
  const [busId, setBusId] = useState("");
  const [contracts, setContracts] = useState([]);
  const [fuel, setFuel] = useState([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState(null); // contract being added/edited
  const [assign, setAssign] = useState(null); // contract whose region window is being changed
  const [okMsg, setOkMsg] = useState("");
  const [fuelYear, setFuelYear] = useState(() => new Date().getFullYear()); // fuel grid: any year
  const [exporting, setExporting] = useState(false);

  const exportExcel = async () => {
    setExporting(true); setErr("");
    try { downloadBlob(await api.exportContracts(), "Contrats.xlsx"); }
    catch (e) { setErr(e.message); }
    finally { setExporting(false); }
  };

  useEffect(() => {
    api.buses().then((b) => {
      setBuses(b);
      const pick = (initialBusId && b.some((x) => x.id === initialBusId)) ? initialBusId : b[0]?.id;
      if (pick) setBusId(String(pick));
    }).catch((e) => setErr(e.message));
  }, []);

  const reload = () => {
    if (!busId) return;
    Promise.all([api.contracts(busId), api.fuel(busId)])
      .then(([c, f]) => { setContracts(c); setFuel(f); })
      .catch((e) => setErr(e.message));
  };
  useEffect(() => { reload(); }, [busId]);
  useAutoRefresh(reload);   // refetch when the app regains focus / reconnects (mobile)

  const saveContract = async () => {
    setErr("");
    try {
      const payload = { ...form, bus_id: Number(busId), loyer: Number(form.loyer) || 0 };
      if (form.id) await api.updateContract(form.id, payload);
      else await api.createContract(payload);
      setForm(null); reload();
    } catch (e) { setErr(e.message); }
  };
  const removeContract = async (id) => {
    if (!confirm("Supprimer ce contrat ?")) return;
    await api.deleteContract(id); reload();
  };
  const saveFuel = async (year, month, field, value) => {
    setErr("");
    try {
      await api.setFuel({ bus_id: Number(busId), year, month, [field]: value === "" ? null : Number(value) });
      reload();
    } catch (e) { setErr(e.message); }
  };

  // Fuel grid: pick a year, get its 12 months — every year works the same, past or future,
  // whether or not anything was entered for it yet.
  const fuelYears = useMemo(() => {
    const now = new Date().getFullYear();
    const ys = [2025, now + 1, ...fuel.map((f) => f.year),
      ...contracts.flatMap((c) => [Number(c.start_date.slice(0, 4)), Number(c.end_date.slice(0, 4))])];
    const lo = Math.min(...ys), hi = Math.max(...ys);
    return Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  }, [fuel, contracts]);
  const fuelMonths = useMemo(() => MONTHS.map((_, i) => {
    const month = i + 1, mm = String(month).padStart(2, "0");
    const first = `${fuelYear}-${mm}-01`;
    const last = `${fuelYear}-${mm}-${String(new Date(fuelYear, month, 0).getDate()).padStart(2, "0")}`;
    const f = fuel.find((x) => x.year === fuelYear && x.month === month);
    return {
      year: fuelYear, month, estimated: f ? f.estimated : "", actual: f ? f.actual : null,
      covered: contracts.some((c) => c.start_date <= last && c.end_date >= first), // a contract touches this month
    };
  }), [fuel, contracts, fuelYear]);
  // what the year adds up to: the real amount when entered, else the estimate
  const fuelTotal = fuelMonths.reduce((t, f) => t + Number(f.actual ?? (f.estimated || 0)), 0);

  const bus = buses.find((b) => String(b.id) === String(busId));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">Contrats & Résultats</h1>
        <select value={busId} onChange={(e) => setBusId(e.target.value)}
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm">
          {buses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        {!readOnly && (
          <button onClick={() => setForm({ start_date: "", end_date: "", loyer: contracts[0]?.loyer || 0, label: "" })}
            className="rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white shadow hover:bg-[#234d77]">
            + Nouveau contrat
          </button>
        )}
        <button onClick={exportExcel} disabled={exporting}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50">
          {exporting ? "Export…" : "⬇️ Exporter tous les contrats"}
        </button>
      </div>

      {err && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{err}</div>}
      {okMsg && <div className="rounded-lg bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">{okMsg}</div>}

      {/* contract result cards */}
      <div className="grid gap-4 lg:grid-cols-2">
        {contracts.map((c) => (
          <div key={c.contract_id} className="rounded-2xl bg-white p-5 shadow-lg ring-1 ring-slate-200">
            <div className="mb-3 flex items-start justify-between">
              <div>
                <div className="font-bold text-slate-700">{c.label || "Contrat"}</div>
                <div className="text-xs text-slate-400">{c.start_date} → {c.end_date} · {c.days} jours</div>
              </div>
              <div className="flex gap-2">
                {c.is_estimated && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700">Estimé</span>}
                {!readOnly && <button onClick={() => setAssign(c)} className="-m-1 p-2 text-lg text-slate-400 hover:text-amber-600" title="Changer la région sur ce contrat" aria-label="Changer la région">🗺️</button>}
                {!readOnly && <button onClick={() => setForm({ id: c.contract_id, start_date: c.start_date, end_date: c.end_date, loyer: c.loyer, label: c.label })} className="-m-1 p-2 text-lg text-slate-400 hover:text-sky-600" title="Modifier">✎</button>}
                {!readOnly && <button onClick={() => removeContract(c.contract_id)} className="-m-1 p-2 text-lg text-slate-400 hover:text-rose-600" title="Supprimer">🗑</button>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4 sm:gap-2">
              <Stat label="Revenu" value={fmtTND(c.revenue)} />
              <Stat label="Loyer" value={fmtTND(c.loyer)} neg />
              <Stat label="Carburant" value={fmtTND(c.fuel)} neg />
              <Stat label="Net" value={fmtTND(c.net)} big pos={c.net >= 0} />
            </div>
            {c.fuel_breakdown.length > 0 && (
              <div className="mt-3 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
                {c.fuel_breakdown.map((b, i) => (
                  <span key={i} className="mr-3">
                    {MONTHS[b.month - 1]} {b.days}/{b.days_in_month}j × {fmtTND(b.fuel_month)} {b.is_actual ? "réel" : "est."} = <b>{fmtTND(b.contribution)}</b>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {contracts.length === 0 && <div className="text-sm text-slate-400">Aucun contrat. Cliquez « Nouveau contrat ».</div>}
      </div>

      {/* fuel per month */}
      <div className="rounded-2xl bg-white p-5 shadow-lg ring-1 ring-slate-200">
        <h2 className="mb-3 font-bold text-[#1a3a5c]">⛽ Carburant mensuel ({bus?.name})</h2>
        <p className="mb-3 text-xs text-slate-400">Saisissez l'<b>estimation</b> à l'avance pour les mois à venir, puis le <b>réel</b> le 1er du mois suivant. Tapez un montant et cliquez ailleurs pour enregistrer (videz la case pour effacer).</p>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {fuelYears.map((y) => (
            <button key={y} onClick={() => setFuelYear(y)}
              className={`h-9 rounded-full px-4 text-sm font-semibold ${y === fuelYear ? "bg-[#1a3a5c] text-white shadow" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{y}</button>
          ))}
          <span className="ml-auto text-xs text-slate-400">Total {fuelYear} : <b className="text-slate-700">{fmtTND(fuelTotal)}</b></span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-400">
              <th className="py-1">Mois</th><th>Estimé (TND)</th><th>Réel (TND)</th>
            </tr></thead>
            <tbody>
              {fuelMonths.map((f) => {
                const now = new Date();
                const isCurrent = f.year === now.getFullYear() && f.month === now.getMonth() + 1;
                return (
                  <tr key={`${f.year}-${f.month}`} className={`border-t border-slate-100 ${isCurrent ? "bg-sky-50/50" : ""}`}>
                    <td className={`py-2 font-semibold ${f.covered ? "" : "text-slate-400"}`}>
                      {MONTHS[f.month - 1]} {f.year}
                      {isCurrent && <span className="ml-1 text-[10px] font-bold uppercase text-sky-500">en cours</span>}
                      {!f.covered && <span className="block text-[10px] font-normal text-slate-400">hors contrat</span>}
                    </td>
                    {readOnly ? (
                      <>
                        <td className="py-2">{f.estimated ? Number(f.estimated).toLocaleString("fr-FR") : "—"}</td>
                        <td className="py-2">{f.actual != null ? Number(f.actual).toLocaleString("fr-FR") : "—"}</td>
                      </>
                    ) : (
                      <>
                        <td><FuelCell value={f.estimated} placeholder="0" onSave={(v) => saveFuel(f.year, f.month, "estimated", v)} /></td>
                        <td><FuelCell value={f.actual} placeholder="—" onSave={(v) => saveFuel(f.year, f.month, "actual", v)} /></td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {assign && (
        <RegionAssignModal buses={buses} bus={buses.find((b) => String(b.id) === busId)}
          initial={{ date_from: assign.start_date, date_to: assign.end_date }}
          onClose={() => setAssign(null)}
          onDone={(b, r) => {
            setAssign(null); reload();
            setOkMsg(`Région mise à jour : ${b?.name || "véhicule"} → ${r}. Le calendrier et les totaux sont recalculés.`);
            setTimeout(() => setOkMsg(""), 6000);
          }} />
      )}

      {form && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4" onClick={() => setForm(null)}>
          <div className="safe-bottom max-h-[92vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="mb-4 text-lg font-bold text-[#1a3a5c]">{form.id ? "Modifier" : "Nouveau"} contrat</h3>
            <div className="space-y-3">
              <L label="Libellé"><input className={inp} value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} placeholder="ex. Contrat Mai" /></L>
              <div className="grid grid-cols-2 gap-3">
                <L label="Début"><input type="date" className={inp} value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></L>
                <L label="Fin"><input type="date" className={inp} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></L>
              </div>
              <L label="Loyer (TND)"><input type="number" className={inp} value={form.loyer} onChange={(e) => setForm({ ...form, loyer: e.target.value })} /></L>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setForm(null)} className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-500 hover:bg-slate-100">Annuler</button>
              <button onClick={saveContract} disabled={!form.start_date || !form.end_date} className="rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white hover:bg-[#234d77] disabled:opacity-50">Enregistrer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const inp = "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
const L = ({ label, children }) => (<label className="block"><span className="mb-1 block text-xs font-semibold text-slate-500">{label}</span>{children}</label>);

function Stat({ label, value, neg, pos, big }) {
  const color = big ? (pos ? "text-emerald-600" : "text-rose-600") : neg ? "text-slate-500" : "text-slate-700";
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`${big ? "text-base font-extrabold" : "text-sm font-semibold"} ${color}`}>{value}</div>
    </div>
  );
}

function FuelCell({ value, onSave, placeholder }) {
  const [v, setV] = useState(value ?? "");
  useEffect(() => { setV(value ?? ""); }, [value]);
  return (
    <input
      type="number" value={v} placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => { if (String(v) !== String(value ?? "")) onSave(v); }}
      min="0" inputMode="decimal"
      className="w-24 rounded-lg border border-slate-200 px-2 py-1.5 text-sm outline-none focus:border-sky-400 sm:w-28"
    />
  );
}
