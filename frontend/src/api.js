const BASE = "/api";

export function getToken() {
  return localStorage.getItem("mm_token") || "";
}
export function setToken(t) {
  if (t) localStorage.setItem("mm_token", t);
  else localStorage.removeItem("mm_token");
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (auth && token) headers.Authorization = `Token ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const message =
      data?.detail ||
      (data && typeof data === "object"
        ? Object.entries(data)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
            .join("  ")
        : "") ||
      `Request failed (${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function qs(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (Array.isArray(v)) v.forEach((item) => search.append(k, item));
    else search.append(k, v);
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const api = {
  // auth
  register: (b) => request("/auth/register/", { method: "POST", body: b, auth: false }),
  login: (b) => request("/auth/login/", { method: "POST", body: b, auth: false }),
  logout: () => request("/auth/logout/", { method: "POST" }),
  me: () => request("/auth/me/"),
  updateMe: (b) => request("/auth/me/", { method: "PATCH", body: b }),
  verifyRequest: (b) => request("/auth/verify/request/", { method: "POST", body: b }),
  verifyConfirm: (b) => request("/auth/verify/confirm/", { method: "POST", body: b }),

  // catalog
  config: () => request("/config/", { auth: false }),
  geoReverse: (lat, lng) =>
    request(`/geo/reverse/?lat=${lat}&lng=${lng}`, { auth: false }),
  geoSearch: (q) =>
    request(`/geo/search/?q=${encodeURIComponent(q)}`, { auth: false }),
  categories: () => request("/categories/", { auth: false }),
  stats: () => request("/stats/", { auth: false }),
  listings: (params) => request(`/listings/${qs(params)}`, { auth: false }),
  listing: (id) => request(`/listings/${id}/`, { auth: false }),
  related: (id) => request(`/listings/${id}/related/`, { auth: false }),
  myListings: () => request("/listings/mine/"),
  createListing: (b) => request("/listings/", { method: "POST", body: b }),
  updateListing: (id, b) => request(`/listings/${id}/`, { method: "PATCH", body: b }),
  deleteListing: (id) => request(`/listings/${id}/`, { method: "DELETE" }),

  // matching
  match: (text) => request("/match/", { method: "POST", body: { text } }),
  myNeeds: () => request("/needs/"),

  // booking
  transactions: (params) => request(`/transactions/${qs(params)}`),
  claim: (b) => request("/transactions/", { method: "POST", body: b }),
  accept: (id, b) => request(`/transactions/${id}/accept/`, { method: "POST", body: b || {} }),
  reject: (id) => request(`/transactions/${id}/reject/`, { method: "POST", body: {} }),
  cancel: (id) => request(`/transactions/${id}/cancel/`, { method: "POST", body: {} }),
  confirm: (id) => request(`/transactions/${id}/confirm/`, { method: "POST", body: {} }),
  dispute: (id) => request(`/transactions/${id}/dispute/`, { method: "POST", body: {} }),
  review: (b) => request("/reviews/", { method: "POST", body: b }),
  proposeTime: (id, pickup_at) =>
    request(`/transactions/${id}/propose-time/`, { method: "POST", body: { pickup_at } }),
  agreeTime: (id) =>
    request(`/transactions/${id}/agree-time/`, { method: "POST", body: {} }),
  messages: (id) => request(`/transactions/${id}/messages/`),
  sendMessage: (id, body) =>
    request(`/transactions/${id}/messages/`, { method: "POST", body: { body } }),
  travel: (id) => request(`/listings/${id}/travel/`, { auth: false }),

  // notifications
  notifications: () => request("/notifications/"),
  markNotificationRead: (id) => request(`/notifications/${id}/read/`, { method: "POST", body: {} }),
  markAllNotificationsRead: () => request("/notifications/read-all/", { method: "POST", body: {} }),

  // wallet
  wallet: () => request("/wallet/"),
  ledger: () => request("/wallet/ledger/"),
  impact: () => request("/wallet/impact/"),
  redeem: (points) => request("/wallet/redeem/", { method: "POST", body: { points } }),
  settle: () => request("/wallet/settle/", { method: "POST", body: {} }),
  leaderboard: () => request("/leaderboard/", { auth: false }),
};

export const money = (cents) => `$${((cents || 0) / 100).toFixed(2)}`;
export const pointsToMoney = (points, per = 20) => `$${((points || 0) / per).toFixed(2)}`;
