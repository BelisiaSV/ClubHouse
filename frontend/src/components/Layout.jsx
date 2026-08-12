import Navbar from "./Navbar.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import useClubTheme from "../hooks/useClubTheme.js";

/**
 * Shared shell for every authenticated page: the navbar plus a centered,
 * low-opacity club-logo watermark behind the content, so branding shows up
 * consistently everywhere without each page having to render it itself.
 * Also applies the club's own colors as CSS variables (useClubTheme) for
 * the whole subtree.
 */
export default function Layout({ children }) {
  const { club } = useAuth();
  useClubTheme(club);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {club?.logo_url && (
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
      )}
      <div className="relative z-10">
        <Navbar />
        <main>{children}</main>
      </div>
    </div>
  );
}
