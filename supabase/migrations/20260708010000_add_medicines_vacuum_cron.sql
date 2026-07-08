-- =============================================================================
-- SahiDawa - Schedule monthly maintenance for medicines vector index health
-- =============================================================================
-- HNSW vector indexes can accumulate bloat after frequent INSERT/UPDATE activity.
-- This monthly VACUUM ANALYZE keeps public.medicines statistics fresh and helps
-- maintain stable RAG search performance.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname = 'vacuum_analyze_medicines';

SELECT cron.schedule(
  'vacuum_analyze_medicines',
  '0 2 1 * *',
  $$ VACUUM ANALYZE public.medicines; $$
);
