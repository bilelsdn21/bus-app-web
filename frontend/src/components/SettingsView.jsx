import { useEffect, useState } from "react";
import { api } from "../api.js";

const TYPES = ["MICRO", "OTOKAR", "BUS"];
const REGIONS = ["Sousse", "Djerba"];

export default function SettingsView() {
  const [tab, setTab] = useState("buses");
  return (
    <div className="space-y-5">
      <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">Paramètres</h1>
      <div className="flex gap-1 rounded-xl bg-slate-200 p-1 w-fit">
        <SubTab on={tab === "buses"} onClick={() => setTab("buses")}>🚌 Véhicules</SubTab>
        <SubTab on={tab === "dests"} onClick={() => setTab("dests")}>📍 Destinations</SubTab>
        <SubTab on={tab === "config"} onClick={() => setTab("config")}>⚙️ Périodes</SubTab>
      </div>
      {tab === "buses" && <BusesPanel />}
      {tab === "dests" && <DestsPanel />}
      {tab === "config" && <ConfigPanel />}
    </div>
  );
}

function BusesPanel() {
  const [buses, setBuses] = useState([]);
  const [form, setForm] = useState(null);
  const [err, setErr] = useState("");
  const load = () => api.buses().then(setBuses).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const save = async () => {
    setErr("");
    try {
      const p = { name: form.name, type: form.type, region: form.region,
        distance: Number(form.distance) || 0, plate: form.plate || "" };
      if (form.id) await api.updateBus(form.id, p); else await api.createBus(p);
      setForm(null); load();
    } catch (e) { setErr(e.message); }
  };
  const del = async (b) => { if (!confirm(`Supprimer ${b.name} ?`)) return; try { await api.deleteBus(b.id); load(); } catch (e) { setErr(e.message); } };

  return (
    <div className="space-y-3">
      {err && <Err msg={err} />}
      <button onClick={() => setForm({ name: "", type: "BUS", region: "Sousse", distance: 0, plate: "" })} className={btnPrimary}>+ Véhicule</button>
      <p className="text-xs text-slate-400">💡 Le loyer se définit par <b>contrat</b> (onglet Contrats), pas sur le véhicule.</p>
      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
            <th className="px-3 py-2">Nom</th><th>Type</th><th>Région</th><th className="text-right">Distance</th><th></th>
          </tr></thead>
          <tbody>
            {buses.map((b) => (
              <tr key={b.id} className="border-t border-slate-100">
                <td className="px-3 py-2 font-semibold text-slate-700">{b.name}</td>
                <td>{b.type}</td><td>{b.region}</td>
                <td className="text-right">{b.distance ? Number(b.distance).toLocaleString("fr-FR") + " km" : "—"}</td>
                <td className="whitespace-nowrap pr-3 text-right">
                  <button onClick={() => setForm({ ...b })} className="px-1 text-slate-400 hover:text-sky-600">✎</button>
                  <button onClick={() => del(b)} className="px-1 text-slate-400 hover:text-rose-600">🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {form && (
        <Modal title={`${form.id ? "Modifier" : "Nouveau"} véhicule`} onClose={() => setForm(null)} onSave={save} canSave={!!form.name}>
          <L label="Nom (avec plaque, ex. BUS X 370 TU 243)"><input className={inp} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></L>
          <div className="grid grid-cols-2 gap-3">
            <L label="Type"><select className={inp} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></L>
            <L label="Région"><select className={inp} value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })}>{REGIONS.map((r) => <option key={r}>{r}</option>)}</select></L>
          </div>
          <L label="Distance (km / mois)"><input type="number" className={inp} value={form.distance} onChange={(e) => setForm({ ...form, distance: e.target.value })} /></L>
        </Modal>
      )}
    </div>
  );
}

function DestsPanel() {
  const [dests, setDests] = useState([]);
  const [form, setForm] = useState(null);
  const [err, setErr] = useState("");
  const load = () => api.destinations().then(setDests).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setErr("");
    try {
      const p = { category: form.category, name: form.name,
        price_micro: Number(form.price_micro) || 0, price_otokar: Number(form.price_otokar) || 0, price_bus: Number(form.price_bus) || 0 };
      if (form.id) await api.updateDest(form.id, p); else await api.createDest(p);
      setForm(null); load();
    } catch (e) { setErr(e.message); }
  };
  const del = async (d) => { if (!confirm(`Supprimer ${d.name} ?`)) return; await api.deleteDest(d.id); load(); };

  return (
    <div className="space-y-3">
      {err && <Err msg={err} />}
      <button onClick={() => setForm({ category: "", name: "", price_micro: 0, price_otokar: 0, price_bus: 0 })} className={btnPrimary}>+ Destination</button>
      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
            <th className="px-3 py-2">Catégorie</th><th>Destination</th><th className="text-right">MICRO</th><th className="text-right">OTOKAR</th><th className="text-right">BUS</th><th></th>
          </tr></thead>
          <tbody>
            {dests.map((d) => (
              <tr key={d.id} className="border-t border-slate-100">
                <td className="px-3 py-2 text-slate-400">{d.category}</td>
                <td className="font-semibold text-slate-700">{d.name}</td>
                <td className="text-right">{d.price_micro || "—"}</td><td className="text-right">{d.price_otokar || "—"}</td><td className="text-right">{d.price_bus || "—"}</td>
                <td className="whitespace-nowrap pr-3 text-right">
                  <button onClick={() => setForm({ ...d })} className="px-1 text-slate-400 hover:text-sky-600">✎</button>
                  <button onClick={() => del(d)} className="px-1 text-slate-400 hover:text-rose-600">🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {form && (
        <Modal title={`${form.id ? "Modifier" : "Nouvelle"} destination`} onClose={() => setForm(null)} onSave={save} canSave={!!form.name}>
          <div className="grid grid-cols-2 gap-3">
            <L label="Catégorie"><input className={inp} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></L>
            <L label="Destination"><input className={inp} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></L>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <L label="Prix MICRO"><input type="number" className={inp} value={form.price_micro} onChange={(e) => setForm({ ...form, price_micro: e.target.value })} /></L>
            <L label="Prix OTOKAR"><input type="number" className={inp} value={form.price_otokar} onChange={(e) => setForm({ ...form, price_otokar: e.target.value })} /></L>
            <L label="Prix BUS"><input type="number" className={inp} value={form.price_bus} onChange={(e) => setForm({ ...form, price_bus: e.target.value })} /></L>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ConfigPanel() {
  const [cfg, setCfg] = useState(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { api.config().then(setCfg); }, []);
  if (!cfg) return null;
  const save = async () => {
    await api.setConfig({ cut_morn: Number(cfg.cut_morn), cut_night: Number(cfg.cut_night) });
    setMsg("Enregistré.");
    setTimeout(() => setMsg(""), 2000);
  };
  return (
    <div className="max-w-md space-y-3 rounded-2xl bg-white p-5 shadow ring-1 ring-slate-200">
      <p className="text-sm text-slate-500">Bornes horaires pour la couleur des excursions (matin / soir / nuit).</p>
      <div className="grid grid-cols-2 gap-3">
        <L label="Coupure Matin/Soir (h)"><input type="number" className={inp} value={cfg.cut_morn} onChange={(e) => setCfg({ ...cfg, cut_morn: e.target.value })} /></L>
        <L label="Coupure Soir/Nuit (h)"><input type="number" className={inp} value={cfg.cut_night} onChange={(e) => setCfg({ ...cfg, cut_night: e.target.value })} /></L>
      </div>
      <button onClick={save} className={btnPrimary}>Enregistrer</button>
      {msg && <span className="ml-3 text-sm text-emerald-600">{msg}</span>}
    </div>
  );
}

const inp = "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
const btnPrimary = "rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white shadow hover:bg-[#234d77]";
const L = ({ label, children }) => (<label className="block"><span className="mb-1 block text-xs font-semibold text-slate-500">{label}</span>{children}</label>);
const Err = ({ msg }) => <div className="rounded-lg bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">{msg}</div>;
const SubTab = ({ on, onClick, children }) => (
  <button onClick={onClick} className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${on ? "bg-white text-[#1a3a5c] shadow" : "text-slate-500"}`}>{children}</button>
);

function Modal({ title, children, onClose, onSave, canSave }) {
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-md space-y-3 rounded-2xl bg-white p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-[#1a3a5c]">{title}</h3>
        {children}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-500 hover:bg-slate-100">Annuler</button>
          <button onClick={onSave} disabled={!canSave} className="rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white hover:bg-[#234d77] disabled:opacity-50">Enregistrer</button>
        </div>
      </div>
    </div>
  );
}
