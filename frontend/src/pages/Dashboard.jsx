import { usePlayerContext } from "../context/PlayerContext.jsx";

export default function Dashboard() {
  const { players, selectedPlayerId, loading, error } = usePlayerContext();
  const player = players.find((p) => p.id === selectedPlayerId);

  if (loading) return <p className="text-gray-400">Loading players…</p>;
  if (error) return <p className="text-red-400">Failed to load players: {error}</p>;
  if (!player) return <p className="text-gray-400">No players yet. Seed the backend to get started.</p>;

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-white mb-4">{player.name}</h1>
      <dl className="grid grid-cols-2 gap-4 bg-gray-800 rounded-lg p-4 text-gray-200">
        <div>
          <dt className="text-gray-400 text-sm">Position</dt>
          <dd>{player.position ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-gray-400 text-sm">MAS Score</dt>
          <dd>{player.mas_score} m/s</dd>
        </div>
      </dl>
    </div>
  );
}
