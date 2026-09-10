-- ============================================================================
-- The TopsportSpace — "The Performance Desk" — initial schema
-- profiles · invitations · documents · comments · athletes · schedules ·
-- permissions · meals · messages (Dug-out Chat)
-- ============================================================================
-- Two roles only: 'hoofdcoach' (UI label: Topsportdirecteur — full rights
-- incl. inviting/removing staff) and 'assistent_coach' (UI label: Staff/
-- Begeleider — can edit schedules, log permission decisions and meal
-- registrations, upload documents, chat, but cannot manage users). The
-- enum's own values stay as originally named rather than being renamed
-- with every UI-label change the brief has gone through — see is_hoofdcoach()
-- further down, which every other role check is built on.
--
-- Student-athletes never log in — 'athletes' is data the staff manage, not
-- a set of accounts (see 'Leerlingen loggen hier niet in' in the brief).
-- ============================================================================

create extension if not exists "pgcrypto";

create type public.user_role as enum ('hoofdcoach', 'assistent_coach');
create type public.invitation_status as enum ('pending', 'accepted', 'revoked');

-- ----------------------------------------------------------------------------
-- profiles — one row per Supabase Auth user, kept in sync by the
-- handle_new_user trigger below (auth.users itself is never queried
-- directly from the client — RLS can't reach it — so every other table's
-- FKs and policies go through profiles instead).
-- ----------------------------------------------------------------------------
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  full_name text not null,
  avatar_url text,
  role public.user_role not null default 'assistent_coach',
  created_at timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- invitations — a hoofdcoach-issued invite. Supabase Auth's own
-- admin.inviteUserByEmail() sends the actual email + registration link;
-- this table only tracks WHICH ROLE the invitee should get once they
-- accept (handle_new_user reads it by email) plus an audit trail of who
-- invited whom and whether it's still open. The partial unique index
-- keeps at most one *pending* invite per email.
-- ----------------------------------------------------------------------------
create table public.invitations (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  role public.user_role not null default 'assistent_coach',
  status public.invitation_status not null default 'pending',
  invited_by uuid not null references public.profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  accepted_at timestamptz
);

create unique index invitations_email_pending_key
  on public.invitations (lower(email))
  where status = 'pending';

create index invitations_status_idx on public.invitations (status);

-- ----------------------------------------------------------------------------
-- documents — the Tactische Database. file_path points into the
-- 'documents' Supabase Storage bucket (created + policed further down in
-- this same file — Storage buckets/objects are regular Postgres tables
-- under the hood, so this IS manageable from a SQL migration).
--
-- content_text holds a plain-text copy of the file's content for search:
-- for text-native formats (markdown, html, plain text) the client extracts
-- this directly before upload; PDF/Word files currently go in with
-- content_text left null (searchable by title/description/tags only) until
-- a text-extraction step is added. search_vector is kept in sync by the
-- documents_set_search_vector trigger below rather than GENERATED ALWAYS AS
-- — to_tsvector(regconfig, text) is only STABLE, not IMMUTABLE (the
-- configuration lookup can change), which Postgres generated columns
-- reject; a BEFORE INSERT/UPDATE trigger is the standard workaround.
-- ----------------------------------------------------------------------------
create table public.documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  file_path text not null,
  file_type text not null,
  tags text[] not null default '{}',
  content_text text,
  uploaded_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  search_vector tsvector
);

create index documents_uploaded_by_idx on public.documents (uploaded_by);
create index documents_tags_idx on public.documents using gin (tags);
create index documents_search_vector_idx on public.documents using gin (search_vector);

create or replace function public.set_document_search_vector()
returns trigger
language plpgsql
as $$
begin
  new.search_vector :=
    setweight(to_tsvector('dutch', coalesce(new.title, '')), 'A') ||
    setweight(to_tsvector('dutch', array_to_string(new.tags, ' ')), 'B') ||
    setweight(to_tsvector('dutch', coalesce(new.description, '')), 'C') ||
    setweight(to_tsvector('dutch', coalesce(new.content_text, '')), 'D');
  return new;
end;
$$;

create trigger documents_set_search_vector
  before insert or update on public.documents
  for each row execute function public.set_document_search_vector();

-- Keeps *.updated_at honest on every edit without the app having to
-- remember to set it itself — reused below by athletes/schedules/meals.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger documents_set_updated_at
  before update on public.documents
  for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- comments — threaded notes on a document, using the same realtime
-- pattern as messages below. parent_comment_id allows one level of
-- replies without a separate reply table.
-- ----------------------------------------------------------------------------
create table public.comments (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents (id) on delete cascade,
  author_id uuid references public.profiles (id) on delete set null,
  parent_comment_id uuid references public.comments (id) on delete cascade,
  body text not null,
  created_at timestamptz not null default now()
);

create index comments_document_id_idx on public.comments (document_id);

-- ----------------------------------------------------------------------------
-- athletes — the student-athletes' profile. No login of their own; every FK
-- from schedules/permissions/meals/athlete_meetings/athlete_custom_fields
-- points here, not at profiles. contact_email/contact_phone are the
-- athlete's OWN contact details (only relevant for older students) —
-- guardian_* is the parent/guardian contact the school actually leans on
-- day to day.
-- ----------------------------------------------------------------------------
create table public.athletes (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  date_of_birth date,
  sport text,
  class_group text,
  external_club text,
  contact_email text,
  contact_phone text,
  guardian_name text,
  guardian_phone text,
  guardian_email text,
  -- Warme maaltijden: this is the standing preference/eligibility flag —
  -- distinct from `meals`, which logs the actual per-day registration
  -- (an athlete can be opted in generally but skip/be marked absent a
  -- given day, or vice versa for a one-off exception).
  meal_plan_opt_in boolean not null default false,
  is_boarding_student boolean not null default false,
  boarding_school_name text,
  departure_time time,
  departure_notes text,
  medical_screening_done boolean not null default false,
  medical_screening_date date,
  medical_screening_notes text,
  notes text,
  is_active boolean not null default true,
  created_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index athletes_full_name_idx on public.athletes (full_name);
create index athletes_class_group_idx on public.athletes (class_group);

create trigger athletes_set_updated_at
  before update on public.athletes
  for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- athlete_meetings — klassenraad ("class council") and deliberatie
-- ("deliberation") entries for an athlete: a date, prep notes, a report,
-- and optionally a link to an uploaded report file in `documents`. One
-- table for both meeting types since they share the same shape (a date +
-- preparation + a report) rather than two near-identical tables.
-- ----------------------------------------------------------------------------
create type public.athlete_meeting_type as enum ('klassenraad', 'deliberatie');

create table public.athlete_meetings (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  meeting_type public.athlete_meeting_type not null,
  meeting_date date not null,
  preparation_notes text,
  report_notes text,
  report_document_id uuid references public.documents (id) on delete set null,
  created_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index athlete_meetings_athlete_id_idx on public.athlete_meetings (athlete_id);
create index athlete_meetings_meeting_date_idx on public.athlete_meetings (meeting_date);

create trigger athlete_meetings_set_updated_at
  before update on public.athlete_meetings
  for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- athlete_custom_fields — free-form "add anything else" label/value pairs
-- per athlete, for whatever the fixed profile columns above don't cover.
-- Deliberately unstructured (plain text value) rather than typed, since
-- what staff will want to track here isn't known upfront.
-- ----------------------------------------------------------------------------
create table public.athlete_custom_fields (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  label text not null,
  value text,
  created_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index athlete_custom_fields_athlete_id_idx on public.athlete_custom_fields (athlete_id);

create trigger athlete_custom_fields_set_updated_at
  before update on public.athlete_custom_fields
  for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- schedules — one row per lesson/training/logistics block for an athlete.
-- Either a RECURRING weekly slot (day_of_week set, specific_date null — a
-- standing lesson/training time) or a ONE-OFF dated entry (specific_date
-- set, day_of_week null — a stage, a wedstrijd, a one-time deviation);
-- never both, never neither.
-- ----------------------------------------------------------------------------
create type public.schedule_entry_type as enum (
  'les', 'training', 'stage', 'wedstrijd', 'topsport_verplichting', 'overig'
);

create table public.schedules (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  entry_type public.schedule_entry_type not null default 'les',
  title text not null,
  day_of_week smallint,
  specific_date date,
  start_time time,
  end_time time,
  location text,
  notes text,
  created_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint schedules_day_xor_date check (
    (day_of_week is not null) <> (specific_date is not null)
  ),
  constraint schedules_day_of_week_range check (day_of_week between 0 and 6)
);

create index schedules_athlete_id_idx on public.schedules (athlete_id);
create index schedules_specific_date_idx on public.schedules (specific_date);

create trigger schedules_set_updated_at
  before update on public.schedules
  for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- permissions — the "Toestemmingen-Matrix": requests to deviate from the
-- normal schedule (leave early, arrive late, absence) that a director/staff
-- member logs and then approves or refuses.
-- ----------------------------------------------------------------------------
create type public.permission_request_type as enum (
  'vroeger_vertrek', 'later_toekomen', 'afwezigheid', 'overig'
);
create type public.permission_status as enum ('in_afwachting', 'goedgekeurd', 'geweigerd');

create table public.permissions (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  request_type public.permission_request_type not null default 'overig',
  requested_date date not null,
  start_time time,
  end_time time,
  reason text,
  status public.permission_status not null default 'in_afwachting',
  requested_by uuid references public.profiles (id) on delete set null,
  decided_by uuid references public.profiles (id) on delete set null,
  decided_at timestamptz,
  decision_note text,
  created_at timestamptz not null default now()
);

create index permissions_athlete_id_idx on public.permissions (athlete_id);
create index permissions_requested_date_idx on public.permissions (requested_date);
create index permissions_status_idx on public.permissions (status);

-- ----------------------------------------------------------------------------
-- meals — daily warme-maaltijden registration, one row per (athlete, date).
-- 'is_registered' rather than a delete-on-cancel keeps the day's headcount
-- ("hoeveel maaltijden moeten er klaargemaakt worden") auditable — an
-- afmelding is a state change, not a vanished row.
-- ----------------------------------------------------------------------------
create table public.meals (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athletes (id) on delete cascade,
  meal_date date not null,
  is_registered boolean not null default true,
  note text,
  registered_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, meal_date)
);

create index meals_meal_date_idx on public.meals (meal_date);

create trigger meals_set_updated_at
  before update on public.meals
  for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- messages — the Dug-out Chat. A single shared channel: this is a closed,
-- small-team environment (currently two coaches), not a multi-channel
-- product, so there's no channel/room concept yet.
-- ----------------------------------------------------------------------------
create table public.messages (
  id uuid primary key default gen_random_uuid(),
  sender_id uuid references public.profiles (id) on delete set null,
  body text not null,
  created_at timestamptz not null default now(),
  edited_at timestamptz
);

create index messages_created_at_idx on public.messages (created_at);

-- Realtime UPDATE/DELETE payloads only include changed columns by default;
-- full replica identity gives the client the complete old row so deletes/
-- edits in the chat, document overview, and document-comment threads can be
-- reconciled locally.
alter table public.messages replica identity full;
alter table public.comments replica identity full;
alter table public.documents replica identity full;
alter table public.permissions replica identity full;
alter table public.meals replica identity full;
alter table public.athletes replica identity full;
alter table public.athlete_meetings replica identity full;
alter table public.athlete_custom_fields replica identity full;

-- ============================================================================
-- Auth sync: create a profile row for every new Supabase Auth user, and
-- resolve their role from a matching pending invitation (or bootstrap the
-- very first account on a fresh instance to hoofdcoach — otherwise nobody
-- could ever invite anyone).
-- ============================================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  matched_invitation public.invitations%rowtype;
  assigned_role public.user_role;
  resolved_name text;
begin
  resolved_name := coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1));

  select * into matched_invitation
  from public.invitations
  where lower(email) = lower(new.email) and status = 'pending'
  order by created_at desc
  limit 1;

  if matched_invitation.id is not null then
    assigned_role := matched_invitation.role;
    update public.invitations
      set status = 'accepted', accepted_at = now()
      where id = matched_invitation.id;
  elsif not exists (select 1 from public.profiles) then
    assigned_role := 'hoofdcoach';
  else
    assigned_role := 'assistent_coach';
  end if;

  insert into public.profiles (id, email, full_name, role)
  values (new.id, new.email, resolved_name, assigned_role);

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================================
-- Role-escalation guard: only a hoofdcoach may change anyone's role
-- (including their own demotion/promotion of someone else). A non-
-- hoofdcoach's attempt to change the role column is silently reverted
-- rather than erroring, so an update that also touches other columns
-- (e.g. avatar_url) still succeeds for the columns they ARE allowed to
-- change.
-- ============================================================================
create or replace function public.is_hoofdcoach(uid uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profiles where id = uid and role = 'hoofdcoach'
  );
$$;

create or replace function public.prevent_role_self_escalation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.role is distinct from old.role and not public.is_hoofdcoach(auth.uid()) then
    new.role := old.role;
  end if;
  return new;
end;
$$;

create trigger profiles_guard_role_update
  before update on public.profiles
  for each row execute function public.prevent_role_self_escalation();

-- ============================================================================
-- Row Level Security
-- ============================================================================
alter table public.profiles enable row level security;
alter table public.invitations enable row level security;
alter table public.documents enable row level security;
alter table public.comments enable row level security;
alter table public.athletes enable row level security;
alter table public.schedules enable row level security;
alter table public.permissions enable row level security;
alter table public.meals enable row level security;
alter table public.athlete_meetings enable row level security;
alter table public.athlete_custom_fields enable row level security;
alter table public.messages enable row level security;

-- profiles: every authenticated coach can see the (small, closed) roster;
-- only the row owner or a hoofdcoach may update it (role escalation is
-- blocked separately by the trigger above); a hoofdcoach can remove a
-- coach's profile (offboarding). Inserts only ever happen via
-- handle_new_user's security-definer trigger, so there is deliberately no
-- INSERT policy for authenticated/anon.
create policy "profiles_select_authenticated"
  on public.profiles for select
  to authenticated
  using (true);

create policy "profiles_update_own_or_hoofdcoach"
  on public.profiles for update
  to authenticated
  using (auth.uid() = id or public.is_hoofdcoach(auth.uid()));

create policy "profiles_delete_hoofdcoach"
  on public.profiles for delete
  to authenticated
  using (public.is_hoofdcoach(auth.uid()));

-- invitations: hoofdcoach-only, end to end (the "Transfermarkt" admin panel).
create policy "invitations_all_hoofdcoach"
  on public.invitations for all
  to authenticated
  using (public.is_hoofdcoach(auth.uid()))
  with check (public.is_hoofdcoach(auth.uid()));

-- documents: any coach can read/upload; only the uploader or a hoofdcoach
-- may edit/delete.
create policy "documents_select_authenticated"
  on public.documents for select
  to authenticated
  using (true);

create policy "documents_insert_authenticated"
  on public.documents for insert
  to authenticated
  with check (uploaded_by = auth.uid());

create policy "documents_update_owner_or_hoofdcoach"
  on public.documents for update
  to authenticated
  using (uploaded_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

create policy "documents_delete_owner_or_hoofdcoach"
  on public.documents for delete
  to authenticated
  using (uploaded_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

-- comments: any coach can read/write; only the author or a hoofdcoach may
-- edit/delete.
create policy "comments_select_authenticated"
  on public.comments for select
  to authenticated
  using (true);

create policy "comments_insert_authenticated"
  on public.comments for insert
  to authenticated
  with check (author_id = auth.uid());

create policy "comments_update_owner_or_hoofdcoach"
  on public.comments for update
  to authenticated
  using (author_id = auth.uid() or public.is_hoofdcoach(auth.uid()));

create policy "comments_delete_owner_or_hoofdcoach"
  on public.comments for delete
  to authenticated
  using (author_id = auth.uid() or public.is_hoofdcoach(auth.uid()));

-- athletes/schedules/permissions/meals: any authenticated staff member can
-- read and write — both roles run day-to-day operations on this data (the
-- brief only carves out user management as admin-only, see 'invitations'
-- above); deletes are restricted to the creator or a hoofdcoach, same
-- ownership pattern as documents/comments.
create policy "athletes_select_authenticated"
  on public.athletes for select
  to authenticated
  using (true);

create policy "athletes_insert_authenticated"
  on public.athletes for insert
  to authenticated
  with check (true);

create policy "athletes_update_authenticated"
  on public.athletes for update
  to authenticated
  using (true);

create policy "athletes_delete_owner_or_hoofdcoach"
  on public.athletes for delete
  to authenticated
  using (created_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

create policy "schedules_select_authenticated"
  on public.schedules for select
  to authenticated
  using (true);

create policy "schedules_insert_authenticated"
  on public.schedules for insert
  to authenticated
  with check (true);

create policy "schedules_update_authenticated"
  on public.schedules for update
  to authenticated
  using (true);

create policy "schedules_delete_owner_or_hoofdcoach"
  on public.schedules for delete
  to authenticated
  using (created_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

create policy "permissions_select_authenticated"
  on public.permissions for select
  to authenticated
  using (true);

create policy "permissions_insert_authenticated"
  on public.permissions for insert
  to authenticated
  with check (true);

create policy "permissions_update_authenticated"
  on public.permissions for update
  to authenticated
  using (true);

create policy "permissions_delete_owner_or_hoofdcoach"
  on public.permissions for delete
  to authenticated
  using (requested_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

create policy "meals_select_authenticated"
  on public.meals for select
  to authenticated
  using (true);

create policy "meals_insert_authenticated"
  on public.meals for insert
  to authenticated
  with check (true);

create policy "meals_update_authenticated"
  on public.meals for update
  to authenticated
  using (true);

create policy "meals_delete_owner_or_hoofdcoach"
  on public.meals for delete
  to authenticated
  using (registered_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

-- athlete_meetings/athlete_custom_fields: same authenticated-read-write,
-- creator-or-hoofdcoach-delete pattern as the rest of an athlete's profile.
create policy "athlete_meetings_select_authenticated"
  on public.athlete_meetings for select
  to authenticated
  using (true);

create policy "athlete_meetings_insert_authenticated"
  on public.athlete_meetings for insert
  to authenticated
  with check (true);

create policy "athlete_meetings_update_authenticated"
  on public.athlete_meetings for update
  to authenticated
  using (true);

create policy "athlete_meetings_delete_owner_or_hoofdcoach"
  on public.athlete_meetings for delete
  to authenticated
  using (created_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

create policy "athlete_custom_fields_select_authenticated"
  on public.athlete_custom_fields for select
  to authenticated
  using (true);

create policy "athlete_custom_fields_insert_authenticated"
  on public.athlete_custom_fields for insert
  to authenticated
  with check (true);

create policy "athlete_custom_fields_update_authenticated"
  on public.athlete_custom_fields for update
  to authenticated
  using (true);

create policy "athlete_custom_fields_delete_owner_or_hoofdcoach"
  on public.athlete_custom_fields for delete
  to authenticated
  using (created_by = auth.uid() or public.is_hoofdcoach(auth.uid()));

-- messages (Dug-out Chat): any coach can read/write; only the sender or a
-- hoofdcoach may edit/delete (moderation).
create policy "messages_select_authenticated"
  on public.messages for select
  to authenticated
  using (true);

create policy "messages_insert_authenticated"
  on public.messages for insert
  to authenticated
  with check (sender_id = auth.uid());

create policy "messages_update_owner_or_hoofdcoach"
  on public.messages for update
  to authenticated
  using (sender_id = auth.uid() or public.is_hoofdcoach(auth.uid()));

create policy "messages_delete_owner_or_hoofdcoach"
  on public.messages for delete
  to authenticated
  using (sender_id = auth.uid() or public.is_hoofdcoach(auth.uid()));

-- ============================================================================
-- Realtime: publish messages + comments + documents + permissions + meals so
-- Supabase Realtime's postgres_changes can stream INSERT/UPDATE/DELETE to
-- subscribed clients — the Dug-out Chat, document-comment threads, the
-- document overview, and status changes (e.g. an approved permission or a
-- meal registration) syncing live between both directors.
-- ============================================================================
alter publication supabase_realtime add table public.messages;
alter publication supabase_realtime add table public.comments;
alter publication supabase_realtime add table public.documents;
alter publication supabase_realtime add table public.permissions;
alter publication supabase_realtime add table public.meals;
alter publication supabase_realtime add table public.athletes;
alter publication supabase_realtime add table public.athlete_meetings;
alter publication supabase_realtime add table public.athlete_custom_fields;

-- ============================================================================
-- Storage: the 'documents' bucket backing public.documents.file_path.
-- Private bucket — every read goes through the authenticated client SDK (or
-- a signed URL), never a public URL, since these are internal school
-- documents. `owner` is set automatically by Supabase Storage to the
-- uploader's auth.uid() on upload.
-- ============================================================================
insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;

create policy "documents_bucket_select_authenticated"
  on storage.objects for select
  to authenticated
  using (bucket_id = 'documents');

create policy "documents_bucket_insert_authenticated"
  on storage.objects for insert
  to authenticated
  with check (bucket_id = 'documents');

create policy "documents_bucket_update_owner_or_hoofdcoach"
  on storage.objects for update
  to authenticated
  using (bucket_id = 'documents' and (owner = auth.uid() or public.is_hoofdcoach(auth.uid())));

create policy "documents_bucket_delete_owner_or_hoofdcoach"
  on storage.objects for delete
  to authenticated
  using (bucket_id = 'documents' and (owner = auth.uid() or public.is_hoofdcoach(auth.uid())));
