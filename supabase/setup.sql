-- IFPK V45: PUBLIC ECONOMIC DATA ONLY. Never insert real clients' financial/identity data here.
-- Run once: Supabase Dashboard -> SQL Editor -> New query -> Run.

create table if not exists public.ifpk_observations (
    indicator_id text not null,
    month text not null check (month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    value numeric not null,
    unit text not null,
    provider text not null,
    source_code text not null,
    source_updated text not null default '',
    retrieved_at timestamptz not null,
    primary key (indicator_id, month)
);

create table if not exists public.ifpk_revisions (
    id bigint generated always as identity primary key,
    indicator_id text not null,
    month text not null,
    previous_value numeric not null,
    new_value numeric not null,
    detected_at timestamptz not null default now(),
    source_updated text not null default ''
);

create table if not exists public.ifpk_collection_runs (
    id uuid primary key,
    indicator_id text not null,
    started_at timestamptz not null,
    finished_at timestamptz not null,
    status text not null check (status in ('ok','failed','missing_key')),
    fetched int not null default 0,
    inserted int not null default 0,
    revised int not null default 0,
    message text not null default ''
);
create index if not exists ifpk_collection_runs_recent on public.ifpk_collection_runs(finished_at desc);

-- Revision history recorded in the SAME transaction as any actual CPI correction.
create or replace function public.ifpk_revision_audit() returns trigger
language plpgsql security definer set search_path=public as $$
begin
    if old.value is distinct from new.value then
        insert into public.ifpk_revisions(indicator_id, month, previous_value, new_value, source_updated)
        values(old.indicator_id, old.month, old.value, new.value, new.source_updated);
    end if;
    return new;
end;
$$;

drop trigger if exists ifpk_observations_audit on public.ifpk_observations;
create trigger ifpk_observations_audit
before update on public.ifpk_observations
for each row execute function public.ifpk_revision_audit();

-- No policy grants anon/authenticated access; the GitHub server-side secret writes snapshots.
alter table public.ifpk_observations enable row level security;
alter table public.ifpk_revisions enable row level security;
alter table public.ifpk_collection_runs enable row level security;
revoke all on public.ifpk_observations from anon, authenticated;
revoke all on public.ifpk_revisions from anon, authenticated;
revoke all on public.ifpk_collection_runs from anon, authenticated;
grant select, insert, update on public.ifpk_observations to service_role;
grant select, insert on public.ifpk_collection_runs to service_role;
grant select on public.ifpk_revisions to service_role;
grant usage, select on sequence public.ifpk_revisions_id_seq to service_role;

-- Note: Supabase Data API schema cache may need a refresh if table creation just finished.
notify pgrst, 'reload schema';
