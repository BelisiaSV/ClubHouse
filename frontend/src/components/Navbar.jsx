import { NavLink } from "react-router-dom";
import { usePlayerContext } from "../context/PlayerContext.jsx";

const linkClass = ({ isActive }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? "bg-emerald-600 text-white" : "text-gray-300 hover:bg-gray-800 hover:text-white"
  }`;

export default function Navbar() {
  const { players, selectedPlayerId, setSelectedPlayerId } = usePlayerContext();

  return (
    <nav className="bg-gray-900 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <span className="text-white font-bold text-lg">ClubHouse</span>
        <NavLink to="/" end className={linkClass}>
          Dashboard
        </NavLink>
        <NavLink to="/compensation" className={linkClass}>
          Compensation
        </NavLink>
        <NavLink to="/wellness" className={linkClass}>
          Wellness
        </NavLink>
      </div>
      <select
        className="bg-gray-800 text-white text-sm rounded-md px-2 py-1"
        value={selectedPlayerId ?? ""}
        onChange={(e) => setSelectedPlayerId(Number(e.target.value))}
      >
        {players.length === 0 && <option value="">No players</option>}
        {players.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </nav>
  );
}
