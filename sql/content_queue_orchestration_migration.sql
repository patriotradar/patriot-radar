-- Extends content_queue statuses for dashboard approval orchestration.
-- Safe to run multiple times; only alters constraint when needed.

alter table public.content_queue
  drop constraint if exists content_queue_status_check;

alter table public.content_queue
  add constraint content_queue_status_check
  check (status in ('queued', 'pending', 'approved', 'blocked', 'posted', 'failed'));

create index if not exists content_queue_pending_idx
  on public.content_queue (status)
  where status in ('pending', 'approved', 'blocked');
