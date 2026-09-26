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
   `profiles`, `invitations`, `documents`, `comments`, `athletes`, `external_athletes`,
   `other_students`, `athlete_meetings`, `athlete_custom_fields`, `schedules`,
   `permissions`, `meal_plans`, `meal_exceptions`, `meal_free_days`, `messages`, their
   RLS policies, the `documents` Storage bucket + policies, the `handle_new_user`
   trigger that syncs `auth.users` → `profiles`, and a one-time seed import of the
   28-student roster + initial weekly plan from the standalone "Maaltijdplanning" HTML
   tool staff were using before this module existed (see "Warme maaltijden" below).

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
  Mailing (weekly counts + copyable e-mail text), Maandoverzicht, Uitzonderingen
  (exceptions + free-school-days management) + Wijzigingen (full audit log), and
  Leerlingen (CRUD on `external_athletes`/`other_students` + their weekly plan, since
  those two populations have no profile page of their own the way topsport athletes do).
  Combines THREE populations into one roster/overview: topsport athletes, external
  athletes (`external_athletes`), and other students (`other_students`) — a
  `meal_plans`/`meal_exceptions` row always belongs to exactly one of them (see the
  polymorphic FK + `*_exactly_one_subject` check constraints in the migration, and
  `subjectId()` in `lib/meals.ts`). Boarding students from any of the three (internaat)
  are excluded from the kitchen roster/counts, but get an `'eigen_lunchpakket'`
  exception type for the days the internaat itself is closed and they eat here with
  their own lunch package instead — tracked in Dagexport as a separate, uncounted
  section for staff visibility, not folded into s/v/gv.
- `app/(dashboard)/permissions`, `.../documents` — read-only overview tables (see
  "Not built yet" below — create/edit UI is the next step for these).
- `components/dugout-chat/DugoutChat.tsx` — the chat UI + Supabase Realtime
  (`postgres_changes` on `public.messages`) subscription.
- `components/athletes/AthleteForm.tsx` — the create/edit profile form (shared by both
  routes); `AthleteMeetings.tsx`, `AthleteCustomFields.tsx`, and `AthleteMealPlan.tsx` —
  the three sub-sections on the profile page, each with their own inline add form.
- `components/meals/` — the Meals module's tabs (`MealsPlanner.tsx` is the tab shell) and
  the shared `ExceptionDialog`/`MealPill`. `SubjectsTab.tsx` is the Leerlingen tab (CRUD
  on external athletes/other students) and `SubjectMealPlanEditor.tsx` is their weekly
  plan editor — the `external_athletes`/`other_students` equivalent of
  `components/athletes/AthleteMealPlan.tsx`.
- `lib/meals.ts` — pure functions computing "does subject X eat on date Y, and what"
  from plans + exceptions + free days (nothing is a materialized per-day row — see its
  docstring). `subjectId()` reads whichever of a row's three subject FK columns is set,
  so every other function here works on any of the three populations without knowing
  which one it's looking at. Shared by the dashboard KPI, the profile page, and every
  Meals tab.
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
