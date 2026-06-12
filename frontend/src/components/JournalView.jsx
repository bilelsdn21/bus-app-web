import { useEffect, useState } from "react";
import { api } from "../api.js";

// Colored chip per action category.
const CHIP = {
  "Excursion":   "bg-sky-100 text-sky-700",
  "Contrat":     "bg-violet-100 text-violet-700",
  "Carburant":   "bg-amber-100 text-amber-700",
  "Véhicule":    "bg-emerald-100 text-emerald-700",
  "Destination": "bg-rose-100 text-rose-700",
  "Périodes":    "bg-slate-200 text-slate-700",
  "Journée":     "bg-sky-100 text-sky-700",
  "Connexion":         "bg-emerald-100 text-emerald-700",
  "Déconnexion":       "bg-slate-200 text-slate-600",
  "Connexion échouée": "bg-rose-100 text-rose-700",
};

// Emoji by whether the detail is an add / edit / delete.
function icon(detail = "") {
  if (detail.startsWith("Ajout")) return "➕";
  if (detail.startsWith("Modification")) return "✏️";
  if (detail.startsWith("Suppression")) return "🗑️";
  return "•";
}

export default function JournalView() {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");

  const load = () => api.audit().then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">🧾 Journal d'activité</h1>
        <button onClick={load} className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold shadow hover:bg-slate-50">↻ Actualiser</button>
      </div>
      <p className="text-xs text-slate-400">Qui a fait quoi, et quand — avec le détail exact de chaque ajout, modification ou suppression, et le compte responsable.</p>

      {err && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{err}</div>}
      {rows === null && <div className="py-10 text-center text-slate-400">Chargement…</div>}

      {rows && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
          <table className="w-full text-sm">
            <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
              <th className="px-4 py-2">Date / heure</th><th className="px-2">Utilisateur</th><th className="px-2">Catégorie</th><th className="px-2">Détail</th>
            </tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-slate-100 align-top">
                  <td className="whitespace-nowrap px-4 py-2 text-slate-500">
                    {r.time ? new Date(r.time + "Z").toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                  </td>
                  <td className="px-2 py-2 font-semibold text-[#1a3a5c]">{r.user}</td>
                  <td className="px-2 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${CHIP[r.action] || "bg-slate-100 text-slate-600"}`}>{r.action}</span>
                  </td>
                  <td className="px-2 py-2 text-slate-700">{icon(r.detail)} {r.detail}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={4} className="py-6 text-center text-slate-400">Aucune activité enregistrée pour l'instant.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
