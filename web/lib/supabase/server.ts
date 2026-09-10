import { cookies } from "next/headers";
import { createServerClient, type CookieOptions } from "@supabase/ssr";
import type { Database } from "@/types/database";

type CookieToSet = { name: string; value: string; options: CookieOptions };

/**
 * Server-side Supabase client for Server Components / Server Actions.
 * Cookie writes are wrapped in try/catch because a Server Component can't
 * set cookies itself — middleware.ts (lib/supabase/middleware.ts) is what
 * actually refreshes the session cookie on every request.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: CookieToSet[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
          } catch {
            // Called from a Server Component — safe to ignore, the
            // middleware handles session refresh instead.
          }
        },
      },
    }
  );
}
