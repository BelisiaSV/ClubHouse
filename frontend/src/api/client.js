import axios from "axios";

const client = axios.create();

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 from a protected endpoint means the token is missing/expired: clear it
// and send the coach back to the login screen instead of failing silently in
// the console. Auth endpoints themselves (wrong password, etc.) are excluded
// so their 401s stay inline form errors instead of triggering a redirect.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || "";
    const isAuthEndpoint = url.includes("/api/auth/login") || url.includes("/api/auth/register");
    if (status === 401 && !isAuthEndpoint) {
      localStorage.removeItem("access_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---- Auth ----
export const register = (payload) => client.post("/api/auth/register", payload).then((res) => res.data);

export const login = (email, password) => {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  return client
    .post("/api/auth/login", form, { headers: { "Content-Type": "application/x-www-form-urlencoded" } })
    .then((res) => res.data);
};

export const getMe = () => client.get("/api/auth/me").then((res) => res.data);

export const forgotPassword = (email) =>
  client.post("/api/auth/forgot-password", { email }).then((res) => res.data);

export const resetPassword = (token, newPassword) =>
  client.post("/api/auth/reset-password", { token, new_password: newPassword }).then((res) => res.data);

// ---- Club (whitelabel branding) ----
export const getMyClub = () => client.get("/api/clubs/me").then((res) => res.data);
export const updateMyClub = (payload) => client.patch("/api/clubs/me", payload).then((res) => res.data);

// ---- Players ----
export const listPlayers = () => client.get("/api/players").then((res) => res.data);
export const createPlayer = (payload) => client.post("/api/players", payload).then((res) => res.data);
export const updatePlayer = (id, payload) => client.patch(`/api/players/${id}`, payload).then((res) => res.data);
export const deletePlayer = (id) => client.delete(`/api/players/${id}`);

export const downloadImportTemplate = () =>
  client.get("/api/players/import-template", { responseType: "blob" }).then((res) => res.data);

export const importPlayers = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return client
    .post("/api/players/import", formData, { headers: { "Content-Type": "multipart/form-data" } })
    .then((res) => res.data);
};

// ---- MAS compensation (single player, manual) ----
export const calculateCompensation = (playerId, minutesPlayed, intensityPct = 1.1) =>
  client
    .post("/mas/compensation", {
      player_id: playerId,
      minutes_played: minutesPlayed,
      intensity_pct: intensityPct,
    })
    .then((res) => res.data);

// ---- Matches / MAS compensation panel ----
export const listMatches = () => client.get("/api/matches").then((res) => res.data);

export const createMatch = (payload) => client.post("/api/matches", payload).then((res) => res.data);

export const getMatchPlayers = (matchId) =>
  client.get(`/api/matches/${matchId}/players`).then((res) => res.data);

export const updateMatchPlayer = (matchId, playerId, payload) =>
  client.patch(`/api/matches/${matchId}/players/${playerId}`, payload).then((res) => res.data);

export const generateForMatch = (matchId) =>
  client
    .post("/api/makeup-programs/generate-for-match", { match_id: matchId })
    .then((res) => res.data);

export default client;
