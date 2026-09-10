-- ============================================================================
-- The TopsportSpace — initial schema
-- profiles · invitations · documents · comments · messages (Dug-out Chat)
-- ============================================================================
-- Two roles only: hoofdcoach (full rights incl. inviting/removing coaches)
-- and assistent_coach (can upload/edit documents and lists, chat, but
-- cannot manage users). There are no separate "players" in this product —
-- every account is a coach account.
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
-- 'documents' Supabase Storage bucket (created separately via the
-- dashboard/CLI — storage buckets aren't managed by SQL migrations).
-- ----------------------------------------------------------------------------
create table public.documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  file_path text not null,
  file_type text not null,
  tags text[] not null default '{}',
  uploaded_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index documents_uploaded_by_idx on public.documents (uploaded_by);
create index documents_tags_idx on public.documents using gin (tags);

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
-- edits in the chat and document-comment threads can be reconciled locally.
alter table public.messages replica identity full;
alter table public.comments replica identity full;

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
-- Realtime: publish messages + comments so Supabase Realtime's
-- postgres_changes can stream INSERT/UPDATE/DELETE to subscribed clients
-- (the Dug-out Chat and document-comment threads).
-- ============================================================================
alter publication supabase_realtime add table public.messages;
alter publication supabase_realtime add table public.comments;
