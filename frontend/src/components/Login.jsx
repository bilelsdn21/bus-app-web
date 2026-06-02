import { useState } from "react";
import { api } from "../api.js";

export default function Login({ onLogin }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#0f2444] via-[#1a3a5c] to-[#1e4976] p-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-3xl bg-white p-8 shadow-2xl">
        <div className="mb-6 text-center">
          <div className="text-3xl">🚌</div>
          <h1 className="mt-2 text-xl font-extrabold text-[#1a3a5c]">Bestimetravel</h1>
          <p className="text-xs text-slate-400">Gestion des Bus</p>
        </div>
        {err && <div className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
        <input autoFocus placeholder="Utilisateur" value={u} onChange={(e) => setU(e.target.value)}
          className="mb-3 w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" />
        <input type="password" placeholder="Mot de passe" value={p} onChange={(e) => setP(e.target.value)}
          className="mb-5 w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" />
        <button disabled={busy || !u || !p}
          className="w-full rounded-xl bg-[#1a3a5c] py-3 text-sm font-bold text-white shadow-lg hover:bg-[#234d77] disabled:opacity-50">
          {busy ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
