# The TopsportSpace — web

Next.js (App Router) + TypeScript + Tailwind CSS, backed by Supabase (Auth, Postgres, Realtime).
Closed environment for the coaching staff only — no player/student accounts.

## Setup

1. Create a Supabase project, then run the migration against it:
   ```bash
   supabase link --project-ref <your-project-ref>
   supabase db push
   ```
   (or paste `supabase/migrations/0001_init.sql` into the SQL editor). This creates
   `profiles`, `invitations`, `documents`, `comments`, `messages`, their RLS policies,
   and the `handle_new_user` trigger that syncs `auth.users` → `profiles`.

2. The **first** person to sign up is automatically made `hoofdcoach` (see the trigger's
   bootstrap case) — sign up once via Supabase Auth (e.g. the dashboard's "Add user", or
   `supabase.auth.signUp`) before inviting anyone else.

3. Copy the env file and fill in your project's values:
   ```bash
   cp .env.example .env.local
   ```

4. Install and run:
   ```bash
   npm install
   npm run dev
   ```

## Structure

- `app/login` — email/password sign-in.
- `app/chat` — the Dug-out Chat (server component fetches the session + initial
  messages/profiles, then hands off to the realtime client component).
- `components/dugout-chat/DugoutChat.tsx` — the chat UI + Supabase Realtime
  (`postgres_changes` on `public.messages`) subscription.
- `lib/supabase/` — browser client, server (RSC) client, and the middleware session
  refresher.
- `types/database.ts` — hand-written types mirroring the SQL schema (swap for
  `supabase gen types typescript` output once the schema stabilizes).

## Not built yet

Invitation UI (admin panel), document upload/list, document comment threads, and match
analytics charts — the schema and RLS for all of these already exist in the migration,
only the frontend is pending.
