-- Phase 0.4: profiles table with RLS
create table public.profiles (
  id          uuid        references auth.users(id) on delete cascade primary key,
  role        text        not null default 'viewer' check (role in ('admin', 'viewer')),
  username    text        unique,
  created_at  timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Auto-create a viewer profile when a user signs up
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id)
  values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Security-definer helper so admin policies don't recurse
create or replace function public.get_my_role()
returns text
language sql
security definer
stable
set search_path = ''
as $$
  select role from public.profiles where id = auth.uid();
$$;

-- Policy: users can read their own profile
create policy "users_select_own"
  on public.profiles for select
  using (auth.uid() = id);

-- Policy: admins can read all profiles
create policy "admins_select_all"
  on public.profiles for select
  using (public.get_my_role() = 'admin');

-- Policy: users can update their own profile (username only; role locked by trigger below)
create policy "users_update_own"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Prevent users from escalating their own role
create or replace function public.lock_role_column()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  new.role := old.role;
  return new;
end;
$$;

create trigger prevent_role_change
  before update on public.profiles
  for each row
  when (new.role <> old.role)
  execute procedure public.lock_role_column();
