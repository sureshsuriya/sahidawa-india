-- Prevent duplicate CDSCO drug alerts for the same batch and source.
ALTER TABLE public.drug_alerts
ADD CONSTRAINT unique_drug_alert
UNIQUE (batch_number, source_url);