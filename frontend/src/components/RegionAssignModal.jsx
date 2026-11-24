import { useEffect, useMemo, useState } from "react";
import { api, clearCache } from "../api.js";
import { fmtTND } from "../colors.js";

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const frDate = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : "—");

// quick windows, computed from today
function presets(contract) {
  const n = new Date(), y = n.getFullYear(), m = n.getMonth();
  const list = [
    ["Mois dernier", iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))],
    ["2 derniers mois", iso(new Date(y, m - 2, 1)), iso(new Date(y, m, 0))],
    ["3 derniers mois", iso(new Date(y, m - 3, 1)), iso(new Date(y, m, 0))],
    ["Ce mois", iso(new Date(y, m, 1)), iso(new Date(y, m + 1, 0))],
  ];
  if (contract?.date_from && contract?.date_to) list.unshift(["Ce contrat", contract.date_from, contract.date_to]);
  return list;
}

const inp = "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
const L = ({ label, children }) => (<label className="block"><span className="mb-1 block text-xs font-semibold text-slate-500">{label}</span>{children}</label>);

// "Between these two dates, this vehicle was in <region>" — for any window, past or future.
// The impact is previewed before anything is written.
export default function RegionAssignModal({ buses, bus, initial, onClose, onDone }) {
  const first = presets(initial)[0];
  const [busId, setBusId] = useState(String(bus?.id ?? buses[0]?.id ?? ""));
  const cur = buses.find((b) => String(b.id) === busId);
  const known = useMemo(
    () => [...new Set(["Sousse", "Djerba", ...buses.map((b) => (b.region || "").trim()).filter(Boolean)])],
    [buses]
  );
  const [region, setRegion] = useState(known.find((r) => r !== (cur?.region || "")) || known[0] || "");
  const [from, setFrom] = useState(first[1]);
  const [to, setTo] = useState(first[2]);
  const [open, setOpen] = useState(false);          // "from then on" (no end date)
  const [prev, setPrev] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const valid = !!busId && !!region.trim() && !!from && (open || (!!to && to >= from));
  const today = iso(new Date());
  const coversToday = valid && from <= today && (open || to >= today);

  // live impact preview (debounced)
  useEffect(() => {
    setPrev(null); setErr("");
    if (!valid) return;
    let alive = true;
    const t = setTimeout(() => {
      api.assignRegion({ bus_id: Number(busId), region, date_from: from, date_to: open ? null : to, preview: true })
        .then((r) => alive && setPrev(r))
        .catch((e) => alive && setErr(e.message));
    }, 400);
    return () => { alive = false; clearTimeout(t); };
  }, [busId, region, from, to, open, valid]);

  const apply = async () => {
    setBusy(true); setErr("");
    try {
      await api.assignRegion({ bus_id: Number(busId), region, date_from: from, date_to: open ? null : to });
      clearCache();                                 // calendar/analyse numbers have just changed
      onDone?.(cur, region);
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div className="safe-bottom max-h-[92vh] w-full max-w-lg space-y-3 overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-[#1a3a5c]">🗺️ Changer la région sur une période</h3>
            <p className="text-xs text-slate-400">Pour n'importe quelle période, passée ou à venir. Les sorties de ces jours suivent la région, et les totaux se recalculent.</p>
          </div>
          <button onClick={onClose} aria-label="Fermer" className="-m-2 p-2 text-lg text-slate-400">✕</button>
        </div>

        <L label="Véhicule">
          <select className={inp} value={busId} onChange={(e) => setBusId(e.target.value)}>
            {buses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </L>

        <L label="Nouvelle région">
          <input className={inp} list="known-regions" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="ex. Djerba" />
          <datalist id="known-regions">{known.map((r) => <option key={r} value={r} />)}</datalist>
        </L>
        <div className="flex flex-wrap gap-1.5">
          {known.map((r) => (
            <button key={r} onClick={() => setRegion(r)}
              className={`h-9 rounded-full px-3 text-xs font-semibold ${region === r ? "bg-[#1a3a5c] text-white" : "bg-slate-100 text-slate-600"}`}>{r}</button>
          ))}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {presets(initial).map(([label, f, t]) => (
            <button key={label} onClick={() => { setFrom(f); setTo(t); setOpen(false); }}
              className="h-9 rounded-lg bg-amber-100 px-3 text-xs font-semibold text-amber-800 active:scale-95">{label}</button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <L label="Du"><input type="date" className={inp} value={from} onChange={(e) => setFrom(e.target.value)} /></L>
          <L label="Au"><input type="date" disabled={open} className={inp + (open ? " bg-slate-50 text-slate-300" : "")} value={to} onChange={(e) => setTo(e.target.value)} /></L>
        </div>
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          <input type="checkbox" checked={open} onChange={(e) => setOpen(e.target.checked)} className="h-4 w-4" />
          Sans date de fin (le véhicule est dans cette région à partir de cette date)
        </label>
        {!open && to && from && to < from && <p className="text-xs font-semibold text-rose-600">La date de fin est avant la date de début.</p>}

        {/* impact preview */}
        {valid && !prev && !err && <div className="rounded-xl bg-slate-50 p-3 text-xs text-slate-400">Calcul de l'impact…</div>}
        {prev && prev.changed_days === 0 && (
          <div className="rounded-xl bg-emerald-50 p-3 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
            Aucun changement : {cur?.name} est déjà à <b>{prev.to_region}</b> sur cette période.
          </div>
        )}
        {prev && prev.changed_days > 0 && (
          <div className="space-y-1.5 rounded-xl bg-amber-50 p-3 text-xs text-amber-900 ring-1 ring-amber-200">
            <div className="text-sm font-bold">
              {prev.changed_days} jour{prev.changed_days > 1 ? "s" : ""} passent à {prev.to_region}
              {prev.unchanged_days > 0 && <span className="font-normal text-amber-700"> ({prev.unchanged_days} y étaient déjà)</span>}
            </div>
            {prev.from.map((g) => (
              <div key={g.region}>
                • <b>{g.days} j</b> étaient à <b>{g.region}</b>
                {g.trips > 0 ? <> — {g.trips} sortie{g.trips > 1 ? "s" : ""}, <b>{fmtTND(g.revenue)}</b> de recettes déplacées</> : " — aucune sortie enregistrée"}
              </div>
            ))}
            <div className="pt-1 text-[11px] text-amber-700">
              Le loyer et le carburant du contrat sont répartis au prorata des jours dans chaque région. Les jours hors de cette période ne changent pas.
            </div>
          </div>
        )}
        {open && <p className="text-[11px] text-slate-400">Sans date de fin = « Déplacer » : l'historique avant le {frDate(from)} garde sa région.</p>}
        {coversToday && !open && <p className="text-[11px] text-slate-400">Cette période contient aujourd'hui : la région actuelle du véhicule devient <b>{region}</b>.</p>}
        {err && <div className="rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{err}</div>}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="h-11 rounded-xl px-4 text-sm font-semibold text-slate-500 hover:bg-slate-100">Annuler</button>
          <button onClick={apply} disabled={!valid || busy || (prev && prev.changed_days === 0)}
            className="h-11 rounded-xl bg-[#1a3a5c] px-5 text-sm font-bold text-white hover:bg-[#234d77] disabled:opacity-50">
            {busy ? "Application…" : "Appliquer"}
          </button>
        </div>
      </div>
    </div>
  );
}
