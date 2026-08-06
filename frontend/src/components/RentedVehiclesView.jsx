import { useEffect, useState } from "react";
import { api, downloadBlob } from "../api.js";
import { fmtTND } from "../colors.js";

const REGIONS = ["Sousse", "Djerba"];
const TYPES = ["MICRO", "OTOKAR", "BUS"];
const frDate = (s) => (s ? s.split("-").reverse().join("/") : "—");

export default function RentedVehiclesView({ readOnly = false }) {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(null); // {id?, name, region, start_date, end_date, cost, notes}
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);

  const load = () => api.rentedVehicles().then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const exportExcel = async () => {
    setExporting(true); setErr("");
    try {
      const blob = await api.exportRentedVehicles();
      downloadBlob(blob, "Vehicules_loues.xlsx");
    } catch (e) { setErr(e.message); }
    finally { setExporting(false); }
  };

  const save = async () => {
    setErr("");
    try {
      const p = {
        name: form.name, type: form.type, region: form.region,
        start_date: form.start_date, end_date: form.end_date,
        cost: Number(form.cost) || 0, notes: form.notes || "",
      };
      if (form.id) await api.updateRentedVehicle(form.id, p); else await api.createRentedVehicle(p);
      setForm(null); load();
    } catch (e) { setErr(e.message); }
  };
  const del = async (r) => {
    if (!confirm(`Supprimer "${r.name}" (${frDate(r.start_date)} → ${frDate(r.end_date)}) ?`)) return;
    try { await api.deleteRentedVehicle(r.id); load(); } catch (e) { setErr(e.message); }
  };

  const total = rows.reduce((s, r) => s + (r.cost || 0), 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">🚐 Véhicules loués</h1>
        {readOnly && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-bold uppercase text-slate-500">lecture seule</span>}
        {!readOnly && (
          <button onClick={() => setForm({ name: "", type: TYPES[0], region: REGIONS[0], start_date: "", end_date: "", cost: 0, notes: "" })}
            className="rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white shadow hover:bg-[#234d77]">
            + Véhicule loué
          </button>
        )}
        <button onClick={exportExcel} disabled={exporting || rows.length === 0}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50">
          {exporting ? "Export…" : "⬇️ Exporter Excel"}
        </button>
      </div>

      <p className="text-xs text-slate-400">
        Véhicules loués en renfort (pas notre flotte) pour une période. Leur coût est réparti au prorata des jours sur
        chaque mois couvert, et déduit du Net de ce mois sur le Calendrier — voir la section
        "🚐 Location de véhicules supplémentaires" sous le calendrier.
      </p>

      {err && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{err}</div>}

      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
            <th className="px-3 py-2">Nom</th><th className="px-2">Type</th><th className="px-2">Région</th><th className="px-2">Du</th><th className="px-2">Au</th>
            <th className="px-2 text-right">Coût</th><th className="px-2">Alternative dispo ?</th><th className="px-2">Notes</th>{!readOnly && <th></th>}
          </tr></thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-6 text-center text-sm text-slate-400">Aucun véhicule loué enregistré.</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 font-semibold text-slate-700">{r.name}</td>
                <td className="px-2 py-2">{r.type || "—"}</td>
                <td className="px-2 py-2">{r.region || "—"}</td>
                <td className="px-2 py-2">{frDate(r.start_date)}</td>
                <td className="px-2 py-2">{frDate(r.end_date)}</td>
                <td className="px-2 py-2 text-right font-semibold text-slate-700">{fmtTND(r.cost)}</td>
                <td className="px-2 py-2"><RowAltBadge row={r} /></td>
                <td className="max-w-[160px] truncate px-2 py-2 text-slate-400">{r.notes}</td>
                {!readOnly && (
                  <td className="whitespace-nowrap px-2 py-2 pr-3 text-right">
                    <button onClick={() => setForm({ ...r })} className="px-1 text-slate-400 hover:text-sky-600">✎</button>
                    <button onClick={() => del(r)} className="px-1 text-slate-400 hover:text-rose-600">🗑</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
          {rows.length > 0 && (
            <tfoot>
              <tr className="border-t-2 border-slate-200 bg-slate-50 font-bold text-slate-700">
                <td className="px-3 py-2" colSpan={5}>Total</td>
                <td className="text-right">{fmtTND(total)}</td>
                <td colSpan={readOnly ? 2 : 3}></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4" onClick={() => setForm(null)}>
          <div className="w-full max-w-lg space-y-3 rounded-2xl bg-white p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-[#1a3a5c]">{form.id ? "Modifier" : "Nouveau"} véhicule loué</h3>
            <L label="Nom du véhicule"><input className={inp} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></L>
            <div className="grid grid-cols-3 gap-3">
              <L label="Type"><select className={inp} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></L>
              <L label="Région"><select className={inp} value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })}>{REGIONS.map((r) => <option key={r}>{r}</option>)}</select></L>
              <L label="Coût total (TND)"><input type="number" className={inp} value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} /></L>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <L label="Du"><input type="date" className={inp} value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></L>
              <L label="Au"><input type="date" className={inp} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></L>
            </div>
            <L label="Notes (optionnel)"><input className={inp} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></L>

            <LiveAlternatives type={form.type} region={form.region} start_date={form.start_date} end_date={form.end_date} />

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setForm(null)} className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-500 hover:bg-slate-100">Annuler</button>
              <button onClick={save} disabled={!form.name || !form.start_date || !form.end_date}
                className="rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white hover:bg-[#234d77] disabled:opacity-50">Enregistrer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Alternative-fleet-vehicle check: was renting this really necessary? ---

function AlternativesDetail({ result, type }) {
  if (!result) return null;
  const { days_total, days_with_alternative, days, fleet_count } = result;
  if (!fleet_count) {
    return (
      <div className="rounded-xl bg-slate-50 p-3 text-sm font-medium text-slate-500 ring-1 ring-slate-200">
        ℹ️ Aucun véhicule {type} dans notre flotte — comparaison impossible.
      </div>
    );
  }
  const bad = days_with_alternative > 0;
  return (
    <div className={`rounded-xl p-3 ring-1 ${bad ? "bg-rose-50 ring-rose-200" : "bg-emerald-50 ring-emerald-200"}`}>
      <div className={`flex items-center gap-2 text-sm font-bold ${bad ? "text-rose-700" : "text-emerald-700"}`}>
        <span>{bad ? "⚠️" : "✅"}</span>
        <span>
          {bad
            ? `${days_with_alternative}/${days_total} jour(s) où un ${type} de notre flotte était libre — location peut-être évitable`
            : `Aucune alternative — les ${fleet_count} véhicule(s) ${type} étaient occupés ou hors service`}
        </span>
      </div>
      {bad && (
        <div className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs text-rose-700">
          {days.filter((d) => d.available.length > 0).map((d) => (
            <div key={d.date}>
              <span className="font-semibold">{frDate(d.date)}</span> : {d.available.map((b) => b.name).join(", ")}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LiveAlternatives({ type, region, start_date, end_date }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!type || !start_date || !end_date || end_date < start_date) { setResult(null); return; }
    let alive = true;
    setLoading(true);
    const t = setTimeout(() => {
      api.checkAlternatives({ type, region, start_date, end_date })
        .then((r) => { if (alive) setResult(r); })
        .catch(() => { if (alive) setResult(null); })
        .finally(() => { if (alive) setLoading(false); });
    }, 350);
    return () => { alive = false; clearTimeout(t); };
  }, [type, region, start_date, end_date]);

  if (!start_date || !end_date) return null;
  return (
    <div>
      <div className="mb-1 text-xs font-semibold text-slate-500">Un véhicule de notre flotte était-il disponible ?</div>
      {loading && !result ? (
        <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-400 ring-1 ring-slate-200">Vérification…</div>
      ) : (
        <AlternativesDetail result={result} type={type} />
      )}
    </div>
  );
}

function RowAltBadge({ row }) {
  const [result, setResult] = useState(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let alive = true;
    api.checkAlternatives({ type: row.type, region: row.region, start_date: row.start_date, end_date: row.end_date })
      .then((r) => { if (alive) setResult(r); })
      .catch(() => {});
    return () => { alive = false; };
  }, [row.id, row.type, row.region, row.start_date, row.end_date]);

  if (!result) return <span className="text-xs text-slate-300">…</span>;
  if (!result.fleet_count) return <span className="text-xs text-slate-400">— aucun {row.type}</span>;

  const bad = result.days_with_alternative > 0;
  return (
    <div>
      <button onClick={() => setExpanded(!expanded)}
        className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${bad ? "bg-rose-100 text-rose-700 hover:bg-rose-200" : "bg-emerald-100 text-emerald-700 hover:bg-emerald-200"}`}>
        {bad ? `⚠️ ${result.days_with_alternative}/${result.days_total} jour(s)` : "✅ Aucune"}
      </button>
      {expanded && <div className="mt-2 w-64"><AlternativesDetail result={result} type={row.type} /></div>}
    </div>
  );
}

const inp = "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
const L = ({ label, children }) => (<label className="block"><span className="mb-1 block text-xs font-semibold text-slate-500">{label}</span>{children}</label>);
