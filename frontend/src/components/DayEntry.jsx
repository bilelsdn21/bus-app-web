import { useEffect, useState } from "react";
import { api } from "../api.js";
import ExcursionEditor from "./ExcursionEditor.jsx";

const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// Mobile-friendly entry: pick a bus + date, then manage that day's excursions.
export default function DayEntry() {
  const [buses, setBuses] = useState([]);
  const [dests, setDests] = useState([]);
  const [busId, setBusId] = useState("");
  const [date, setDate] = useState(todayISO());
  const [open, setOpen] = useState(false);
  const [cover, setCover] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([api.buses(), api.destinations()])
      .then(([b, d]) => { setBuses(b); setDests(d); if (b[0]) setBusId(String(b[0].id)); })
      .catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!busId || !date) { setCover(null); return; }
    let alive = true;
    api.coverage(busId, date).then((c) => alive && setCover(c)).catch(() => {});
    return () => { alive = false; };
  }, [busId, date]);

  const bus = buses.find((b) => String(b.id) === String(busId));

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-xl font-extrabold text-[#1a3a5c]">Saisie des excursions</h1>
      {err && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{err}</div>}

      <div className="space-y-3 rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200">
        <label className="block">
          <span className="mb-1 block text-xs font-semibold text-slate-500">Véhicule</span>
          <select value={busId} onChange={(e) => setBusId(e.target.value)} className={inp}>
            {buses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-semibold text-slate-500">Date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inp} />
        </label>
        {bus && <div className="text-xs text-slate-400">Type : <b>{bus.type}</b> · Région : <b>{bus.region}</b></div>}
        {cover && !cover.covered && (
          <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
            ⛔ Aucun contrat ne couvre cette date — créez d'abord un contrat (onglet Contrats).
          </div>
        )}
        {cover && cover.covered && cover.contract && (
          <div className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            ✅ Contrat actif : {cover.contract.label || "contrat"} ({cover.contract.start_date} → {cover.contract.end_date})
          </div>
        )}
      </div>

      <button onClick={() => setOpen(true)} disabled={!busId}
        className="w-full rounded-2xl bg-[#1a3a5c] py-3.5 text-base font-bold text-white shadow-xl hover:bg-[#234d77] disabled:opacity-50">
        📋 Gérer les excursions de ce jour
      </button>

      {open && bus && (
        <ExcursionEditor bus={bus} dayISO={date} dests={dests} onClose={() => setOpen(false)} onChanged={() => {}} />
      )}
    </div>
  );
}

const inp = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
