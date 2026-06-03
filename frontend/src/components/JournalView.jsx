import { useEffect, useState } from "react";
import { api } from "../api.js";

// Turn a method+path into a readable French action.
function label(method, path) {
  const entity =
    path.includes("/excursions") || path.includes("/day") ? "excursion" :
    path.includes("/contracts") ? "contrat" :
    path.includes("/fuel") ? "carburant" :
    path.includes("/buses") ? "véhicule" :
    path.includes("/destinations") ? "destination" :
    path.includes("/config") ? "réglages (périodes)" : path;
  const verb =
    method === "POST" ? "Ajout" :
    method === "PUT" ? (path.includes("/fuel") || path.includes("/config") ? "Mise à jour" : "Modification") :
    method === "DELETE" ? "Suppression" : method;
  return path.includes("/fuel") ? "Mise à jour du carburant"
       : path.includes("/config") ? "Mise à jour des périodes"
       : `${verb} ${entity}`;
}

const ICON = { POST: "➕", PUT: "✏️", DELETE: "🗑️" };

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
      <p className="text-xs text-slate-400">Qui a fait quoi, et quand. Chaque ajout / modification / suppression est enregistré avec le compte responsable.</p>

      {err && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{err}</div>}
      {rows === null && <div className="py-10 text-center text-slate-400">Chargement…</div>}

      {rows && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
          <table className="w-full text-sm">
            <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
              <th className="px-4 py-2">Date / heure</th><th>Utilisateur</th><th>Action</th>
            </tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="whitespace-nowrap px-4 py-2 text-slate-500">
                    {r.time ? new Date(r.time + "Z").toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                  </td>
                  <td className="py-2 font-semibold text-[#1a3a5c]">{r.user}</td>
                  <td className="py-2">{ICON[r.method] || ""} {label(r.method, r.path)}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={3} className="py-6 text-center text-slate-400">Aucune activité enregistrée pour l'instant.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
