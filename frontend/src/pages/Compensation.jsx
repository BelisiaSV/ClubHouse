import { useState } from "react";
import { calculateCompensation } from "../api/client";
import { usePlayerContext } from "../context/PlayerContext.jsx";

export default function Compensation() {
  const { selectedPlayerId } = usePlayerContext();
  const [matchMinutes, setMatchMinutes] = useState(45);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedPlayerId) return;
    setSubmitting(true);
    setError(null);
    try {
      const data = await calculateCompensation(selectedPlayerId, Number(matchMinutes));
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-white mb-4">HIT Compensation Training</h1>
      <form onSubmit={handleSubmit} className="flex items-end gap-3 mb-6">
        <label className="flex flex-col text-sm text-gray-300">
          Match minutes played
          <input
            type="number"
            min="0"
            max="120"
            value={matchMinutes}
            onChange={(e) => setMatchMinutes(e.target.value)}
            className="mt-1 bg-gray-800 text-white rounded-md px-3 py-2 w-40"
          />
        </label>
        <button
          type="submit"
          disabled={submitting || !selectedPlayerId}
          className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-md"
        >
          {submitting ? "Calculating…" : "Calculate"}
        </button>
      </form>

      {error && <p className="text-red-400 mb-4">{error}</p>}

      {result && (
        <dl className="grid grid-cols-2 gap-4 bg-gray-800 rounded-lg p-4 text-gray-200">
          <Stat label="Minutes missed" value={result.minutesMissed} />
          <Stat label="Target speed (110% MAS)" value={`${result.targetSpeedMs} m/s`} />
          <Stat label="Intervals" value={`${result.repetitions} × ${result.intervalWorkSeconds}s/${result.intervalRestSeconds}s`} />
          <Stat label="Total distance" value={`${result.totalDistanceMeters} m`} />
          <Stat label="Running duration" value={`${result.totalRunningDurationMinutes} min`} />
          <Stat label="Total session duration" value={`${result.totalSessionDurationMinutes} min`} />
        </dl>
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
