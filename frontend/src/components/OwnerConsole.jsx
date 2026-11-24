import { useCallback, useEffect, useMemo, useState } from "react";
import { api, downloadBlob } from "../api.js";
import { fmtTND } from "../colors.js";

// ---------------------------------------------------------------------------------------- helpers
const fmtAt = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const ago = (iso) => {
  if (!iso) return "jamais";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return "à l'instant";
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.round(s / 3600)} h`;
  return `il y a ${Math.round(s / 86400)} j`;
};
const uptime = (s) => (s < 3600 ? `${Math.round(s / 60)} min` : s < 86400 ? `${(s / 3600).toFixed(1)} h` : `${(s / 86400).toFixed(1)} j`);
const frDate = (v) => (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? `${v.slice(8, 10)}/${v.slice(5, 7)}/${v.slice(0, 4)}` : v);
const ENT = { contract: "Contrat", booking: "Sortie", fuel: "Carburant", destination: "Destination", price: "Prix", region: "Région", bus: "Véhicule", config: "Paramètres", rented: "Location", numbers: "Chiffres" };
const ENT_ICON = { contract: "📄", booking: "🚌", fuel: "⛽", destination: "📍", price: "💰", region: "🗺️", bus: "🚐", config: "⚙️", rented: "🚐", numbers: "📊" };
const LABELS = { loyer: "Loyer", start_date: "Début", end_date: "Fin", label: "Libellé", total: "Total", unit_price: "Prix unitaire", destination: "Destination", date: "Date", client: "Client", pax: "Passagers", type: "Type", heure_debut: "Heure début", heure_fin: "Heure fin", estimated: "Estimé", actual: "Réel", region: "Région", effective_from: "Du", effective_to: "Au", price_micro: "Prix micro", price_otokar: "Prix otokar", price_bus: "Prix bus", name: "Nom", plate: "Plaque", distance: "Distance", cost: "Coût", notes: "Notes", cut_morn: "Seuil matin", cut_night: "Seuil nuit", current_prices_since: "Prix actuels depuis", bus_id: "Véhicule (id)", sort_order: "Ordre", year: "Année", month: "Mois", category: "Catégorie", dest_name: "Destination", id: "N°" };
const MONEY = new Set(["loyer", "total", "unit_price", "estimated", "actual", "cost", "price_micro", "price_otokar", "price_bus"]);
const val = (k, v) => (v === null || v === undefined || v === "" ? "—" : MONEY.has(k) ? fmtTND(v) : frDate(String(v)));
const monthLabel = (ym) => { const [y, m] = ym.split("-"); return `${["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."][+m - 1]} ${y}`; };
const delta = (n) => `${n >= 0 ? "+" : "−"}${Math.abs(Math.round(n)).toLocaleString("fr-FR")} TND`;

const card = "rounded-2xl bg-white p-4 shadow ring-1 ring-slate-200";
const Chip = ({ on, onClick, children }) => (
  <button onClick={onClick} className={`h-9 shrink-0 whitespace-nowrap rounded-full px-3 text-xs font-semibold transition ${on ? "bg-[#1a3a5c] text-white shadow" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{children}</button>
);
const Stat = ({ label, value, tone = "slate", hint }) => (
  <div className={card}>
    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{label}</div>
    <div className={`mt-1 text-2xl font-extrabold ${{ slate: "text-slate-700", red: "text-rose-600", green: "text-emerald-600", amber: "text-amber-600" }[tone]}`}>{value}</div>
    {hint && <div className="mt-0.5 text-[11px] text-slate-400">{hint}</div>}
  </div>
);

// ---------------------------------------------------------------------------------------- one register entry
function Details({ r }) {
  const d = r.data || {};
  if (r.kind === "impact") {
    return (
      <div className="space-y-2">
        {(d.months || []).map((m) => (
          <div key={m.month} className="rounded-xl bg-slate-50 p-3 text-xs">
            <div className="flex items-baseline justify-between gap-2">
              <b className="text-slate-700">{monthLabel(m.month)}</b>
              <span className={`font-bold ${m.delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>Net {fmtTND(m.total_before)} → {fmtTND(m.total_after)} ({delta(m.delta)})</span>
            </div>
            {m.regions.map((g) => <div key={g.region} className="mt-1 text-slate-500">• {g.region} : {delta(g.delta)}</div>)}
          </div>
        ))}
      </div>
    );
  }
  if (r.kind === "snapshot") return <p className="text-xs text-slate-500">Chiffres de {(d.months || []).length} mois figés : {(d.months || []).map(monthLabel).join(", ")}.</p>;
  const keys = r.action === "update" ? Object.keys(d.after || {}) : Object.keys((r.action === "delete" ? d.before : d.after) || {}).filter((k) => k !== "id");
  const src = r.action === "delete" ? d.before : d.after;
  return (
    <div className="space-y-2">
      <table className="w-full text-xs">
        <tbody>
          {keys.map((k) => (
            <tr key={k} className="border-t border-slate-100 first:border-0">
              <td className="py-1 pr-3 font-semibold text-slate-400">{LABELS[k] || k}</td>
              {r.action === "update" ? (
                <td className="py-1 text-right"><span className="text-rose-600 line-through">{val(k, d.before?.[k])}</span> <span className="mx-1 text-slate-300">→</span> <b className="text-emerald-700">{val(k, d.after?.[k])}</b></td>
              ) : <td className={`py-1 text-right font-semibold ${r.action === "delete" ? "text-rose-600" : "text-slate-700"}`}>{val(k, src?.[k])}</td>}
            </tr>
          ))}
        </tbody>
      </table>
      {d.months?.length > 0 && <p className="text-[11px] text-slate-400">Mois concernés : {d.months.map(monthLabel).join(", ")}</p>}
    </div>
  );
}

export function EntryCard({ r, compact = false }) {
  const [open, setOpen] = useState(false);
  const tone = r.kind === "impact" ? "ring-sky-200 bg-sky-50/50" : r.sensitive ? "ring-amber-200" : "ring-slate-200";
  return (
    <div className={`rounded-2xl bg-white p-3 shadow ring-1 ${tone}`}>
      <button className="flex w-full items-start gap-2.5 text-left" onClick={() => setOpen(!open)}>
        <span className="mt-0.5 text-lg">{r.kind === "snapshot" ? "📸" : r.kind === "impact" ? "📊" : ENT_ICON[r.entity] || "•"}</span>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold leading-snug text-slate-700">{r.summary}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-slate-400">
            <span>{fmtAt(r.at)}</span><span>·</span>
            <b className="text-slate-600">{r.actor}</b>{r.role && <span>({r.role})</span>}
            {r.ip && <><span>·</span><span>{r.ip}</span></>}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {r.kind === "change" && <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${r.action === "delete" ? "bg-rose-100 text-rose-700" : r.action === "create" ? "bg-emerald-100 text-emerald-700" : "bg-sky-100 text-sky-700"}`}>{{ create: "ajout", update: "modif.", delete: "suppression" }[r.action] || r.action}</span>}
            {r.kind === "impact" && <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-sky-700">effet sur les chiffres</span>}
            {r.retroactive && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-700">↶ rétroactif</span>}
            {r.sensitive && r.kind === "change" && <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold uppercase text-rose-600">⚠ sensible</span>}
          </div>
        </div>
        <span className="text-slate-300">{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          <Details r={r} />
          <p className="font-mono text-[10px] text-slate-300">n° {r.id} · empreinte {r.hash}… · lot {String(r.batch || "").slice(0, 8)}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------- tabs
export function Overview({ ov, go }) {
  const i = ov.integrity, l = ov.ledger;
  const maxActor = Math.max(1, ...l.by_actor_7d.map((a) => a.count));
  return (
    <div className="space-y-4">
      <div className={`rounded-2xl p-4 shadow ring-1 ${i.ok === false ? "bg-rose-50 ring-rose-300" : "bg-emerald-50 ring-emerald-200"}`}>
        {i.ok === false ? (
          <>
            <div className="text-base font-extrabold text-rose-700">🚨 ALERTE — le registre a été altéré</div>
            <p className="mt-1 text-xs text-rose-700">Entrée n° {i.first_break?.id} : {i.first_break?.reason}</p>
          </>
        ) : (
          <>
            <div className="text-base font-extrabold text-emerald-700">🛡️ Registre intact</div>
            <p className="mt-1 text-xs text-emerald-700">{i.checked} entrée{i.checked > 1 ? "s" : ""} vérifiée{i.checked > 1 ? "s" : ""} : aucune n'a été modifiée, supprimée ni insérée.</p>
          </>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Modifications 24 h" value={l.last_24h} hint={`${l.last_7d} sur 7 jours`} />
        <Stat label="Rétroactives (30 j)" value={l.retroactive_30d} tone={l.retroactive_30d ? "amber" : "slate"} hint="touchent un mois passé" />
        <Stat label="Écarts non expliqués" value={i.unexplained_drift} tone={i.unexplained_drift ? "red" : "green"} hint="chiffres changés sans trace" />
        <Stat label="Connexions échouées" value={ov.security.failed_7d} tone={ov.security.failed_7d ? "amber" : "slate"} hint={`7 j · ${ov.security.logins_7d} réussies`} />
      </div>

      <div className={card}>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-bold text-[#1a3a5c]">⚠️ Dernières modifications sensibles</h3>
          <button onClick={() => go("ledger")} className="text-xs font-semibold text-sky-600">Tout voir →</button>
        </div>
        <div className="space-y-2">
          {l.recent_sensitive.length === 0 && <p className="text-xs text-slate-400">Aucune pour l'instant.</p>}
          {l.recent_sensitive.map((r) => <EntryCard key={r.id} r={r} />)}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className={card}>
          <h3 className="mb-3 text-sm font-bold text-[#1a3a5c]">Activité par utilisateur (7 jours)</h3>
          {l.by_actor_7d.length === 0 && <p className="text-xs text-slate-400">Aucune activité.</p>}
          <div className="space-y-2">
            {l.by_actor_7d.map((a) => (
              <div key={a.actor}>
                <div className="flex justify-between text-xs"><b className="text-slate-600">{a.actor}</b><span className="text-slate-400">{a.count}</span></div>
                <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-[#1a3a5c]" style={{ width: `${(a.count / maxActor) * 100}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
        <div className={card}>
          <h3 className="mb-3 text-sm font-bold text-[#1a3a5c]">Par type (30 jours)</h3>
          <div className="flex flex-wrap gap-2">
            {l.by_entity_30d.map((e) => <span key={e.entity} className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600">{ENT_ICON[e.entity]} {ENT[e.entity] || e.entity} · {e.count}</span>)}
            {l.by_entity_30d.length === 0 && <p className="text-xs text-slate-400">Aucune.</p>}
          </div>
          <p className="mt-4 text-[11px] text-slate-400">Dernier instantané des chiffres : {ago(i.last_snapshot)} · {i.snapshots} au total</p>
        </div>
      </div>
    </div>
  );
}

function Ledger({ users }) {
  const [filter, setFilter] = useState("all");      // all | sensitive | retro | impact | snapshot
  const [entity, setEntity] = useState("");
  const [actor, setActor] = useState("");
  const [q, setQ] = useState("");
  const [since, setSince] = useState("");
  const [rows, setRows] = useState(null);
  const [next, setNext] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const params = useMemo(() => {
    const p = { limit: "40" };
    if (filter === "sensitive") p.sensitive = "true";
    if (filter === "retro") p.retro = "true";
    if (filter === "impact") p.kind = "impact";
    if (filter === "snapshot") p.kind = "snapshot";
    if (entity) p.entity = entity;
    if (actor) p.actor = actor;
    if (q.trim()) p.q = q.trim();
    if (since) p.since = since;
    return p;
  }, [filter, entity, actor, q, since]);

  const load = useCallback((more = false, before = null) => {
    setBusy(true); setErr("");
    api.ownerLedger(before ? { ...params, before_id: String(before) } : params)
      .then((r) => { setRows((cur) => (more ? [...(cur || []), ...r.rows] : r.rows)); setNext(r.next_before_id); })
      .catch((e) => setErr(e.message)).finally(() => setBusy(false));
  }, [params]);
  useEffect(() => { const t = setTimeout(() => load(false), q ? 350 : 0); return () => clearTimeout(t); }, [load]);

  const exportXlsx = async () => { try { downloadBlob(await api.exportLedger(), "Registre_des_modifications.xlsx"); } catch (e) { setErr(e.message); } };
  const sel = "h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs";
  return (
    <div className="space-y-3">
      <div className="scroll-x -mx-3 flex gap-1.5 overflow-x-auto px-3 pb-1 sm:mx-0 sm:px-0">
        {[["all", "Tout"], ["sensitive", "⚠️ Sensibles"], ["retro", "↶ Rétroactives"], ["impact", "📊 Effets"], ["snapshot", "📸 Instantanés"]].map(([k, label]) => <Chip key={k} on={filter === k} onClick={() => setFilter(k)}>{label}</Chip>)}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select className={sel} value={entity} onChange={(e) => setEntity(e.target.value)}>
          <option value="">Tous les types</option>
          {Object.entries(ENT).filter(([k]) => k !== "numbers").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className={sel} value={actor} onChange={(e) => setActor(e.target.value)}>
          <option value="">Tous les utilisateurs</option>
          {users.map((u) => <option key={u.username} value={u.username}>{u.username}</option>)}
        </select>
        <input type="date" className={sel} value={since} onChange={(e) => setSince(e.target.value)} aria-label="Depuis le" />
        <input className={sel + " min-w-[140px] flex-1"} placeholder="Rechercher (véhicule, montant…)" value={q} onChange={(e) => setQ(e.target.value)} />
        <button onClick={exportXlsx} className="h-9 rounded-lg bg-emerald-600 px-3 text-xs font-bold text-white">⬇️ Excel</button>
      </div>
      {err && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
      {rows === null && <div className="py-8 text-center text-sm text-slate-400">Chargement…</div>}
      {rows && rows.length === 0 && <div className={card + " text-center text-sm text-slate-400"}>Aucune entrée pour ces filtres.</div>}
      <div className="space-y-2">{(rows || []).map((r) => <EntryCard key={r.id} r={r} />)}</div>
      {next && <button disabled={busy} onClick={() => load(true, next)} className="h-11 w-full rounded-xl bg-white text-sm font-semibold text-slate-600 shadow ring-1 ring-slate-200">{busy ? "…" : "Charger plus"}</button>}
    </div>
  );
}

function Integrity({ ov, reload }) {
  const [ver, setVer] = useState(null);
  const [drift, setDrift] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const run = async (key, fn) => { setBusy(key); setErr(""); try { await fn(); } catch (e) { setErr(e.message); } finally { setBusy(""); } };
  useEffect(() => { api.ownerDrift(false).then(setDrift).catch((e) => setErr(e.message)); }, []);
  const v = ver || { ok: ov.integrity.ok, checked: ov.integrity.checked, first_break: ov.integrity.first_break, head: ov.ledger.head && { id: ov.ledger.head.id, hash: ov.ledger.head.hash } };

  const DriftList = ({ title, sub, months }) => (
    <div className="space-y-2">
      <div><div className="text-sm font-bold text-[#1a3a5c]">{title}</div><div className="text-[11px] text-slate-400">{sub}</div></div>
      {months.length === 0 && <div className="rounded-xl bg-emerald-50 p-3 text-xs font-semibold text-emerald-700">✓ Aucun chiffre n'a changé sur cette période.</div>}
      {months.map((m) => (
        <div key={m.month} className={`rounded-2xl p-3 ring-1 ${m.explained ? "bg-white ring-slate-200" : "bg-rose-50 ring-rose-300"}`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <b className="text-slate-700">{monthLabel(m.month)}</b>
            <span className={`text-xs font-bold ${m.delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>Net {fmtTND(m.total_before)} → {fmtTND(m.total_after)} ({delta(m.delta)})</span>
          </div>
          <span className={`mt-1.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${m.explained ? "bg-emerald-100 text-emerald-700" : "bg-rose-600 text-white"}`}>
            {m.explained ? `expliqué par ${m.explained_by.length} modification${m.explained_by.length > 1 ? "s" : ""}` : "NON EXPLIQUÉ — aucune modification enregistrée"}
          </span>
          {m.regions.map((g) => <div key={g.region} className="mt-1 text-xs text-slate-500">• {g.region} : {delta(g.delta)}</div>)}
          {m.buses.slice(0, 5).map((b) => <div key={b.id} className="text-[11px] text-slate-400">   ↳ {b.name} : {delta(b.delta)}</div>)}
          {m.explained_by.slice(0, 4).map((e) => <div key={e.id} className="mt-1 text-[11px] text-slate-500">#{e.id} · {e.actor} · {e.summary.slice(0, 90)}</div>)}
        </div>
      ))}
    </div>
  );

  return (
    <div className="space-y-4">
      {err && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
      <div className={card}>
        <h3 className="text-sm font-bold text-[#1a3a5c]">🔗 Chaîne d'empreintes du registre</h3>
        <p className="mt-1 text-xs text-slate-500">Chaque entrée contient l'empreinte de la précédente : modifier, supprimer ou insérer une entrée casse la chaîne. La base de données refuse en plus toute modification ou suppression.</p>
        <div className={`mt-3 rounded-xl p-3 text-sm font-semibold ${v.ok === false ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>
          {v.ok === false ? `🚨 Rompue à l'entrée n° ${v.first_break?.id} — ${v.first_break?.reason}` : `✓ Intacte — ${v.checked} entrées vérifiées`}
        </div>
        {v.head && <p className="mt-2 break-all font-mono text-[10px] text-slate-400">Dernière entrée n° {v.head.id} — empreinte {v.head.hash}</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <button disabled={!!busy} onClick={() => run("ver", async () => setVer(await api.ownerVerify()))} className="h-11 rounded-xl bg-[#1a3a5c] px-4 text-sm font-bold text-white disabled:opacity-50">{busy === "ver" ? "Vérification…" : "Vérifier maintenant"}</button>
          <button onClick={() => run("exp", async () => downloadBlob(await api.exportLedger(), "Registre_des_modifications.xlsx"))} className="h-11 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white">⬇️ Copie Excel du registre</button>
        </div>
        <p className="mt-2 text-[11px] text-slate-400">Conseil : gardez régulièrement une copie hors de l'application (e-mail, cloud). L'empreinte du dernier élément prouve l'état du registre à cette date.</p>
      </div>

      <div className={card}>
        <h3 className="text-sm font-bold text-[#1a3a5c]">📸 Instantanés des chiffres affichés</h3>
        <p className="mt-1 text-xs text-slate-500">Chaque jour, les chiffres des 13 derniers mois (par région et par véhicule) sont figés dans le registre. Si un chiffre d'un mois passé change entre deux instantanés, il faut qu'une modification enregistrée l'explique : sinon c'est signalé en rouge.</p>
        <p className="mt-2 text-xs text-slate-400">Dernier instantané : {ago(ov.integrity.last_snapshot)} ({fmtAt(ov.integrity.last_snapshot)})</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button disabled={!!busy} onClick={() => run("snap", async () => { await api.ownerSnapshot(); setDrift(await api.ownerDrift(false)); reload(); })} className="h-11 rounded-xl bg-white px-4 text-sm font-bold text-[#1a3a5c] ring-1 ring-slate-300 disabled:opacity-50">{busy === "snap" ? "Calcul…" : "Prendre un instantané maintenant"}</button>
          <button disabled={!!busy} onClick={() => run("live", async () => setDrift(await api.ownerDrift(true)))} className="h-11 rounded-xl bg-amber-500 px-4 text-sm font-bold text-[#13294a] disabled:opacity-50">{busy === "live" ? "Comparaison…" : "Comparer aux chiffres actuels"}</button>
        </div>
      </div>

      {drift?.live && <div className={card}><DriftList title="Chiffres actuels comparés au dernier instantané" sub={`depuis le ${fmtAt(drift.live.since)}`} months={drift.live.months} /></div>}
      {drift?.between ? <div className={card}><DriftList title="Entre les deux derniers instantanés" sub={`${fmtAt(drift.between.from)} → ${fmtAt(drift.between.to)}`} months={drift.between.months} /></div>
        : drift && <div className={card + " text-xs text-slate-400"}>Il faut au moins deux instantanés pour comparer. Un nouveau est pris automatiquement chaque jour.</div>}
    </div>
  );
}

export function Security({ ov }) {
  const s = ov.security;
  const tone = { "Connexion": "bg-emerald-100 text-emerald-700", "Connexion échouée": "bg-rose-100 text-rose-700", "Déconnexion": "bg-slate-200 text-slate-600" };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Connexions (7 j)" value={s.logins_7d} tone="green" />
        <Stat label="Échecs (7 j)" value={s.failed_7d} tone={s.failed_7d ? "red" : "slate"} />
        <Stat label="Adresses IP" value={s.distinct_ips_7d} hint="distinctes (7 j)" />
      </div>
      <div className={card}>
        <h3 className="mb-2 text-sm font-bold text-[#1a3a5c]">Dernières connexions</h3>
        <div className="space-y-2">
          {s.recent.map((r, i) => (
            <div key={i} className="flex items-start gap-2 border-t border-slate-100 pt-2 first:border-0 first:pt-0 text-xs">
              <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${tone[r.event] || "bg-slate-100"}`}>{r.event === "Connexion échouée" ? "échec" : r.event === "Connexion" ? "entrée" : "sortie"}</span>
              <div className="min-w-0 flex-1"><b className="text-slate-700">{r.user}</b> <span className="text-slate-400">· {r.detail}</span></div>
              <span className="shrink-0 text-slate-400">{ago(r.at)}</span>
            </div>
          ))}
          {s.recent.length === 0 && <p className="text-xs text-slate-400">Aucune connexion enregistrée.</p>}
        </div>
      </div>
    </div>
  );
}

export function System({ ov }) {
  const sv = ov.server;
  const me = ov.users.find((u) => u.role === "owner");
  const Row = ({ k, v, tone }) => (<div className="flex justify-between gap-3 border-t border-slate-100 py-2 text-sm first:border-0"><span className="text-slate-400">{k}</span><b className={tone || "text-slate-700"}>{v}</b></div>);
  return (
    <div className="space-y-4">
      <div className={card}>
        <h3 className="mb-1 text-sm font-bold text-[#1a3a5c]">Serveur</h3>
        <Row k="Base de données" v={`${sv.db_ok ? "✓ connectée" : "✗ injoignable"} (${sv.db}, ${sv.db_ms} ms)`} tone={sv.db_ok ? "text-emerald-600" : "text-rose-600"} />
        <Row k="Démarré depuis" v={uptime(sv.uptime_s)} />
        <Row k="Version déployée" v={sv.commit || "—"} />
        <Row k="Service" v={sv.service || "—"} />
        <Row k="Python" v={sv.python} />
        <Row k="Erreurs d'enregistrement du registre" v={sv.register_errors} tone={sv.register_errors ? "text-rose-600" : "text-emerald-600"} />
        {sv.register_last_error && <p className="mt-1 break-all text-[11px] text-rose-600">{sv.register_last_error}</p>}
      </div>
      <div className={card}>
        <h3 className="mb-1 text-sm font-bold text-[#1a3a5c]">Comptes</h3>
        {ov.users.map((u) => <Row key={u.username} k={`${u.username} (${u.role})`} v={u.push_devices ? `🔔 ${u.push_devices} appareil${u.push_devices > 1 ? "s" : ""}` : "🔕 aucune notification"} />)}
        {me && me.push_devices === 0 && <p className="mt-2 rounded-lg bg-amber-50 p-2 text-[11px] text-amber-700">Vous ne recevrez pas les alertes de modifications sensibles : activez la cloche 🔔 sur ce téléphone.</p>}
      </div>
      <div className={card}>
        <h3 className="mb-1 text-sm font-bold text-[#1a3a5c]">Contenu de la base</h3>
        {Object.entries(ov.tables).map(([k, n]) => <Row key={k} k={k} v={n.toLocaleString("fr-FR")} />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------- the console
export default function OwnerConsole({ onSeen }) {
  const [tab, setTab] = useState("overview");
  const [ov, setOv] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    api.ownerOverview().then((r) => { setOv(r); setErr(""); onSeen?.(r.ledger.head?.id || 0); }).catch((e) => setErr(e.message));
  }, [onSeen]);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);

  const tabs = [["overview", "🛰️ Vue d'ensemble"], ["ledger", "📒 Registre"], ["integrity", "🛡️ Intégrité"], ["security", "🔐 Sécurité"], ["system", "🖥️ Système"]];
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">🛰️ Console propriétaire</h1>
          <p className="text-[11px] text-slate-400">Tout ce qui touche aux chiffres est enregistré ici, définitivement.</p>
        </div>
        <button onClick={load} className="h-9 rounded-lg bg-white px-3 text-xs font-semibold shadow ring-1 ring-slate-200">↻</button>
      </div>
      <div className="scroll-x -mx-3 flex gap-1.5 overflow-x-auto px-3 pb-1 sm:mx-0 sm:px-0">
        {tabs.map(([k, label]) => <Chip key={k} on={tab === k} onClick={() => setTab(k)}>{label}</Chip>)}
      </div>
      {err && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{err}</div>}
      {!ov && !err && <div className="py-10 text-center text-sm text-slate-400">Chargement de la console…</div>}
      {ov && tab === "overview" && <Overview ov={ov} go={setTab} />}
      {ov && tab === "ledger" && <Ledger users={ov.users} />}
      {ov && tab === "integrity" && <Integrity ov={ov} reload={load} />}
      {ov && tab === "security" && <Security ov={ov} />}
      {ov && tab === "system" && <System ov={ov} />}
    </div>
  );
}
