import { useState } from "react";
import { api } from "../api.js";
import Logo from "./Logo.jsx";

export default function Login({ onLogin }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const res = await api.login(u, p);
      localStorage.setItem("bus_auth", JSON.stringify(res));
      onLogin(res);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-[#0c1f3a] via-[#1a3a5c] to-[#21507e] p-4">
      {/* soft gold glow accents */}
      <div className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-amber-400/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-sky-400/10 blur-3xl" />

      <form onSubmit={submit} className="relative w-full max-w-sm overflow-hidden rounded-3xl bg-white shadow-2xl ring-1 ring-white/20">
        {/* gold top accent */}
        <div className="h-1.5 w-full bg-gradient-to-r from-amber-300 via-amber-500 to-amber-300" />

        <div className="p-8">
          <div className="mb-7 flex flex-col items-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#1a3a5c] shadow-lg ring-1 ring-black/5">
              <Logo className="h-10 w-10" />
            </div>
            <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-[#1a3a5c]">Bestimetravel</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="h-px w-5 bg-amber-400" />
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-600">Gestion des Bus</p>
              <span className="h-px w-5 bg-amber-400" />
            </div>
          </div>

          {err && <div className="mb-4 rounded-xl bg-rose-50 px-3 py-2.5 text-sm font-medium text-rose-700 ring-1 ring-rose-100">{err}</div>}

          <label className="mb-1 block text-xs font-semibold text-slate-500">Utilisateur</label>
          <input autoFocus placeholder="Votre identifiant" value={u} onChange={(e) => setU(e.target.value)}
            className="mb-4 w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100" />

          <label className="mb-1 block text-xs font-semibold text-slate-500">Mot de passe</label>
          <div className="relative mb-6">
            <input type={show ? "text" : "password"} placeholder="••••••••" value={p} onChange={(e) => setP(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 pr-12 text-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100" />
            <button type="button" onClick={() => setShow(!show)} tabIndex={-1}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400 hover:text-slate-600">
              {show ? "Cacher" : "Voir"}
            </button>
          </div>

          <button disabled={busy || !u || !p}
            className="group w-full rounded-xl bg-[#1a3a5c] py-3.5 text-sm font-bold text-white shadow-lg transition hover:bg-[#234d77] hover:shadow-amber-500/20 disabled:opacity-50">
            {busy ? "Connexion…" : "Se connecter"}
          </button>

          <p className="mt-6 text-center text-[11px] text-slate-400">Bestimetravel · Location de bus · Tunisie</p>
        </div>
      </form>
    </div>
  );
}
