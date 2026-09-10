"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { UserRole } from "@/types/database";
import {
  AthletesIcon,
  ChatIcon,
  DashboardIcon,
  DocumentsIcon,
  LogoutIcon,
  MealsIcon,
  PermissionsIcon,
} from "./icons";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", Icon: DashboardIcon },
  { href: "/chat", label: "Dug-out Chat", Icon: ChatIcon },
  { href: "/athletes", label: "Atleten", Icon: AthletesIcon },
  { href: "/permissions", label: "Toestemmingen", Icon: PermissionsIcon },
  { href: "/meals", label: "Maaltijden", Icon: MealsIcon },
  { href: "/documents", label: "Documenten", Icon: DocumentsIcon },
];

const ROLE_LABEL: Record<UserRole, string> = {
  hoofdcoach: "Topsportdirecteur",
  assistent_coach: "Staff / Begeleider",
};

interface AppSidebarProps {
  fullName: string;
  role: UserRole;
  onNavigate?: () => void;
}

export default function AppSidebar({ fullName, role, onNavigate }: AppSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  };

  return (
    <div className="flex h-full w-64 flex-col border-r border-white/10 bg-gray-950">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/10">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
          TS
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold tracking-tight text-white">The TopsportSpace</p>
          <p className="truncate text-[11px] text-gray-500">Performance Desk</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map(({ href, label, Icon }) => {
          const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={`flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-medium transition-colors duration-150 ${
                isActive ? "bg-emerald-600 text-white" : "text-gray-400 hover:bg-white/5 hover:text-gray-100"
              }`}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-1 border-t border-white/10 px-3 py-4">
        <div className="px-3.5 pb-2">
          <p className="truncate text-sm font-medium text-gray-200">{fullName}</p>
          <p className="truncate text-xs text-emerald-400">{ROLE_LABEL[role]}</p>
        </div>
        <button
          type="button"
          onClick={handleSignOut}
          className="flex w-full items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-medium text-gray-400 transition-colors duration-150 hover:bg-white/5 hover:text-gray-100"
        >
          <LogoutIcon className="h-5 w-5 shrink-0" />
          Uitloggen
        </button>
      </div>
    </div>
  );
}
