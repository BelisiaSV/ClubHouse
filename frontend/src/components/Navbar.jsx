import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const linkClass = ({ isActive }) =>
  `px-3.5 py-2 rounded-lg text-sm font-medium transition-colors duration-150 ${
    isActive ? "bg-white/20 text-white shadow-sm" : "text-white/75 hover:bg-white/10 hover:text-white"
  }`;

export default function Navbar() {
  const { user, club, logout } = useAuth();
  const bg = club?.primary_color || "#111827";

  return (
    <nav
      className="px-6 py-3.5 flex items-center justify-between shadow-lg shadow-black/20 backdrop-blur-sm"
      style={{ backgroundColor: bg }}
    >
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-2.5">
          {club?.logo_url && (
            <img
              src={club.logo_url}
              alt={`${club.name} logo`}
              className="h-9 w-9 rounded-lg bg-white/95 object-contain p-1 shadow-sm"
            />
          )}
          <span className="text-white font-bold text-lg tracking-tight">{club?.name ?? "ClubHouse"}</span>
        </div>
        {user && (
          <div className="flex items-center gap-1">
            <NavLink to="/" end className={linkClass}>
              MAS-paneel
            </NavLink>
            <NavLink to="/matches" className={linkClass}>
              Wedstrijden
            </NavLink>
            <NavLink to="/players" className={linkClass}>
              Spelers
            </NavLink>
            <NavLink to="/settings" className={linkClass}>
              Instellingen
            </NavLink>
          </div>
        )}
      </div>
      {user && (
        <div className="flex items-center gap-3 text-sm text-white/90">
          <span className="font-medium">{user.full_name}</span>
          <button
            onClick={logout}
            className="bg-black/20 hover:bg-black/30 transition-colors px-3.5 py-1.5 rounded-lg font-medium"
          >
            Uitloggen
          </button>
        </div>
      )}
    </nav>
  );
}
