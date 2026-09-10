# The TopsportSpace — Performance Desk — web

Next.js (App Router) + TypeScript + Tailwind CSS, backed by Supabase (Auth, Postgres, Realtime).
Closed environment for the two Performance Directors and their staff only — student-athletes
never log in, their data is managed by staff (see `athletes` in the schema).

## Setup

1. Create a Supabase project, then run the migration against it:
   ```bash
   supabase link --project-ref <your-project-ref>
   supabase db push
   ```
   (or paste `supabase/migrations/0001_init.sql` into the SQL editor). This creates
   `profiles`, `invitations`, `documents`, `comments`, `athletes`, `schedules`,
   `permissions`, `meals`, `messages`, their RLS policies, the `documents` Storage
   bucket + policies, and the `handle_new_user` trigger that syncs `auth.users` →
   `profiles`.

2. The **first** person to sign up is automatically made `hoofdcoach` (UI label:
   Topsportdirecteur — see the trigger's bootstrap case) — sign up once via Supabase Auth
   (e.g. the dashboard's "Add user", or `supabase.auth.signUp`) before inviting anyone else.

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
- `app/(dashboard)/layout.tsx` — fetches the signed-in profile and renders `AppShell`
  (sidebar nav + mobile drawer) around every page below.
- `app/(dashboard)/page.tsx` — the Operations Dashboard: KPI tiles (active athletes,
  meals registered today, permissions pending) + a queue of open permission requests.
- `app/(dashboard)/chat` — the Dug-out Chat (server component fetches the session +
  initial messages/profiles, then hands off to the realtime client component).
- `app/(dashboard)/athletes`, `.../permissions`, `.../meals`, `.../documents` — read-only
  overview tables (see "Not built yet" below — create/edit UI is the next step).
- `components/dugout-chat/DugoutChat.tsx` — the chat UI + Supabase Realtime
  (`postgres_changes` on `public.messages`) subscription.
- `components/app-shell/` — the sidebar navigation + shell wrapping every dashboard page.
- `lib/supabase/` — browser client, server (RSC) client, and the proxy (middleware)
  session refresher.
- `types/database.ts` — hand-written types mirroring the SQL schema (swap for
  `supabase gen types typescript` output once the schema stabilizes).

## Not built yet

- Invitation UI (admin panel) — schema/RLS ready, `invitations` table only.
- Create/edit forms for athletes, schedules, permissions (approve/refuse), and meal
  registrations — currently read-only overview tables.
- Document upload + full-text search UI, and document comment threads — schema/RLS/
  Storage bucket ready (`documents.search_vector`, `documents.content_text`,
  `comments`), only the frontend is pending.
- Operations Analytics charts (absentees today, meals to prepare, curriculum coverage).
- External HTML/iFrame embeds for third-party rosters (e.g. Smartschool).
