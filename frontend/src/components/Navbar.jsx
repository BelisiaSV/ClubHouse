import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const linkClass = ({ isActive }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? "bg-white/20 text-white" : "text-gray-200 hover:bg-white/10 hover:text-white"
  }`;

export default function Navbar() {
  const { user, club, logout } = useAuth();
  const bg = club?.primary_color || "#111827";

  return (
    <nav className="px-6 py-3 flex items-center justify-between" style={{ backgroundColor: bg }}>
      <div className="flex items-center gap-4">
        {club?.logo_url && (
          <img src={club.logo_url} alt={`${club.name} logo`} className="h-8 w-8 rounded bg-white object-contain" />
        )}
        <span className="text-white font-bold text-lg">{club?.name ?? "ClubHouse"}</span>
        {user && (
          <>
            <NavLink to="/" end className={linkClass}>
              Compensation
            </NavLink>
            <NavLink to="/players" className={linkClass}>
              Spelers
            </NavLink>
            <NavLink to="/settings" className={linkClass}>
              Instellingen
            </NavLink>
          </>
        )}
      </div>
      {user && (
        <div className="flex items-center gap-3 text-sm text-gray-100">
          <span>{user.full_name}</span>
          <button onClick={logout} className="bg-black/20 hover:bg-black/30 px-3 py-1 rounded-md">
            Uitloggen
          </button>
        </div>
      )}
    </nav>
  );
}
