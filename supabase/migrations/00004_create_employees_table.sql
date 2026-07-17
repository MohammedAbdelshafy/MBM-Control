-- supabase/migrations/00004_create_employees_table.sql

create table if not exists public.employees (
  id bigint primary key generated always as identity,
  name text not null,
  email text,
  created_at timestamptz default now()
);

alter table public.employees enable row level security;
