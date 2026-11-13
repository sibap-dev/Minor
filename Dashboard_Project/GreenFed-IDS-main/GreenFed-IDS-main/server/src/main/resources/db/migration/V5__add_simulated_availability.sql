ALTER TABLE network_samples
ADD COLUMN IF NOT EXISTS availability DOUBLE PRECISION;

ALTER TABLE network_samples
ADD CONSTRAINT network_samples_availability_check
CHECK (availability IS NULL OR (availability >= 0 AND availability <= 1));
