import { useState } from "react";
import Sidebar from "./Sidebar.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import useClubTheme from "../hooks/useClubTheme.js";
import { CloseIcon, MenuIcon } from "./icons.jsx";

/**
 * Shared shell for every page: applies the club's own colors as CSS
 * variables (useClubTheme) for the whole subtree, plus a centered,
 * low-opacity club-logo watermark behind the content.
 *
 * Logged-in users get the left Sidebar (collapsible drawer on mobile,
 * static on desktop); logged-out routes (login/register/...) render their
 * own centered content directly, same as before this had a sidebar at all.
 */
export default function Layout({ children }) {
  const { user, club } = useAuth();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  useClubTheme(club);

  const watermark = club?.logo_url && (
    <div
      className="pointer-events-none fixed inset-0 z-0 flex items-center justify-center overflow-hidden"
      aria-hidden="true"
    >
      <img
        src={club.logo_url}
        alt=""
        className="w-[60vmin] max-w-none select-none object-contain opacity-[0.05] grayscale"
      />
    </div>
  );

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-100">
        {watermark}
        <div className="relative z-10">{children}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {watermark}
      <div className="relative z-10 flex">
        {/* Desktop sidebar */}
        <div className="hidden md:block shrink-0">
          <div className="fixed inset-y-0 left-0">
            <Sidebar />
          </div>
          <div className="w-60" aria-hidden="true" />
        </div>

        {/* Mobile drawer */}
        {mobileNavOpen && (
          <div className="fixed inset-0 z-20 md:hidden">
            <div className="absolute inset-0 bg-black/60" onClick={() => setMobileNavOpen(false)} />
            <div className="absolute inset-y-0 left-0">
              <Sidebar onNavigate={() => setMobileNavOpen(false)} />
            </div>
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-white/10">
            <span className="text-white font-bold text-base tracking-tight truncate">{club?.name ?? "ClubHouse"}</span>
            <button
              onClick={() => setMobileNavOpen((v) => !v)}
              className="p-1.5 rounded-lg text-gray-300 hover:bg-white/10"
              aria-label={mobileNavOpen ? "Sluit menu" : "Open menu"}
            >
              {mobileNavOpen ? <CloseIcon className="h-6 w-6" /> : <MenuIcon className="h-6 w-6" />}
            </button>
          </div>
          <main>{children}</main>
        </div>
      </div>
    </div>
  );
}
