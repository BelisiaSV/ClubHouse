import { createContext, useContext, useEffect, useState } from "react";
import { getPlayers } from "../api/client";

const PlayerContext = createContext(null);

export function PlayerProvider({ children }) {
  const [players, setPlayers] = useState([]);
  const [selectedPlayerId, setSelectedPlayerId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPlayers()
      .then((data) => {
        setPlayers(data);
        if (data.length > 0) setSelectedPlayerId(data[0].id);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PlayerContext.Provider
      value={{ players, selectedPlayerId, setSelectedPlayerId, loading, error }}
    >
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayerContext() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayerContext must be used within a PlayerProvider");
  return ctx;
}
