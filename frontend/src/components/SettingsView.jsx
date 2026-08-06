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
      <div className="flex flex-wrap gap-1 rounded-xl bg-slate-200 p-1 w-fit">
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

function BusesPanel({ readOnly = false }) {
  const [buses, setBuses] = useState([]);
  const [form, setForm] = useState(null);
  const [err, setErr] = useState("");
  const [exporting, setExporting] = useState(false);
  const load = () => api.buses().then(setBuses).catch((e) => setErr(e.message));
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
        distance: Number(form.distance) || 0, plate: form.plate || "" };
      if (form.id) await api.updateBus(form.id, p); else await api.createBus(p);
      setForm(null); load();
    } catch (e) { setErr(e.message); }
  };
  const del = async (b) => { if (!confirm(`Supprimer ${b.name} ?`)) return; try { await api.deleteBus(b.id); load(); } catch (e) { setErr(e.message); } };

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
      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-100 text-left text-xs text-slate-500">
            <th className="px-3 py-2">Nom</th><th>Type</th><th>Région</th><th className="text-right">Distance</th>{!readOnly && <th></th>}
          </tr></thead>
          <tbody>
            {buses.map((b) => (
              <tr key={b.id} className="border-t border-slate-100">
                <td className="px-3 py-2 font-semibold text-slate-700">{b.name}</td>
                <td>{b.type}</td><td>{b.region}</td>
                <td className="text-right">{b.distance ? Number(b.distance).toLocaleString("fr-FR") + " km" : "—"}</td>
                {!readOnly && (
                  <td className="whitespace-nowrap pr-3 text-right">
                    <button onClick={() => setForm({ ...b })} className="px-1 text-slate-400 hover:text-sky-600">✎</button>
                    <button onClick={() => del(b)} className="px-1 text-slate-400 hover:text-rose-600">🗑</button>
                  </td>
                )}
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
        <table className="w-full text-sm">
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
                    <button onClick={() => setForm({ ...d })} className="px-1 text-slate-400 hover:text-sky-600">✎</button>
                    <button onClick={() => del(d)} className="px-1 text-slate-400 hover:text-rose-600">🗑</button>
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
          <table className="w-full text-sm">
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

  return (
    <div className="space-y-4">
      {err && <Err msg={err} />}
      <div className="rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200">
        <p className="mb-3 text-xs text-slate-400">
          Un véhicule peut changer de région selon la saison. Ajoutez ici ses périodes passées — le Calendrier
          et l'Analyse d'un mois donné utilisent automatiquement la région en vigueur ce mois-là. Sans période
          définie, la région actuelle (onglet Véhicules) s'applique à tous les mois — rien ne change pour les
          véhicules qui n'en ont pas besoin.
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
            <button onClick={() => setForm({ effective_from: "", effective_to: "", region: bus?.region || REGIONS[0] })} className={btnPrimary}>
              + Période
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl bg-white shadow ring-1 ring-slate-200">
        <table className="w-full text-sm">
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
                    <button onClick={() => setForm({ id: p.id, effective_from: p.effective_from, effective_to: p.effective_to || "", region: p.region })} className="px-1 text-slate-400 hover:text-sky-600">✎</button>
                    <button onClick={() => del(p)} className="px-1 text-slate-400 hover:text-rose-600">🗑</button>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
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
