-- Enable the pg_cron extension if it is not already enabled
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule the TTL cleanup job for scan_history
-- This job runs every midnight to delete records older than 90 days
SELECT cron.schedule(
  'cleanup_scan_history',
  '0 0 * * *', -- Run every midnight
  $$ DELETE FROM public.scan_history WHERE created_at < NOW() - INTERVAL '90 days'; $$
);
