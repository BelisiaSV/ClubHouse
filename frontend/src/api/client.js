import axios from "axios";

const client = axios.create();

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

// ---- MAS compensation ----
export const calculateCompensation = (playerId, minutesPlayed, intensityPct = 1.1) =>
  client
    .post("/mas/compensation", {
      player_id: playerId,
      minutes_played: minutesPlayed,
      intensity_pct: intensityPct,
    })
    .then((res) => res.data);

export default client;
