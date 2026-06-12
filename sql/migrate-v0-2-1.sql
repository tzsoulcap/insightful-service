-- =========================================================
-- v0.2.1 — Fix process_pdf status check constraint
-- =========================================================
-- The original constraint only allowed ('pending','processing','completed','failed')
-- but the batch worker uses 'success', 'uploading', 'uploaded', 'error', 'upload_failed'.
-- This migration expands the constraint to match all statuses actually set by the worker.
-- =========================================================

BEGIN;

ALTER TABLE process_pdf
  DROP CONSTRAINT IF EXISTS chk_process_pdf_status;

ALTER TABLE process_pdf
  ADD CONSTRAINT chk_process_pdf_status
  CHECK (
    status IN (
      'pending',
      'processing',
      'success',
      'uploading',
      'uploaded',
      'error',
      'upload_failed',
      'completed',
      'failed'
    )
  );

COMMIT;
