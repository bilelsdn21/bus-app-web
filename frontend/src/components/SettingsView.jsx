import { useEffect, useMemo, useState } from "react";
import { api, downloadBlob } from "../api.js";

const TYPES = ["MICRO", "OTOKAR", "BUS"];
const REGIONS = ["Sousse", "Djerba"];

export default function SettingsView({ readOnly = false }) {
  const [tab, setTab] = useState("buses");
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">Paramètres</h1>
        {readOnly && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-bold uppercase text-slate-500">lecture seule</span>}
      </div>
      <div className="scroll-x -mx-3 flex gap-1 overflow-x-auto rounded-xl bg-slate-200 p-1 sm:mx-0 sm:w-fit sm:flex-wrap">
        <SubTab on={tab === "buses"} onClick={() => setTab("buses")}>🚌 Véhicules</SubTab>
        <SubTab on={tab === "dests"} onClick={() => setTab("dests")}>📍 Destinations</SubTab>
        <SubTab on={tab === "tarifs"} onClick={() => setTab("tarifs")}>💰 Tarifs antérieurs</SubTab>
        <SubTab on={tab === "regions"} onClick={() => setTab("regions")}>🗺️ Régions par saison</SubTab>
        <SubTab on={tab === "config"} onClick={() => setTab("config")}>⚙️ Périodes</SubTab>
      </div>
      {tab === "buses" && <BusesPanel readOnly={readOnly} />}
      {tab === "dests" && <DestsPanel readOnly={readOnly} />}
      {tab === "tarifs" && <PricePeriodsPanel readOnly={readOnly} />}
      {tab === "regions" && <RegionPeriodsPanel readOnly={readOnly} />}
      {tab === "config" && <ConfigPanel readOnly={readOnly} />}
    </div>
  );
}

const BLANK_FILTERS = { q: "", type: "", region: "", year: "", history: "", sort: "order" };

function BusesPanel({ readOnly = false }) {
  const [buses, setBuses] = useState([]);
  const [form, setForm] = useState(null);
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);
  const [f, setF] = useState(BLANK_FILTERS);
  // the overview carries what the Bus row alone can't answer: when the vehicle worked,
  // how much is recorded on it, and whether its region history has holes
  const load = () => api.busesOverview().then(setBuses).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const exportExcel = async () => {
    setExporting(true); setErr("");
    try { downloadBlob(await api.exportBuses(), "Vehicules.xlsx"); }
    catch (e) { setErr(e.message); }
    finally { setExporting(false); }
  };

  const save = async () => {
    setErr("");
    try {
      const p = { name: form.name, type: form.type, region: form.region,
        distance: Number(form.distance) || 0, plate: form.plate || "",
        // a region change on an existing vehicle is a dated MOVE: the API refuses it
        // without a date so past months keep the region they were worked in
        region_effective_from: form.region_effective_from || null };
      if (form.id) await api.updateBus(form.id, p); else await api.createBus(p);
      setForm(null); load();
    } catch (e) { setErr(e.message); }
  };
  const del = async (b) => { if (!confirm(`Supprimer ${b.name} ?`)) return; try { await api.deleteBus(b.id); load(); } catch (e) { setErr(e.message); } };

  const years = useMemo(
    () => [...new Set(buses.flatMap((b) => b.years || []))].sort((a, b) => b - a),
    [buses]
  );

  // every filter is a plain AND — an empty value means "don't filter on this"
  const shown = useMemo(() => {
    const q = f.q.trim().toLowerCase();
    const out = buses.filter((b) => {
      if (q && !`${b.name} ${b.plate}`.toLowerCase().includes(q)) return false;
      if (f.type && b.type !== f.type) return false;
      if (f.region === "__none__" ? !!b.region : f.region && b.region !== f.region) return false;
      if (f.year && !(b.years || []).includes(Number(f.year))) return false;
      if (f.history === "moved" && !b.moved) return false;
      if (f.history === "stable" && b.moved) return false;
      if (f.history === "gaps" && !b.past_gap_days) return false;
      if (f.history === "idle" && b.contracts > 0) return false;
      return true;
    });
    const by = {
      name: (a, b) => a.name.localeCompare(b.name),
      recent: (a, b) => (b.last_day || "").localeCompare(a.last_day || ""),
      trips: (a, b) => b.trips - a.trips,
    }[f.sort];
    return by ? [...out].sort(by) : out;
  }, [buses, f]);

  const active = Object.entries(f).filter(([k, v]) => v && k !== "sort").length;
  const gapCount = buses.filter((b) => b.past_gap_days).length;

  return (
    <div className="space-y-3">
      {err && <Err msg={err} />}
      <div className="flex flex-wrap items-center gap-3">
        {!readOnly && <button onClick={() => setForm({ name: "", type: "BUS", region: "Sousse", distance: 0, plate: "" })} className={btnPrimary}>+ Véhicule</button>}
        <button onClick={exportExcel} disabled={exporting || buses.length === 0}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50">
          {exporting ? "Export…" : "⬇️ Exporter Excel"}
        </button>
      </div>
      <p className="text-xs text-slate-400">💡 Le loyer se définit par <b>contrat</b> (onglet Contrats), pas sur le véhicule.</p>

      {/* Filters — they all apply together, an empty one is simply ignored */}
      <div className="rounded-2xl bg-white p-3 shadow ring-1 ring-slate-200">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <input placeholder="🔎 Nom ou plaque…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })}
                 className={inp + " lg:col-span-2"} />
          <select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })} className={inp}>
            <option value="">Tous les types</option>
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={f.region} onChange={(e) => setF({ ...f, region: e.target.value })} className={inp}>
            <option value="">Toutes les régions</option>
            {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            <option value="__none__">Région non définie</option>
          </select>
          <select value={f.year} onChange={(e) => setF({ ...f, year: e.target.value })} className={inp}>
            <option value="">Toutes les saisons</option>
            {years.map((y) => <option key={y} value={y}>Actif en {y}</option>)}
          </select>
          <select value={f.history} onChange={(e) => setF({ ...f, history: e.target.value })} className={inp}>
            <option value="">Tout l&apos;historique</option>
            <option value="stable">Jamais changé de région</option>
            <option value="moved">A changé de région</option>
            <option value="gaps">⚠️ Historique de région à trous{gapCount ? ` (${gapCount})` : ""}</option>
            <option value="idle">Sans aucun contrat</option>
          </select>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
          <span className="font-semibold text-slate-500">{shown.length} / {buses.length} véhicule(s)</span>
          <label className="flex items-center gap-1.5 text-slate-400">
            Trier
            <select value={f.sort} onChange={(e) => setF({ ...f, sort: e.target.value })}
                    className="rounded-lg border border-slate-200 px-2 py-1 text-xs outline-none focus:border-sky-500">
              <option value="order">Ordre de la flotte</option>
              <option value="name">Nom</option>
              <option value="recent">Activité la plus récente</option>
              <option value="trips">Nombre de sorties</option>
            </select>
          </label>
          {active > 0 && (
            <button onClick={() => setF({ ...BLANK_FILTERS, sort: f.sort })}
                    className="rounded-lg bg-slate-100 px-2 py-1 font-semibold text-slate-500 hover:bg-slate-200">
              ✕ Réinitialiser ({active})
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="stack w-full text-sm">
          <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
            <th className="px-3 py-2">Nom</th><th>Type</th><th>Région</th>
            <th>Saisons</th><th>Activité</th>
            <th className="text-right">Contrats</th><th className="text-right">Sorties</th>
            <th className="text-right">Distance</th>{!readOnly && <th></th>}
          </tr></thead>
          <tbody>
            {shown.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-6 text-center text-sm text-slate-400">
                Aucun véhicule ne correspond à ces filtres.
              </td></tr>
            )}
            {shown.map((b) => (
              <tr key={b.id} className="border-t border-slate-100">
                <td className="px-3 py-2 font-semibold text-slate-700">
                  {b.name}
                  {!!b.past_gap_days && (
                    <span title={`${b.past_gap_days} jour(s) d'activité sans période de région déclarée : ces jours prennent la région actuelle (${b.region}). Corrigez-les dans l'onglet « Régions par saison ».`}
                          className="ml-1.5 cursor-help text-amber-500">⚠️</span>
                  )}
                </td>
                <td>{b.type}</td>
                <td>
                  {b.region || <span className="text-slate-300">—</span>}
                  {b.moved && <span className="ml-1 text-[10px] font-semibold text-slate-400">({b.regions.join(" / ")})</span>}
                </td>
                <td className="whitespace-nowrap text-xs text-slate-500">{(b.years || []).join(", ") || "—"}</td>
                <td className="whitespace-nowrap text-xs text-slate-400">
                  {b.first_day ? `${frDate(b.first_day)} → ${frDate(b.last_day)}` : "—"}
                </td>
                <td className="text-right">{b.contracts || <span className="text-slate-300">0</span>}</td>
                <td className="text-right">{b.trips || <span className="text-slate-300">0</span>}</td>
                <td className="whitespace-nowrap text-right">{b.distance ? Number(b.distance).toLocaleString("fr-FR") + " km" : "—"}</td>
                {!readOnly && (
                  <td className="whitespace-nowrap pr-3 text-right">
                    <button onClick={() => setForm({ ...b, _region0: b.region })} className="px-2.5 py-1.5 text-base text-slate-400 hover:text-sky-600">✎</button>
                    <button onClick={() => del(b)} className="px-2.5 py-1.5 text-base text-slate-400 hover:text-rose-600">🗑</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {form && (() => {
        const moving = !!form.id && form.region !== form._region0;
        return (
          <Modal title={`${form.id ? "Modifier" : "Nouveau"} véhicule`} onClose={() => setForm(null)} onSave={save}
                 canSave={!!form.name && (!moving || !!form.region_effective_from)}>
            <L label="Nom (avec plaque, ex. BUS X 370 TU 243)"><input className={inp} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></L>
            <div className="grid grid-cols-2 gap-3">
              <L label="Type"><select className={inp} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></L>
              <L label="Région"><select className={inp} value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })}>{REGIONS.map((r) => <option key={r}>{r}</option>)}</select></L>
            </div>
            {moving && (
              <div className="rounded-xl bg-amber-50 p-3 ring-1 ring-amber-200">
                <L label={`Date du déplacement vers ${form.region} (obligatoire)`}>
                  <input type="date" className={inp} value={form.region_effective_from || ""}
                         onChange={(e) => setForm({ ...form, region_effective_from: e.target.value })} />
                </L>
                <p className="mt-2 text-[11px] text-amber-700">
                  Tout ce qui a été fait avant cette date reste à <b>{form._region0 || "—"}</b> et n'est pas recalculé.
                  Le mois du déplacement s'affichera en deux lignes, une par région.
                </p>
              </div>
            )}
            <L label="Distance (km / mois)"><input type="number" className={inp} value={form.distance} onChange={(e) => setForm({ ...form, distance: e.target.value })} /></L>
          </Modal>
        );
      })()}
    </div>
  );
}

function DestsPanel({ readOnly = false }) {
  const [dests, setDests] = useState([]);
  const [form, setForm] = useState(null);
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);
  const load = () => api.destinations().then(setDests).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const exportExcel = async () => {
    setExporting(true); setErr("");
    try { downloadBlob(await api.exportDestinations(), "Destinations.xlsx"); }
    catch (e) { setErr(e.message); }
    finally { setExporting(false); }
  };

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
      <div className="flex flex-wrap items-center gap-3">
        {!readOnly && <button onClick={() => setForm({ category: "", name: "", price_micro: 0, price_otokar: 0, price_bus: 0 })} className={btnPrimary}>+ Destination</button>}
        <button onClick={exportExcel} disabled={exporting || dests.length === 0}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50">
          {exporting ? "Export…" : "⬇️ Exporter Excel"}
        </button>
      </div>
      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="stack w-full text-sm">
          <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
            <th className="px-3 py-2">Catégorie</th><th>Destination</th><th className="text-right">MICRO</th><th className="text-right">OTOKAR</th><th className="text-right">BUS</th>{!readOnly && <th></th>}
          </tr></thead>
          <tbody>
            {dests.map((d) => (
              <tr key={d.id} className="border-t border-slate-100">
                <td className="px-3 py-2 text-slate-400">{d.category}</td>
                <td className="font-semibold text-slate-700">{d.name}</td>
                <td className="text-right">{d.price_micro || "—"}</td><td className="text-right">{d.price_otokar || "—"}</td><td className="text-right">{d.price_bus || "—"}</td>
                {!readOnly && (
                  <td className="whitespace-nowrap pr-3 text-right">
                    <button onClick={() => setForm({ ...d })} className="px-2.5 py-1.5 text-base text-slate-400 hover:text-sky-600">✎</button>
                    <button onClick={() => del(d)} className="px-2.5 py-1.5 text-base text-slate-400 hover:text-rose-600">🗑</button>
                  </td>
                )}
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

function ConfigPanel({ readOnly = false }) {
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
        <L label="Coupure Matin/Soir (h)"><input type="number" disabled={readOnly} className={inp} value={cfg.cut_morn} onChange={(e) => setCfg({ ...cfg, cut_morn: e.target.value })} /></L>
        <L label="Coupure Soir/Nuit (h)"><input type="number" disabled={readOnly} className={inp} value={cfg.cut_night} onChange={(e) => setCfg({ ...cfg, cut_night: e.target.value })} /></L>
      </div>
      {!readOnly && <button onClick={save} className={btnPrimary}>Enregistrer</button>}
      {msg && <span className="ml-3 text-sm text-emerald-600">{msg}</span>}
    </div>
  );
}

const frDate = (s) => (s ? s.split("-").reverse().join("/") : "—");

function PricePeriodsPanel({ readOnly = false }) {
  const [dests, setDests] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [from, setFrom] = useState("2025-01-01");
  const [to, setTo] = useState("2025-12-31");
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);

  const loadPeriods = () => api.pricePeriods().then(setPeriods).catch((e) => setErr(e.message));
  useEffect(() => { api.destinations().then(setDests).catch(() => {}); loadPeriods(); }, []);

  const exportExcel = async () => {
    setExporting(true); setErr("");
    try {
      const blob = await api.exportPricePeriods();
      downloadBlob(blob, "Tarifs_anterieurs.xlsx");
    } catch (e) { setErr(e.message); }
    finally { setExporting(false); }
  };

  // distinct saved periods (by date range), for quick re-selection
  const savedPeriods = useMemo(() => {
    const m = new Map();
    periods.forEach((p) => {
      const k = `${p.effective_from}|${p.effective_to || ""}`;
      if (!m.has(k)) m.set(k, { from: p.effective_from, to: p.effective_to || "", count: 0 });
      m.get(k).count++;
    });
    return [...m.values()].sort((a, b) => (a.from < b.from ? 1 : -1));
  }, [periods]);

  // prices already entered for the currently selected range
  const byDest = useMemo(() => {
    const m = {};
    periods.filter((p) => p.effective_from === from && (p.effective_to || "") === to).forEach((p) => { m[p.dest_name] = p; });
    return m;
  }, [periods, from, to]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? dests.filter((d) => d.name.toLowerCase().includes(s) || (d.category || "").toLowerCase().includes(s)) : dests;
  }, [dests, q]);

  const saveRow = async (dest, vals) => {
    setErr("");
    const empty = vals.micro === "" && vals.otokar === "" && vals.bus === "";
    try {
      const existing = byDest[dest.name];
      if (empty) {
        if (existing) await api.deletePricePeriod(existing.id);
      } else {
        await api.setPricePeriod({
          dest_name: dest.name, effective_from: from, effective_to: to || null,
          price_micro: Number(vals.micro) || 0, price_otokar: Number(vals.otokar) || 0, price_bus: Number(vals.bus) || 0,
        });
      }
      loadPeriods();
    } catch (e) { setErr(e.message); }
  };

  const presetYear = (y) => { setFrom(`${y}-01-01`); setTo(`${y}-12-31`); };
  const yNow = new Date().getFullYear();
  const filledCount = Object.keys(byDest).length;

  return (
    <div className="space-y-4">
      {err && <Err msg={err} />}

      <div className="flex justify-end">
        <button onClick={exportExcel} disabled={exporting || periods.length === 0}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50">
          {exporting ? "Export…" : "⬇️ Exporter Excel"}
        </button>
      </div>

      {/* Step 1 — choose the period */}
      <div className="rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200">
        <div className="text-sm font-bold text-[#1a3a5c]">1️⃣ Choisissez la période</div>
        <p className="mb-3 text-xs text-slate-400">Les excursions <b>datées dans cette période</b> utiliseront les prix saisis ci-dessous. En dehors, ce sont les prix actuels (onglet Destinations).</p>
        <div className="flex flex-wrap items-end gap-3">
          <L label="Du"><input type="date" disabled={readOnly} className={inp} value={from} onChange={(e) => setFrom(e.target.value)} /></L>
          <L label="Au"><input type="date" disabled={readOnly} className={inp} value={to} onChange={(e) => setTo(e.target.value)} /></L>
          {!readOnly && (
            <div className="flex gap-1">
              {[yNow - 1, yNow - 2].map((y) => (
                <button key={y} onClick={() => presetYear(y)} className="rounded-lg bg-amber-100 px-2.5 py-2 text-xs font-bold text-amber-700 hover:bg-amber-200">Année {y}</button>
              ))}
            </div>
          )}
        </div>
        {savedPeriods.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-slate-400">Périodes enregistrées :</span>
            {savedPeriods.map((p) => {
              const on = p.from === from && p.to === to;
              return <button key={p.from + p.to} onClick={() => { setFrom(p.from); setTo(p.to); }}
                className={`rounded-lg px-2 py-1 font-semibold ${on ? "bg-[#1a3a5c] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
                {frDate(p.from)} → {frDate(p.to)} ({p.count})</button>;
            })}
          </div>
        )}
      </div>

      {/* Step 2 — enter the prices */}
      <div className="rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-[#1a3a5c]">2️⃣ Saisissez les anciens prix</div>
          <span className="text-xs text-slate-400">{filledCount} renseigné(s)</span>
        </div>
        <p className="mb-2 text-xs text-slate-400">Remplissez <b>uniquement</b> les destinations dont le prix était différent — les autres gardent leur prix actuel. (Videz les 3 cases pour retirer une destination.)</p>
        <input placeholder="🔎 Rechercher une destination…" value={q} onChange={(e) => setQ(e.target.value)} className={inp + " mb-2 max-w-xs"} />
        <div className="overflow-x-auto rounded-xl ring-1 ring-slate-100">
          <table className="stack w-full text-sm">
            <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
              <th className="px-3 py-2">Destination</th>
              <th className="text-right">Actuel (M/O/B)</th>
              <th className="text-right">MICRO</th><th className="text-right">OTOKAR</th><th className="text-right pr-3">BUS</th>
            </tr></thead>
            <tbody>
              {filtered.map((d) => (
                <PriceRow key={d.id} dest={d} period={byDest[d.name]} readOnly={readOnly} onSave={saveRow} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function PriceRow({ dest, period, readOnly, onSave }) {
  const init = (p) => ({
    micro: p ? String(p.price_micro) : "", otokar: p ? String(p.price_otokar) : "", bus: p ? String(p.price_bus) : "",
  });
  const [v, setV] = useState(init(period));
  useEffect(() => { setV(init(period)); }, [period]);
  const commit = () => {
    const cur = init(period);
    if (v.micro === cur.micro && v.otokar === cur.otokar && v.bus === cur.bus) return; // unchanged
    onSave(dest, v);
  };
  const cell = "w-20 rounded-lg border border-slate-200 px-2 py-1 text-right text-sm outline-none focus:border-amber-400 disabled:bg-slate-50";
  return (
    <tr className="border-t border-slate-100">
      <td className="px-3 py-2 font-semibold text-slate-700">{dest.name}<div className="text-[11px] font-normal text-slate-400">{dest.category}</div></td>
      <td className="whitespace-nowrap text-right text-xs text-slate-400">{dest.price_micro || "—"} / {dest.price_otokar || "—"} / {dest.price_bus || "—"}</td>
      <td className="text-right"><input disabled={readOnly} type="number" value={v.micro} placeholder={dest.price_micro || "0"} onChange={(e) => setV({ ...v, micro: e.target.value })} onBlur={commit} className={cell} /></td>
      <td className="text-right"><input disabled={readOnly} type="number" value={v.otokar} placeholder={dest.price_otokar || "0"} onChange={(e) => setV({ ...v, otokar: e.target.value })} onBlur={commit} className={cell} /></td>
      <td className="py-1.5 pr-3 text-right"><input disabled={readOnly} type="number" value={v.bus} placeholder={dest.price_bus || "0"} onChange={(e) => setV({ ...v, bus: e.target.value })} onBlur={commit} className={cell} /></td>
    </tr>
  );
}

function RegionPeriodsPanel({ readOnly = false }) {
  const [buses, setBuses] = useState([]);
  const [busId, setBusId] = useState("");
  const [periods, setPeriods] = useState([]);
  const [form, setForm] = useState(null); // {id?, effective_from, effective_to, region}
  const [move, setMove] = useState(null); // {region, moved_on} — record a change of region
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api.buses().then((b) => { setBuses(b); if (b[0]) setBusId(String(b[0].id)); }).catch((e) => setErr(e.message));
  }, []);
  const loadPeriods = () => api.regionPeriods().then(setPeriods).catch((e) => setErr(e.message));
  useEffect(() => { loadPeriods(); }, []);

  const exportExcel = async () => {
    setExporting(true); setErr("");
    try {
      const blob = await api.exportRegionPeriods();
      downloadBlob(blob, "Regions_par_saison.xlsx");
    } catch (e) { setErr(e.message); }
    finally { setExporting(false); }
  };

  const bus = buses.find((b) => String(b.id) === busId);
  const busPeriods = useMemo(
    () => periods.filter((p) => String(p.bus_id) === busId).sort((a, b) => (a.effective_from < b.effective_from ? 1 : -1)),
    [periods, busId]
  );

  const save = async () => {
    setErr("");
    try {
      await api.setRegionPeriod({
        bus_id: Number(busId), effective_from: form.effective_from,
        effective_to: form.effective_to || null, region: form.region,
      });
      setForm(null); loadPeriods();
    } catch (e) { setErr(e.message); }
  };
  const del = async (p) => {
    if (!confirm(`Supprimer cette période (${p.region}, dès ${frDate(p.effective_from)}) ?`)) return;
    try { await api.deleteRegionPeriod(p.id); loadPeriods(); } catch (e) { setErr(e.message); }
  };
  const saveMove = async () => {
    setErr("");
    try {
      await api.moveRegion({ bus_id: Number(busId), region: move.region, moved_on: move.moved_on });
      setMove(null); loadPeriods(); api.buses().then(setBuses).catch(() => {});
    } catch (e) { setErr(e.message); }
  };

  return (
    <div className="space-y-4">
      {err && <Err msg={err} />}
      <div className="rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200">
        <p className="mb-3 text-xs text-slate-400">
          Un véhicule peut changer de région selon la saison. <b className="text-slate-500">Le véhicule bouge
          aujourd'hui ? Utilisez « ↷ Déplacer »</b> : la période en cours est fermée la veille et la nouvelle
          commence à la date du déplacement. Le Calendrier et l'Analyse découpent alors le mois en deux lignes,
          une par région — les sorties déjà faites gardent la leur, à la date exacte, et rien n'est recalculé.
          Le bouton « + Période » sert à saisir l'historique ancien. Sans aucune période, la région actuelle
          (onglet Véhicules) s'applique à tous les mois — rien ne change pour les véhicules concernés.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <select value={busId} onChange={(e) => setBusId(e.target.value)} className={inp + " max-w-xs"}>
            {buses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button onClick={exportExcel} disabled={exporting || periods.length === 0}
            className="ml-auto rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50">
            {exporting ? "Export…" : "⬇️ Exporter Excel"}
          </button>
          {!readOnly && (
            <>
              <button onClick={() => setMove({ region: REGIONS.find((r) => r !== bus?.region) || REGIONS[0], moved_on: new Date().toISOString().slice(0, 10) })}
                className="rounded-xl bg-amber-500 px-4 py-2 text-sm font-bold text-white shadow hover:bg-amber-600">
                ↷ Déplacer
              </button>
              <button onClick={() => setForm({ effective_from: "", effective_to: "", region: bus?.region || REGIONS[0] })} className={btnPrimary}>
                + Période
              </button>
            </>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="stack w-full text-sm">
          <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
            <th className="px-3 py-2">Du</th><th>Au</th><th>Région</th>{!readOnly && <th></th>}
          </tr></thead>
          <tbody>
            {busPeriods.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-6 text-center text-sm text-slate-400">
                Aucune période — région actuelle appliquée à tous les mois ({bus?.region || "—"}).
              </td></tr>
            )}
            {busPeriods.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="px-3 py-2">{frDate(p.effective_from)}</td>
                <td>{p.effective_to ? frDate(p.effective_to) : "—"}</td>
                <td className="font-semibold text-slate-700">{p.region}</td>
                {!readOnly && (
                  <td className="whitespace-nowrap pr-3 text-right">
                    <button onClick={() => setForm({ id: p.id, effective_from: p.effective_from, effective_to: p.effective_to || "", region: p.region })} className="px-2.5 py-1.5 text-base text-slate-400 hover:text-sky-600">✎</button>
                    <button onClick={() => del(p)} className="px-2.5 py-1.5 text-base text-slate-400 hover:text-rose-600">🗑</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {form && (
        <Modal title={`${form.id ? "Modifier" : "Nouvelle"} période — ${bus?.name || ""}`} onClose={() => setForm(null)} onSave={save} canSave={!!form.effective_from && !!form.region}>
          <div className="grid grid-cols-2 gap-3">
            <L label="Du">
              <input type="date" disabled={!!form.id} className={inp + (form.id ? " bg-slate-50 text-slate-400" : "")}
                value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />
            </L>
            <L label="Au (optionnel)"><input type="date" className={inp} value={form.effective_to} onChange={(e) => setForm({ ...form, effective_to: e.target.value })} /></L>
          </div>
          {form.id && <p className="text-xs text-slate-400">La date de début ne peut pas être modifiée — supprimez et recréez la période pour la changer.</p>}
          <L label="Région"><select className={inp} value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })}>{REGIONS.map((r) => <option key={r}>{r}</option>)}</select></L>
        </Modal>
      )}

      {move && (
        <Modal title={`Déplacer — ${bus?.name || ""}`} onClose={() => setMove(null)} onSave={saveMove}
               canSave={!!move.moved_on && !!move.region}>
          <div className="grid grid-cols-2 gap-3">
            <L label="Nouvelle région"><select className={inp} value={move.region} onChange={(e) => setMove({ ...move, region: e.target.value })}>{REGIONS.map((r) => <option key={r}>{r}</option>)}</select></L>
            <L label="Premier jour dans la nouvelle région"><input type="date" className={inp} value={move.moved_on} onChange={(e) => setMove({ ...move, moved_on: e.target.value })} /></L>
          </div>
          <div className="rounded-xl bg-amber-50 p-3 text-[11px] text-amber-700 ring-1 ring-amber-200">
            La période en cours (<b>{bus?.region || "—"}</b>) sera fermée la veille. Tout ce qui a déjà été
            enregistré avant cette date reste à <b>{bus?.region || "—"}</b>, avec ses recettes — rien n'est
            déplacé ni recalculé. Sur le mois du déplacement, le véhicule apparaîtra sur deux lignes, une par
            région, chacune avec ses propres jours ; leur somme redonne exactement le total du contrat.
          </div>
        </Modal>
      )}
    </div>
  );
}

const inp = "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
const btnPrimary = "rounded-xl bg-[#1a3a5c] px-4 py-2 text-sm font-bold text-white shadow hover:bg-[#234d77]";
const L = ({ label, children }) => (<label className="block"><span className="mb-1 block text-xs font-semibold text-slate-500">{label}</span>{children}</label>);
const Err = ({ msg }) => <div className="rounded-lg bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">{msg}</div>;
const SubTab = ({ on, onClick, children }) => (
  <button onClick={onClick} className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold ${on ? "bg-white text-[#1a3a5c] shadow" : "text-slate-500"}`}>{children}</button>
);

function Modal({ title, children, onClose, onSave, canSave }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div className="safe-bottom max-h-[92vh] w-full max-w-md space-y-3 overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-[#1a3a5c]">{title}</h3>
        {children}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="h-11 rounded-xl px-4 py-2 text-sm font-semibold text-slate-500 hover:bg-slate-100">Annuler</button>
          <button onClick={onSave} disabled={!canSave} className="h-11 rounded-xl bg-[#1a3a5c] px-5 py-2 text-sm font-bold text-white hover:bg-[#234d77] disabled:opacity-50">Enregistrer</button>
        </div>
      </div>
    </div>
  );
}
