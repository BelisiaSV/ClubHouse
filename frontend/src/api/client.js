import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export const getPlayers = () => client.get("/players").then((res) => res.data);

export const getWellnessStatus = (playerId) =>
  client.get("/wellness-status", { params: { playerId } }).then((res) => res.data);

export const calculateCompensation = (playerId, matchMinutes) =>
  client
    .post("/calculate-compensation", { playerId, matchMinutes })
    .then((res) => res.data);

export default client;
