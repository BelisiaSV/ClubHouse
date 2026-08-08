import { useEffect, useState } from "react";
import { calculateCompensation, listPlayers } from "../api/client";

export default function Compensation() {
  const [players, setPlayers] = useState([]);
  const [playerId, setPlayerId] = useState("");
  const [minutesPlayed, setMinutesPlayed] = useState(32);
  const [intensityPct, setIntensityPct] = useState(1.1);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listPlayers().then((data) => {
      setPlayers(data);
      if (data.length > 0) setPlayerId(data[0].id);
    });
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const data = await calculateCompensation(playerId, Number(minutesPlayed), Number(intensityPct));
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto py-10 px-4">
      <h1 className="text-2xl font-bold text-white mb-1">MAS HIT Compensation</h1>
      <p className="text-sm text-gray-400 mb-6">
        15s/15s HIT-compensatieprotocol, gebaseerd op de meest recente MAS-test van de speler.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4 mb-8">
        <label className="flex flex-col text-sm text-gray-300">
          Speler
          <select
            required
            value={playerId}
            onChange={(e) => setPlayerId(e.target.value)}
            className="mt-1 bg-gray-800 text-white rounded-md px-3 py-2"
          >
            {players.length === 0 && <option value="">Nog geen spelers</option>}
            {players.map((p) => (
              <option key={p.id} value={p.id}>
                {p.jersey_number != null ? `#${p.jersey_number} ` : ""}
                {p.first_name} {p.last_name}
              </option>
            ))}
          </select>
        </label>
        <div className="flex gap-4">
          <label className="flex flex-col text-sm text-gray-300 flex-1">
            Match minutes played
            <input
              type="number"
              min="0"
              max="90"
              value={minutesPlayed}
              onChange={(e) => setMinutesPlayed(e.target.value)}
              className="mt-1 bg-gray-800 text-white rounded-md px-3 py-2"
            />
          </label>
          <label className="flex flex-col text-sm text-gray-300 flex-1">
            Intensity (% MAS)
            <input
              type="number"
              step="0.01"
              min="0.5"
              max="2"
              value={intensityPct}
              onChange={(e) => setIntensityPct(e.target.value)}
              className="mt-1 bg-gray-800 text-white rounded-md px-3 py-2"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={submitting || !playerId}
          className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-md"
        >
          {submitting ? "Calculating…" : "Calculate"}
        </button>
      </form>

      {error && <p className="text-red-400 mb-4">{typeof error === "string" ? error : JSON.stringify(error)}</p>}

      {result && (
        <div className="bg-gray-800 rounded-lg p-4 text-gray-200 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-white">{result.player_name}</h2>
            <p className="text-sm text-gray-400">
              MAS {result.mas_kmh} km/u ({result.mas_test_date}) — {result.minutes_played} min gespeeld
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-4">
            <Stat label="Target speed" value={`${result.target_speed_kmh} km/u (${result.target_speed_ms} m/s)`} />
            <Stat label="Total work time" value={`${result.total_work_time_min} min`} />
            <Stat label="Repetitions" value={`${result.total_reps} × ${result.reps_per_block}/blok`} />
            <Stat label="Blocks" value={result.blocks} />
            <Stat label="Distance / rep" value={`${result.distance_per_rep_m} m`} />
            <Stat label="Total distance" value={`${result.total_distance_m} m`} />
          </dl>
          <p className="text-sm text-gray-300 border-t border-gray-700 pt-3">{result.protocol_description}</p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <dt className="text-gray-400 text-sm">{label}</dt>
      <dd className="text-lg">{value}</dd>
    </div>
  );
}
