import axios from "axios";

// Empty (the default) in local dev, where Vite's own dev-server proxy
// (vite.config.js) forwards relative /api, /mas, /admin, /static paths to
// the backend on :8000 — so requests stay relative and nothing changes.
// Set to the deployed backend's own origin (e.g. a Vercel project URL) in
// production, where frontend and backend are separate deployments with no
// shared proxy, so every request needs to be absolute instead.
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
});

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

export const uploadClubLogo = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return client
    .post("/api/clubs/me/logo", formData, { headers: { "Content-Type": "multipart/form-data" } })
    .then((res) => res.data);
};

// ---- Players ----
export const listPlayers = () => client.get("/api/players").then((res) => res.data);
export const getSquadOverview = () => client.get("/api/players/squad-overview").then((res) => res.data);
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

export const getMinutesAdvice = () => client.get("/api/matches/minutes-advice").then((res) => res.data);

// ---- Periodization: weekselector ----
export const queueNextCycle = (payload) =>
  client.post("/api/periodization/cycles/queue-next", payload).then((res) => res.data);

export const getCurrentCycles = () =>
  client.get("/api/periodization/cycles/current").then((res) => res.data);

export const patchActiveCycle = (payload) =>
  client.patch("/api/periodization/cycles/active", payload).then((res) => res.data);

export const getKmOverview = (cycleId) =>
  client.get(`/api/periodization/training-cycles/${cycleId}/km-overview`).then((res) => res.data);

// ---- Periodization: season start ----
export const startSeason = (payload) =>
  client.post("/api/periodization/seasons", payload).then((res) => res.data);

// ---- MAS testing: protocols, recording, calendar ----
export const getMasTestProtocols = () =>
  client.get("/api/mas-testing/protocols").then((res) => res.data);

export const recordMasTest = (payload) =>
  client.post("/api/mas-testing/record", payload).then((res) => res.data);

export const syncMasTestCalendar = () =>
  client.post("/api/mas-testing/sync-calendar").then((res) => res.data);

export const recordMasTestBatch = (payload) =>
  client.post("/api/mas-testing/record-batch", payload).then((res) => res.data);

export const getCalendarEvents = (eventType) =>
  client
    .get("/api/calendar/events", { params: eventType ? { event_type: eventType } : {} })
    .then((res) => res.data);

// ---- MAS testing: looptypegroepen (running groups) ----
export const suggestRunningGroups = (numGroups) =>
  client
    .post("/api/mas-testing/running-groups/suggest", { num_groups: numGroups })
    .then((res) => res.data);

export const confirmRunningGroups = (groups) =>
  client.post("/api/mas-testing/running-groups/confirm", { groups }).then((res) => res.data);

export const getRunningGroups = () =>
  client.get("/api/mas-testing/running-groups").then((res) => res.data);

// ---- RPE / wellness ----
export const getRpeWellnessShouldPrompt = (date) =>
  client.get("/api/rpe-wellness/should-prompt", { params: date ? { date } : {} }).then((res) => res.data);

export const recordRpeWellness = (payload) =>
  client.post("/api/rpe-wellness", payload).then((res) => res.data);

// ---- Next Training: status tiles ----
export const getNextTrainingOverview = () =>
  client.get("/api/team-readiness/overview").then((res) => res.data);

export const flagPlayers = (players) =>
  client.post("/api/team-readiness/flags", { players }).then((res) => res.data);

export const proposeTraining = (payload) =>
  client.post("/api/team-readiness/propose-training", payload).then((res) => res.data);

export const proposeTrainingAuto = (kmPerTraining) =>
  client
    .post("/api/team-readiness/propose-training/auto", { km_per_training: kmPerTraining })
    .then((res) => res.data);

export const proposeWeek = () =>
  client.post("/api/team-readiness/propose-week").then((res) => res.data);

// ---- Next Training: session composition (oefenvormen) ----
export const getVormenLibrary = () => client.get("/api/training-sessions/vormen").then((res) => res.data);

export const getCompositionProposal = (sessionId, payload) =>
  client.post(`/api/training-sessions/${sessionId}/composition-proposal`, payload).then((res) => res.data);

export const getVormTarget = (sessionId, payload) =>
  client.post(`/api/training-sessions/${sessionId}/vorm-target`, payload).then((res) => res.data);

export const recalculateComposition = (sessionId, payload) =>
  client.post(`/api/training-sessions/${sessionId}/recalculate`, payload).then((res) => res.data);

export const dryRunTopup = (payload) =>
  client.post("/api/training-sessions/dry-run-topup", payload).then((res) => res.data);

export const finalizeSession = (sessionId, payload) =>
  client.post(`/api/training-sessions/${sessionId}/finalize`, payload).then((res) => res.data);

export const getRecentSessions = (limit) =>
  client.get("/api/training-sessions/recent", { params: limit ? { limit } : {} }).then((res) => res.data);

export const getSessionDetail = (sessionId) =>
  client.get(`/api/training-sessions/${sessionId}`).then((res) => res.data);

export const deleteSession = (sessionId) => client.delete(`/api/training-sessions/${sessionId}`);

export default client;
