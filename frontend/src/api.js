// Central API client. Base URL is overridable for production (Vercel env).
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function authToken() {
  try { return JSON.parse(localStorage.getItem("bus_auth") || "null")?.token || ""; }
  catch { return ""; }
}

async function req(path, opts = {}) {
  const token = authToken();
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    // Session expired/invalid while we DID send a token -> log out to the login screen.
    if (res.status === 401 && token) {
      localStorage.removeItem("bus_auth");
      location.reload();
      throw new Error("Session expirée — reconnectez-vous.");
    }
    let msg = `Erreur ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  login: (username, password) => req(`/api/login`, { method: "POST", body: JSON.stringify({ username, password }) }),
  calendar: (y, m) => req(`/api/calendar/${y}/${m}`),
  buses: () => req(`/api/buses`),
  destinations: () => req(`/api/destinations`),
  config: () => req(`/api/config`),
  getDay: (busId, iso) => req(`/api/day/${busId}/${iso}`),
  coverage: (busId, iso) => req(`/api/coverage/${busId}/${iso}`),
  saveDay: (payload) => req(`/api/day`, { method: "POST", body: JSON.stringify(payload) }),

  excursionsForDay: (busId, iso) => req(`/api/excursions/day/${busId}/${iso}`),
  createExcursion: (p) => req(`/api/excursions`, { method: "POST", body: JSON.stringify(p) }),
  updateExcursion: (id, p) => req(`/api/excursions/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  deleteExcursion: (id) => req(`/api/excursions/${id}`, { method: "DELETE" }),

  contracts: (busId) => req(`/api/contracts?bus_id=${busId}`),
  createContract: (p) => req(`/api/contracts`, { method: "POST", body: JSON.stringify(p) }),
  updateContract: (id, p) => req(`/api/contracts/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  deleteContract: (id) => req(`/api/contracts/${id}`, { method: "DELETE" }),

  fuel: (busId) => req(`/api/fuel?bus_id=${busId}`),
  setFuel: (p) => req(`/api/fuel`, { method: "PUT", body: JSON.stringify(p) }),

  createBus: (p) => req(`/api/buses`, { method: "POST", body: JSON.stringify(p) }),
  updateBus: (id, p) => req(`/api/buses/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  deleteBus: (id) => req(`/api/buses/${id}`, { method: "DELETE" }),

  createDest: (p) => req(`/api/destinations`, { method: "POST", body: JSON.stringify(p) }),
  updateDest: (id, p) => req(`/api/destinations/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  deleteDest: (id) => req(`/api/destinations/${id}`, { method: "DELETE" }),

  setConfig: (p) => req(`/api/config`, { method: "PUT", body: JSON.stringify(p) }),

  audit: () => req(`/api/audit`),

  pushKey: () => req(`/api/push/key`),
  pushSubscribe: (sub) => req(`/api/push/subscribe`, { method: "POST", body: JSON.stringify(sub) }),
  pushUnsubscribe: (sub) => req(`/api/push/unsubscribe`, { method: "POST", body: JSON.stringify(sub) }),
  notifyTest: () => req(`/api/notify/test`, { method: "POST" }),
};
