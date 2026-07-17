-- supabase/migrations/00005_add_department_column.sql

alter table if exists public.employees
add column department text default 'Hooli';
