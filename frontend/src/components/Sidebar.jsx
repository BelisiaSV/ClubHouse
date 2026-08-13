import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { CalendarIcon, CompensationIcon, LogoutIcon, SettingsIcon, SquadIcon } from "./icons.jsx";

const NAV_ITEMS = [
  { to: "/", end: true, label: "MAS & Compensatie", Icon: CompensationIcon },
  { to: "/players", label: "Squad", Icon: SquadIcon },
  { to: "/matches", label: "Kalender", Icon: CalendarIcon },
];

const linkClass = ({ isActive }) =>
  `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
    isActive ? "nav-active-brand" : "text-gray-400 hover:bg-white/5 hover:text-gray-100"
  }`;

/**
 * Left navigation sidebar (replaces the old top Navbar). `onNavigate` closes
 * the mobile drawer after a link is clicked — a no-op on desktop.
 */
export default function Sidebar({ onNavigate }) {
  const { user, club, logout } = useAuth();

  return (
    <div className="flex h-full w-60 flex-col border-r border-white/10 bg-gray-950">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/10">
        {club?.logo_url ? (
          <img
            src={club.logo_url}
            alt={`${club.name} logo`}
            className="h-9 w-9 rounded-lg bg-white/95 object-contain p-1 shrink-0"
          />
        ) : (
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white font-bold text-sm btn-brand">
            {(club?.name ?? "CH").slice(0, 2).toUpperCase()}
          </div>
        )}
        <span className="text-white font-bold text-base tracking-tight truncate">{club?.name ?? "ClubHouse"}</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, end, label, Icon }) => (
          <NavLink key={to} to={to} end={end} className={linkClass} onClick={onNavigate}>
            <Icon className="h-5 w-5 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {user && (
        <div className="border-t border-white/10 px-3 py-4 space-y-1">
          <p className="px-3.5 pb-2 text-sm font-medium text-gray-300 truncate">{user.full_name}</p>
          <NavLink to="/settings" className={linkClass} onClick={onNavigate}>
            <SettingsIcon className="h-5 w-5 shrink-0" />
            Instellingen
          </NavLink>
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-white/5 hover:text-gray-100 transition-colors duration-150"
          >
            <LogoutIcon className="h-5 w-5 shrink-0" />
            Uitloggen
          </button>
        </div>
      )}
    </div>
  );
}
