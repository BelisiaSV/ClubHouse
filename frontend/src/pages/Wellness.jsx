import { useEffect, useState } from "react";
import { getWellnessStatus } from "../api/client";
import { usePlayerContext } from "../context/PlayerContext.jsx";

const FLAG_STYLES = {
  green: "bg-emerald-600",
  orange: "bg-amber-500",
  red: "bg-red-600",
  insufficient_data: "bg-gray-600",
};

export default function Wellness() {
  const { selectedPlayerId } = usePlayerContext();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedPlayerId) return;
    setLoading(true);
    setError(null);
    getWellnessStatus(selectedPlayerId)
      .then(setStatus)
      .catch((err) => setError(err.response?.data?.detail ?? err.message))
      .finally(() => setLoading(false));
  }, [selectedPlayerId]);

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-white mb-4">Wellness Status (ACWR)</h1>
      {loading && <p className="text-gray-400">Loading…</p>}
      {error && <p className="text-red-400">{error}</p>}
      {status && (
        <div className="bg-gray-800 rounded-lg p-4 text-gray-200 space-y-3">
          <div className="flex items-center gap-3">
            <span
              className={`inline-block w-4 h-4 rounded-full ${FLAG_STYLES[status.flag] ?? "bg-gray-600"}`}
            />
            <span className="uppercase text-sm tracking-wide">{status.flag.replace("_", " ")}</span>
          </div>
          <p className="text-sm text-gray-400">{status.message}</p>
          <dl className="grid grid-cols-3 gap-4 pt-2">
            <div>
              <dt className="text-gray-400 text-sm">Acute (7d)</dt>
              <dd>{status.acuteLoad7d}</dd>
            </div>
            <div>
              <dt className="text-gray-400 text-sm">Chronic (28d)</dt>
              <dd>{status.chronicLoad28d}</dd>
            </div>
            <div>
              <dt className="text-gray-400 text-sm">ACWR</dt>
              <dd>{status.acwr ?? "—"}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}
