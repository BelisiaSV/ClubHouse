import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { createClient } from "@/lib/supabase/server";
import AppShell from "@/components/app-shell/AppShell";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("full_name, role")
    .eq("id", user.id)
    .single();

  // handle_new_user's trigger always creates this row alongside the auth
  // user, so a missing profile means the trigger hasn't run yet (or
  // failed) — safer to bounce to login than render a broken shell.
  if (!profile) {
    redirect("/login");
  }

  return (
    <AppShell fullName={profile.full_name} role={profile.role}>
      {children}
    </AppShell>
  );
}
