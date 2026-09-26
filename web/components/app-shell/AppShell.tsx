"use client";

import { type ReactNode, useState } from "react";
import type { UserRole } from "@/types/database";
import AppSidebar from "./AppSidebar";
import { CloseIcon, MenuIcon } from "./icons";

interface AppShellProps {
  fullName: string;
  role: UserRole;
  children: ReactNode;
}

/**
 * Shared shell for every authenticated page: a static sidebar on desktop, a
 * collapsible drawer on mobile — same structure as the rest of the
 * TopsportSpace pages (see components/dugout-chat for the page content
 * this wraps around).
 */
export default function AppShell({ fullName, role, children }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-gray-950 text-gray-100">
      <div className="hidden shrink-0 md:block">
        <div className="fixed inset-y-0 left-0">
          <AppSidebar fullName={fullName} role={role} />
        </div>
        <div className="w-64" aria-hidden="true" />
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-20 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileNavOpen(false)} />
          <div className="absolute inset-y-0 left-0">
            <AppSidebar fullName={fullName} role={role} onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 md:hidden">
          <span className="truncate text-base font-bold tracking-tight text-white">The TopsportSpace</span>
          <button
            type="button"
            onClick={() => setMobileNavOpen((v) => !v)}
            className="rounded-lg p-1.5 text-gray-300 hover:bg-white/10"
            aria-label={mobileNavOpen ? "Sluit menu" : "Open menu"}
          >
            {mobileNavOpen ? <CloseIcon className="h-6 w-6" /> : <MenuIcon className="h-6 w-6" />}
          </button>
        </div>
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
