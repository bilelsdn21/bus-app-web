import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

const UNAVAIL = ["Entretien", "Libre", "Repos Chauffeur"];
const TIMES = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, "0");
  const m = i % 2 ? "30" : "00";
  return `${h}:${m}`;
});

const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function DayEntry() {
  const [buses, setBuses] = useState([]);
  const [dests, setDests] = useState([]);
  const [busId, setBusId] = useState("");
  const [date, setDate] = useState(todayISO());
  const [rows, setRows] = useState([emptyRow()]);
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState(null); // {type, msg}
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([api.buses(), api.destinations()])
      .then(([b, d]) => { setBuses(b); setDests(d); if (b[0]) setBusId(String(b[0].id)); })
      .catch((e) => setStatus({ type: "error", msg: e.message }));
  }, []);

  // categories from destinations + the unavailability reasons
  const categories = useMemo(() => {
    const cats = [...new Set(dests.map((d) => d.category).filter(Boolean))];
    return [...cats, ...UNAVAIL];
  }, [dests]);

  const destsForCat = (cat) => dests.filter((d) => d.category === cat);

  // load existing entries when bus/date change
  useEffect(() => {
    if (!busId || !date) return;
    api.getDay(busId, date).then((existing) => {
      if (!existing.length) { setRows([emptyRow()]); setNotes(""); return; }
      setNotes(existing[0].notes || "");
      setRows(existing.map((e) => ({
        category: UNAVAIL.includes(e.destination) ? e.destination : guessCat(dests, e.destination),
        destination: UNAVAIL.includes(e.destination) ? "" : e.destination,
        client: e.client || "", pax: e.pax || "",
        heure_debut: e.heure_debut || "", heure_fin: e.heure_fin || "",
      })));
    }).catch(() => {});
  }, [busId, date, dests]);

  const setRow = (i, patch) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const addRow = () => setRows((rs) => [...rs, emptyRow()]);
  const delRow = (i) => setRows((rs) => (rs.length === 1 ? [emptyRow()] : rs.filter((_, j) => j !== i)));

  const save = async () => {
    setStatus(null); setLoading(true);
    try {
      const payload = {
        bus_id: Number(busId), date, notes,
        rows: rows
          .filter((r) => r.category)
          .map((r) => ({
            category: r.category, destination: r.destination, client: r.client,
            pax: Number(r.pax) || 0, heure_debut: r.heure_debut, heure_fin: r.heure_fin,
          })),
      };
      const res = await api.saveDay(payload);
      setStatus({ type: "ok", msg: `Enregistré (${res.saved} activité${res.saved > 1 ? "s" : ""}).` });
    } catch (e) {
      setStatus({ type: "error", msg: e.message });
    } finally {
      setLoading(false);
    }
  };

  const bus = buses.find((b) => String(b.id) === String(busId));

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-xl font-extrabold text-[#1a3a5c]">Saisie journalière</h1>

      {/* bus + date */}
      <div className="space-y-3 rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200">
        <Field label="Véhicule">
          <select value={busId} onChange={(e) => setBusId(e.target.value)} className={inputCls}>
            {buses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </Field>
        <Field label="Date">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
        </Field>
        {bus && <div className="text-xs text-slate-400">Type : <b>{bus.type}</b> · Région : <b>{bus.region}</b></div>}
      </div>

      {/* activity rows */}
      <div className="space-y-3">
        {rows.map((r, i) => (
          <div key={i} className="rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400">Activité {i + 1}</span>
              <button onClick={() => delRow(i)} className="text-rose-400 hover:text-rose-600" aria-label="Supprimer">✕</button>
            </div>
            <div className="space-y-2">
              <select value={r.category} onChange={(e) => setRow(i, { category: e.target.value, destination: "" })} className={inputCls}>
                <option value="">— Catégorie —</option>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>

              {r.category && !UNAVAIL.includes(r.category) && (
                <>
                  <select value={r.destination} onChange={(e) => setRow(i, { destination: e.target.value })} className={inputCls}>
                    <option value="">— Destination —</option>
                    {destsForCat(r.category).map((d) => <option key={d.id} value={d.name}>{d.name}</option>)}
                  </select>
                  <input placeholder="Client (optionnel)" value={r.client} onChange={(e) => setRow(i, { client: e.target.value })} className={inputCls} />
                  <div className="grid grid-cols-3 gap-2">
                    <input type="number" min="0" placeholder="Pax" value={r.pax} onChange={(e) => setRow(i, { pax: e.target.value })} className={inputCls} />
                    <TimeSelect value={r.heure_debut} onChange={(v) => setRow(i, { heure_debut: v })} placeholder="Début" />
                    <TimeSelect value={r.heure_fin} onChange={(v) => setRow(i, { heure_fin: v })} placeholder="Fin" />
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
        <button onClick={addRow} className="w-full rounded-2xl border-2 border-dashed border-slate-300 py-3 text-sm font-semibold text-slate-500 hover:border-sky-400 hover:text-sky-600">
          + Ajouter une activité
        </button>
      </div>

      <Field label="Commentaire">
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className={inputCls} />
      </Field>

      {status && (
        <div className={`rounded-xl px-4 py-3 text-sm font-medium ${status.type === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>
          {status.type === "ok" ? "✅ " : "⚠️ "}{status.msg}
        </div>
      )}

      <button onClick={save} disabled={loading || !busId}
        className="sticky bottom-3 w-full rounded-2xl bg-[#1a3a5c] py-3.5 text-base font-bold text-white shadow-xl transition hover:bg-[#234d77] disabled:opacity-50">
        {loading ? "Enregistrement…" : "💾 Enregistrer"}
      </button>
    </div>
  );
}

const inputCls = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function TimeSelect({ value, onChange, placeholder }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls}>
      <option value="">{placeholder}</option>
      {TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
    </select>
  );
}

const emptyRow = () => ({ category: "", destination: "", client: "", pax: "", heure_debut: "", heure_fin: "" });
const guessCat = (dests, destName) => (dests.find((d) => d.name === destName)?.category) || "";
