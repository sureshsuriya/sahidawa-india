SELECT cron.schedule(
  'cleanup_etl_failed_rows',
  '0 2 * * 0', -- Run every Sunday at 2 AM
  $$ DELETE FROM public.etl_failed_rows WHERE created_at < NOW() - INTERVAL '30 days'; $$
);
