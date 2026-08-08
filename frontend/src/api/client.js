import axios from "axios";

const client = axios.create({
  headers: { "Content-Type": "application/json" },
});

export const calculateCompensation = (playerId, minutesPlayed, intensityPct = 1.1) =>
  client
    .post("/mas/compensation", {
      player_id: playerId,
      minutes_played: minutesPlayed,
      intensity_pct: intensityPct,
    })
    .then((res) => res.data);

export default client;
