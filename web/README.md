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
   `profiles`, `invitations`, `documents`, `comments`, `athletes`, `athlete_meetings`,
   `athlete_custom_fields`, `schedules`, `permissions`, `meal_plans`, `meal_exceptions`,
   `meal_free_days`, `messages`, their RLS policies, the `documents` Storage bucket +
   policies, and the `handle_new_user` trigger that syncs `auth.users` → `profiles`.

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
  meals today — derived, see below, permissions pending) + a queue of open permission
  requests.
- `app/(dashboard)/chat` — the Dug-out Chat (server component fetches the session +
  initial messages/profiles, then hands off to the realtime client component).
- `app/(dashboard)/athletes` — full athlete profile: overview table, `/new` create form,
  `/[id]` profile page (all fixed fields + weekly meal plan + klassenraad/deliberatie log
  + free-form extra fields), `/[id]/edit`.
- `app/(dashboard)/meals` — the warme-maaltijden operations hub, ported from a standalone
  HTML tool staff were already using (see `lib/meals.ts`'s docstring): Weekplanning grid
  (click a cell to log an absence/one-off meal), Dagexport (kitchen list for one day),
  Mailing (weekly counts + copyable e-mail text), Maandoverzicht, and Uitzonderingen
  (exceptions + free-school-days management) + Wijzigingen (full audit log).
- `app/(dashboard)/permissions`, `.../documents` — read-only overview tables (see
  "Not built yet" below — create/edit UI is the next step for these).
- `components/dugout-chat/DugoutChat.tsx` — the chat UI + Supabase Realtime
  (`postgres_changes` on `public.messages`) subscription.
- `components/athletes/AthleteForm.tsx` — the create/edit profile form (shared by both
  routes); `AthleteMeetings.tsx`, `AthleteCustomFields.tsx`, and `AthleteMealPlan.tsx` —
  the three sub-sections on the profile page, each with their own inline add form.
- `components/meals/` — the Meals module's tabs (`MealsPlanner.tsx` is the tab shell) and
  the shared `ExceptionDialog`/`MealPill`.
- `lib/meals.ts` — pure functions computing "does athlete X eat on date Y, and what"
  from plans + exceptions + free days (nothing is a materialized per-day row — see its
  docstring). Shared by the dashboard KPI, the profile page, and every Meals tab.
- `components/app-shell/` — the sidebar navigation + shell wrapping every dashboard page.
- `lib/supabase/` — browser client, server (RSC) client, and the proxy (middleware)
  session refresher.
- `types/database.ts` — hand-written types mirroring the SQL schema (swap for
  `supabase gen types typescript` output once the schema stabilizes).

## Not built yet

- Invitation UI (admin panel) — schema/RLS ready, `invitations` table only.
- Create/edit forms for schedules and permissions (approve/refuse) — currently read-only
  overview tables (athletes and meals now have full create/edit, see above).
- Document upload + full-text search UI, and document comment threads — schema/RLS/
  Storage bucket ready (`documents.search_vector`, `documents.content_text`,
  `comments`), only the frontend is pending. Linking a klassenraad/deliberatie report to
  an uploaded document (`athlete_meetings.report_document_id`) also waits on this.
- Operations Analytics charts (absentees today, curriculum coverage).
- External HTML/iFrame embeds for third-party rosters (e.g. Smartschool).
