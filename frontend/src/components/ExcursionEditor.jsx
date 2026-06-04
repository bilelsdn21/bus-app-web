import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmtTND } from "../colors.js";

const UNAVAIL = ["Entretien", "Libre", "Repos Chauffeur"];
const TIMES = Array.from({ length: 48 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`);

// Editable panel for one bus on one day: lists active excursions, add/edit/delete.
// Multi-day aware. readOnly hides all editing.
export default function ExcursionEditor({ bus, dayISO, dests, readOnly = false, onClose, onChanged }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState(null); // excursion being added/edited
  const [cover, setCover] = useState(null);
  const [saving, setSaving] = useState(false); // guard against double-submit

  const load = () => api.excursionsForDay(bus.id, dayISO).then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [bus.id, dayISO]);

  const categories = useMemo(() => {
    const cats = [...new Set(dests.map((d) => d.category).filter(Boolean))];
    return [...cats, ...UNAVAIL];
  }, [dests]);
  const destsForCat = (c) => dests.filter((d) => d.category === c);

  // check contract coverage for the form's start date
  useEffect(() => {
    if (!form) { setCover(null); return; }
    let alive = true;
    api.coverage(bus.id, form.start_date).then((c) => alive && setCover(c)).catch(() => {});
    return () => { alive = false; };
  }, [form?.start_date, bus.id]);

  const startAdd = () => setForm({ start_date: dayISO, end_date: dayISO, category: "", destination: "", client: "", pax: "", heure_debut: "", heure_fin: "" });
  const startEdit = (e) => setForm({
    id: e.id, start_date: e.start_date, end_date: e.end_date,
    category: UNAVAIL.includes(e.destination) ? e.destination : guessCat(dests, e.destination),
    destination: UNAVAIL.includes(e.destination) ? "" : e.destination,
    client: e.client || "", pax: e.pax || "", heure_debut: e.heure_debut || "", heure_fin: e.heure_fin || "",
  });

  const save = async () => {
    if (saving) return;                 // ignore double-clicks while the request is in flight
    setSaving(true);
    setErr("");
    try {
      const payload = {
        bus_id: bus.id, start_date: form.start_date, end_date: form.end_date || form.start_date,
        category: form.category, destination: form.destination, client: form.client,
        pax: Number(form.pax) || 0, heure_debut: form.heure_debut, heure_fin: form.heure_fin,
      };
      if (form.id) await api.updateExcursion(form.id, payload);
      else await api.createExcursion(payload);
      setForm(null); await load(); onChanged?.();
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };
  const del = async (e) => {
    if (!confirm("Supprimer cette excursion ?")) return;
    try { await api.deleteExcursion(e.id); await load(); onChanged?.(); } catch (e) { setErr(e.message); }
  };

  const dateLabel = new Date(dayISO + "T00:00:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const blocked = form && cover && !cover.covered;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between rounded-t-2xl bg-[#1a3a5c] px-5 py-4 text-white">
          <div>
            <div className="text-sm font-bold">{bus.name}</div>
            <div className="text-xs capitalize text-sky-200">{dateLabel}</div>
          </div>
          <button onClick={onClose} className="text-white/70 hover:text-white">✕</button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          {err && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
          {rows === null && <div className="py-6 text-center text-slate-400">Chargement…</div>}

          {rows && rows.length === 0 && !form && (
            <div className="rounded-xl bg-slate-50 py-6 text-center text-sm text-slate-400">Aucune excursion ce jour.</div>
          )}

          {/* existing excursions */}
          {rows && rows.map((e) => (
            <div key={e.id} className={`rounded-xl border-l-4 px-4 py-3 shadow-sm ring-1 ring-slate-100 ${e.type === "Booking" ? "border-emerald-400 bg-white" : "border-rose-400 bg-rose-50"}`}>
              <div className="flex items-start justify-between">
                <div className="text-sm font-bold text-slate-700">{e.type === "Booking" ? e.destination : `🔴 ${e.destination}`}</div>
                <div className="flex items-center gap-2">
                  {e.type === "Booking" && <div className="text-sm font-extrabold text-emerald-600">{fmtTND(e.total)}</div>}
                  {!readOnly && <button onClick={() => startEdit(e)} className="text-slate-400 hover:text-sky-600">✎</button>}
                  {!readOnly && <button onClick={() => del(e)} className="text-slate-400 hover:text-rose-600">🗑</button>}
                </div>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                {e.multi_day && <span className="rounded bg-sky-100 px-1.5 font-semibold text-sky-700">📅 {e.start_date} → {e.end_date}</span>}
                {(e.heure_debut || e.heure_fin) && <span>🕐 {e.heure_debut || "?"} → {e.heure_fin || "?"}</span>}
                {e.client && <span>👤 {e.client}</span>}
                {e.pax > 0 && <span>👥 {e.pax} pax</span>}
              </div>
            </div>
          ))}

          {/* add/edit form */}
          {form && (
            <div className="space-y-2 rounded-xl bg-sky-50/60 p-3 ring-1 ring-sky-100">
              <div className="text-xs font-bold text-[#1a3a5c]">{form.id ? "Modifier l'excursion" : "Nouvelle excursion"}</div>
              <div className="grid grid-cols-2 gap-2">
                <L label="Du"><input type="date" className={inp} value={form.start_date} onChange={(ev) => setForm({ ...form, start_date: ev.target.value, end_date: ev.target.value > form.end_date ? ev.target.value : form.end_date })} /></L>
                <L label="Au (multi-jours)"><input type="date" min={form.start_date} className={inp} value={form.end_date} onChange={(ev) => setForm({ ...form, end_date: ev.target.value })} /></L>
              </div>
              <select className={inp} value={form.category} onChange={(ev) => setForm({ ...form, category: ev.target.value, destination: "" })}>
                <option value="">— Catégorie —</option>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              {form.category && !UNAVAIL.includes(form.category) && (
                <>
                  <select className={inp} value={form.destination} onChange={(ev) => setForm({ ...form, destination: ev.target.value })}>
                    <option value="">— Destination —</option>
                    {destsForCat(form.category).map((d) => <option key={d.id} value={d.name}>{d.name}</option>)}
                  </select>
                  <input className={inp} placeholder="Client (optionnel)" value={form.client} onChange={(ev) => setForm({ ...form, client: ev.target.value })} />
                  <div className="grid grid-cols-3 gap-2">
                    <input type="number" min="0" className={inp} placeholder="Pax" value={form.pax} onChange={(ev) => setForm({ ...form, pax: ev.target.value })} />
                    <Time value={form.heure_debut} onChange={(v) => setForm({ ...form, heure_debut: v })} ph="Départ" />
                    <Time value={form.heure_fin} onChange={(v) => setForm({ ...form, heure_fin: v })} ph="Retour" />
                  </div>
                </>
              )}
              {blocked && <div className="rounded bg-amber-50 px-2 py-1.5 text-xs font-medium text-amber-800">⛔ Aucun contrat ne couvre cette date — créez un contrat d'abord.</div>}
              <div className="flex justify-end gap-2 pt-1">
                <button onClick={() => setForm(null)} disabled={saving} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-slate-500 hover:bg-slate-100 disabled:opacity-50">Annuler</button>
                <button onClick={save} disabled={saving || !form.category || blocked} className="rounded-lg bg-[#1a3a5c] px-3 py-1.5 text-sm font-bold text-white hover:bg-[#234d77] disabled:opacity-50">{saving ? "Enregistrement…" : "Enregistrer"}</button>
              </div>
            </div>
          )}
        </div>

        {!readOnly && !form && (
          <div className="border-t border-slate-100 p-4">
            <button onClick={startAdd} className="w-full rounded-xl bg-[#1a3a5c] py-3 text-sm font-bold text-white hover:bg-[#234d77]">+ Nouvelle excursion</button>
          </div>
        )}
      </div>
    </div>
  );
}

const inp = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
const L = ({ label, children }) => (<label className="block"><span className="mb-1 block text-[11px] font-semibold text-slate-500">{label}</span>{children}</label>);
const Time = ({ value, onChange, ph }) => (
  <select className={inp} value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">{ph}</option>
    {TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
  </select>
);
const guessCat = (dests, name) => dests.find((d) => d.name === name)?.category || "";
