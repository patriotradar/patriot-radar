-- AI Code Governance queue — stores scanned issues, proposed fixes, and approval state.
-- Run once in Supabase SQL Editor before enabling the governance panel.

create table if not exists public.cr_ai_governance_issues (
  id uuid primary key default gen_random_uuid(),
  issue text not null,
  root_cause text not null default '',
  risk text not null default 'REVIEW'
    check (risk in ('SAFE', 'REVIEW', 'BLOCKED')),
  proposed_fix text not null default '',
  gemini_status text not null default 'PENDING'
    check (gemini_status in ('APPROVED', 'REJECTED', 'PENDING')),
  warnings jsonb not null default '[]'::jsonb,
  auto_applicable boolean not null default false,
  source_file text not null default '',
  scan_source text not null default 'manual',
  admin_status text not null default 'pending'
    check (admin_status in ('pending', 'approved', 'rejected', 'applied', 'failed')),
  apply_error text not null default '',
  admin_email text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  applied_at timestamptz
);

create index if not exists cr_ai_governance_issues_admin_status_idx
  on public.cr_ai_governance_issues (admin_status);

create index if not exists cr_ai_governance_issues_created_at_idx
  on public.cr_ai_governance_issues (created_at desc);

create index if not exists cr_ai_governance_issues_risk_idx
  on public.cr_ai_governance_issues (risk);

alter table public.cr_ai_governance_issues enable row level security;

create policy "Authenticated users read governance issues"
  on public.cr_ai_governance_issues
  for select
  to authenticated
  using (true);

-- Service role bypasses RLS for pipeline writes and admin API updates.
