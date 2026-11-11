// Central API client. Base URL is overridable for production (Vercel env).
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function authToken() {
  try { return JSON.parse(localStorage.getItem("bus_auth") || "null")?.token || ""; }
  catch { return ""; }
}

async function reqBlob(path) {
  const token = authToken();
  const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) {
    let msg = `Erreur ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.blob();
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

// ---- stale-while-revalidate cache for GETs --------------------------------------
// The last good answer of every GET is kept in memory + localStorage, so a page can
// paint instantly from it (api.peek) while the fresh answer loads in the background.
const mem = new Map();
// Saved answers belong to ONE backend and ONE data format: the key includes the API address
// and a version, so switching backend (or changing the response shape) can never show old data.
const CACHE_VERSION = 3;
const LS = `bus_cache:v${CACHE_VERSION}:${BASE}:`;
try {   // drop anything saved under another backend/version
  Object.keys(localStorage).filter((k) => k.startsWith("bus_cache:") && !k.startsWith(LS)).forEach((k) => localStorage.removeItem(k));
} catch {}
export function peek(path) {
  if (mem.has(path)) return mem.get(path);
  try {
    const raw = localStorage.getItem(LS + path);
    if (raw) { const v = JSON.parse(raw); mem.set(path, v); return v; }
  } catch {}
  return null;
}
function remember(path, data) {
  mem.set(path, data);
  try { localStorage.setItem(LS + path, JSON.stringify(data)); }
  catch { // quota: drop old entries, they are only an optimisation
    try { Object.keys(localStorage).filter((k) => k.startsWith("bus_cache:")).forEach((k) => localStorage.removeItem(k)); } catch {}
  }
}
export function clearCache() {
  mem.clear();
  try { Object.keys(localStorage).filter((k) => k.startsWith(LS)).forEach((k) => localStorage.removeItem(k)); } catch {}
}
// de-duplicate identical in-flight GETs (e.g. prefetch + real load)
const inflight = new Map();

async function req(path, opts = {}) {
  const isGet = !opts.method || opts.method === "GET";
  if (isGet && inflight.has(path)) return inflight.get(path);
  const p = doReq(path, opts, isGet);
  if (isGet) { inflight.set(path, p); p.finally(() => inflight.delete(path)).catch(() => {}); }
  return p;
}

// A server that is (re)starting answers with an HTML placeholder or a 502/503/504 instead
// of JSON. Reads are retried a few times (they are safe to repeat); writes never are, so
// nothing can be saved twice. After that the user gets a readable message, not a parse error.
const WAKING = "Le serveur démarre, réessayez dans quelques secondes.";
class Transient extends Error {}

async function doReq(path, opts, isGet) {
  // A sleeping free-tier server needs up to ~60 s to boot and answers with error pages
  // meanwhile, so reads keep trying for about a minute before giving up.
  const tries = isGet ? 15 : 1;
  for (let i = 0; i < tries; i++) {
    try { return await attempt(path, opts, isGet); }
    catch (e) {
      if (!(e instanceof Transient)) throw e;
      if (i === tries - 1) throw new Error(WAKING);
      await new Promise((r) => setTimeout(r, 4000));
    }
  }
}

async function attempt(path, opts, isGet) {
  const token = authToken();
  let res;
  try {
    res = await fetch(BASE + path, {
      ...opts,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(opts.headers || {}),
      },
    });
  } catch { throw new Transient(); }          // network error / server not reachable yet
  if ([502, 503, 504].includes(res.status)) throw new Transient();
  const isJson = (res.headers.get("content-type") || "").includes("json");
  if (res.ok && res.status !== 204 && !isJson) throw new Transient();   // HTML placeholder page
  if (!res.ok) {
    // Session expired/invalid while we DID send a token -> log out to the login screen.
    if (res.status === 401 && token) {
      localStorage.removeItem("bus_auth");
      clearCache();
      location.reload();
      throw new Error("Session expirée — reconnectez-vous.");
    }
    let msg = `Erreur ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  const data = res.status === 204 ? null : await res.json();
  if (isGet) remember(path, data);
  return data;
}

export const api = {
  peek: {
    calendar: (y, m) => peek(`/api/calendar/${y}/${m}`),
    analytics: (y, m) => peek(`/api/analytics/${y}/${m}`),
    destinations: () => peek(`/api/destinations`),
  },
  login: (username, password) => req(`/api/login`, { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => req(`/api/logout`, { method: "POST" }),
  calendar: (y, m) => req(`/api/calendar/${y}/${m}`),
  buses: () => req(`/api/buses`),
  // vehicles + the facts the Paramètres > Véhicules filter works on (activity span,
  // years, counts, regions visited, holes in the region history)
  busesOverview: () => req(`/api/buses/overview`),
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

  pricePeriods: () => req(`/api/price-periods`),
  setPricePeriod: (p) => req(`/api/price-periods`, { method: "PUT", body: JSON.stringify(p) }),
  deletePricePeriod: (id) => req(`/api/price-periods/${id}`, { method: "DELETE" }),

  regionPeriods: () => req(`/api/region-periods`),
  // record a move ({bus_id, region, moved_on}) — closes the previous period the day
  // before, so nothing already worked changes region
  moveRegion: (p) => req(`/api/region-periods/move`, { method: "POST", body: JSON.stringify(p) }),
  setRegionPeriod: (p) => req(`/api/region-periods`, { method: "PUT", body: JSON.stringify(p) }),
  deleteRegionPeriod: (id) => req(`/api/region-periods/${id}`, { method: "DELETE" }),

  rentedVehicles: () => req(`/api/rented-vehicles`),
  createRentedVehicle: (p) => req(`/api/rented-vehicles`, { method: "POST", body: JSON.stringify(p) }),
  updateRentedVehicle: (id, p) => req(`/api/rented-vehicles/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  deleteRentedVehicle: (id) => req(`/api/rented-vehicles/${id}`, { method: "DELETE" }),

  exportCalendar: (y, m) => reqBlob(`/api/export/calendar/${y}/${m}`),
  exportRentedVehicles: () => reqBlob(`/api/export/rented-vehicles`),
  exportPricePeriods: () => reqBlob(`/api/export/price-periods`),
  exportRegionPeriods: () => reqBlob(`/api/export/region-periods`),
  exportBuses: () => reqBlob(`/api/export/buses`),
  exportDestinations: () => reqBlob(`/api/export/destinations`),
  exportContracts: () => reqBlob(`/api/export/contracts`),
  exportAnalytics: (y, m) => reqBlob(`/api/export/analytics/${y}/${m}`),
  exportJournal: () => reqBlob(`/api/export/journal`),
  exportJournalFull: () => reqBlob(`/api/export/journal/full`),

  checkAlternatives: ({ type, region, start_date, end_date }) => {
    const q = new URLSearchParams({ type, region: region || "", start_date, end_date });
    return req(`/api/rented-vehicles/alternatives?${q}`);
  },

  analytics: (y, m) => req(`/api/analytics/${y}/${m}`),

  audit: () => req(`/api/audit`),
  auditChanges: () => req(`/api/audit/changes`),

  pushKey: () => req(`/api/push/key`),
  pushSubscribe: (sub) => req(`/api/push/subscribe`, { method: "POST", body: JSON.stringify(sub) }),
  pushUnsubscribe: (sub) => req(`/api/push/unsubscribe`, { method: "POST", body: JSON.stringify(sub) }),
  notifyTest: () => req(`/api/notify/test`, { method: "POST" }),
};
