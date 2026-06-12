BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- DROP OLD TABLES
-- =========================================================

DROP TABLE IF EXISTS chat_message_citations CASCADE;
DROP TABLE IF EXISTS knowledge_permissions CASCADE;
DROP TABLE IF EXISTS group_members CASCADE;
DROP TABLE IF EXISTS groups CASCADE;
DROP TABLE IF EXISTS process_pdf CASCADE;
DROP TABLE IF EXISTS batch CASCADE;
DROP TABLE IF EXISTS knowledge_bases CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  username VARCHAR(150) NOT NULL,
  user_type VARCHAR(20) NOT NULL DEFAULT 'local',
  hashed_password VARCHAR(255),

  role VARCHAR(20) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ,

  CONSTRAINT users_username_usertype_unique
    UNIQUE (username, user_type),

  CONSTRAINT chk_users_user_type
    CHECK (user_type IN ('local', 'ad')),

  CONSTRAINT chk_users_role
    CHECK (role IN ('user', 'admin', 'super_admin'))
);

CREATE INDEX users_is_active_idx
ON users (is_active);

-- =========================================================
-- GROUPS
-- =========================================================

CREATE TABLE groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  name VARCHAR(100) NOT NULL,
  description TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT groups_name_unique
    UNIQUE (name)
);

-- =========================================================
-- GROUP MEMBERS
-- =========================================================

CREATE TABLE group_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  group_id UUID NOT NULL,
  user_id UUID NOT NULL,

  CONSTRAINT fk_group_members_group
    FOREIGN KEY (group_id)
    REFERENCES groups(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_group_members_user
    FOREIGN KEY (user_id)
    REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT group_members_group_user_unique
    UNIQUE (group_id, user_id)
);

CREATE INDEX group_members_user_idx
ON group_members (user_id);

CREATE INDEX group_members_group_idx
ON group_members (group_id);

-- =========================================================
-- KNOWLEDGE BASES
-- =========================================================

CREATE TABLE knowledge_bases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  dify_dataset_id TEXT NOT NULL,
  dify_dataset_name TEXT NOT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT knowledge_bases_dify_dataset_unique
    UNIQUE (dify_dataset_id)
);

-- =========================================================
-- KNOWLEDGE PERMISSIONS
-- =========================================================

CREATE TABLE knowledge_permissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  knowledge_id UUID NOT NULL,

  group_id UUID,
  user_id UUID,

  permission_level VARCHAR(20) NOT NULL,

  CONSTRAINT fk_knowledge_permissions_knowledge
    FOREIGN KEY (knowledge_id)
    REFERENCES knowledge_bases(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_knowledge_permissions_group
    FOREIGN KEY (group_id)
    REFERENCES groups(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_knowledge_permissions_user
    FOREIGN KEY (user_id)
    REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT chk_knowledge_permissions_target
    CHECK (
      (group_id IS NOT NULL AND user_id IS NULL)
      OR
      (group_id IS NULL AND user_id IS NOT NULL)
    ),

  CONSTRAINT chk_knowledge_permissions_level
    CHECK (permission_level IN ('read', 'write', 'admin'))
);

CREATE INDEX knowledge_permissions_knowledge_idx
ON knowledge_permissions (knowledge_id);

CREATE INDEX knowledge_permissions_group_idx
ON knowledge_permissions (group_id);

CREATE INDEX knowledge_permissions_user_idx
ON knowledge_permissions (user_id);

CREATE UNIQUE INDEX knowledge_permissions_knowledge_group_unique
ON knowledge_permissions (knowledge_id, group_id)
WHERE group_id IS NOT NULL;

CREATE UNIQUE INDEX knowledge_permissions_knowledge_user_unique
ON knowledge_permissions (knowledge_id, user_id)
WHERE user_id IS NOT NULL;

-- =========================================================
-- BATCH
-- =========================================================

CREATE TABLE batch (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  knowledge_id UUID,

  dataset_id TEXT NOT NULL,
  dataset_name TEXT NOT NULL,

  status TEXT NOT NULL DEFAULT 'pending',
  total_files INTEGER NOT NULL DEFAULT 0,

  created_by UUID,
  scheduled_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_batch_knowledge
    FOREIGN KEY (knowledge_id)
    REFERENCES knowledge_bases(id)
    ON DELETE SET NULL,

  CONSTRAINT fk_batch_created_by
    FOREIGN KEY (created_by)
    REFERENCES users(id)
    ON DELETE SET NULL,

  CONSTRAINT chk_batch_status
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

  CONSTRAINT chk_batch_total_files_non_negative
    CHECK (total_files >= 0)
);

CREATE INDEX batch_knowledge_idx
ON batch (knowledge_id);

CREATE INDEX batch_dataset_idx
ON batch (dataset_id);

CREATE INDEX batch_status_idx
ON batch (status);

CREATE INDEX batch_created_by_idx
ON batch (created_by);

-- =========================================================
-- PROCESS PDF
-- =========================================================

CREATE TABLE process_pdf (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  batch_id UUID NOT NULL,

  filename TEXT NOT NULL,
  original_file_path TEXT NOT NULL,

  pdf_type TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  current_step TEXT,

  retry_count INTEGER NOT NULL DEFAULT 0,
  error_msg TEXT,

  dify_document_id TEXT,
  dify_batch TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_process_pdf_batch
    FOREIGN KEY (batch_id)
    REFERENCES batch(id)
    ON DELETE CASCADE,

  CONSTRAINT chk_process_pdf_pdf_type
    CHECK (
      pdf_type IS NULL
      OR pdf_type IN ('NORMAL_TEXT', 'SCANNED_PDF', 'CORRUPT_ENCODING')
    ),

  CONSTRAINT chk_process_pdf_status
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

  CONSTRAINT chk_process_pdf_current_step
    CHECK (
      current_step IS NULL
      OR current_step IN (
        'rasterizing',
        'ocr',
        'formatting',
        'correcting',
        'embedding'
      )
    ),

  CONSTRAINT chk_process_pdf_retry_count_non_negative
    CHECK (retry_count >= 0)
);

CREATE INDEX process_pdf_batch_idx
ON process_pdf (batch_id);

CREATE INDEX process_pdf_dify_document_idx
ON process_pdf (dify_document_id);

CREATE INDEX process_pdf_batch_document_idx
ON process_pdf (batch_id, dify_document_id);

CREATE INDEX process_pdf_status_idx
ON process_pdf (status);

-- =========================================================
-- CHAT MESSAGE CITATIONS
-- =========================================================

CREATE TABLE chat_message_citations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Dify message linkage
  dify_conversation_id TEXT NOT NULL,
  dify_message_id TEXT NOT NULL,

  -- App ownership
  user_id UUID NOT NULL,
  tenant_id TEXT,

  -- Optional normalized links
  knowledge_id UUID,
  process_pdf_id UUID,

  -- Ordering in source panel
  position INTEGER NOT NULL,

  -- Dify Knowledge identity
  dify_dataset_id TEXT NOT NULL,
  dify_dataset_name TEXT,

  dify_document_id TEXT,
  dify_document_name TEXT,

  dify_segment_id TEXT NOT NULL,
  segment_position INTEGER,

  -- Retrieval result
  score DOUBLE PRECISION,
  retrieval_rank INTEGER,
  search_method TEXT,

  -- Snapshot ของ chunk ตอน retrieve
  content TEXT NOT NULL,
  content_hash TEXT,

  -- Nullable snapshot/fallback fields
  file_name TEXT,
  file_path TEXT,
  page_no INTEGER,

  -- Flexible metadata
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_chat_message_citations_user
    FOREIGN KEY (user_id)
    REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_chat_message_citations_knowledge
    FOREIGN KEY (knowledge_id)
    REFERENCES knowledge_bases(id)
    ON DELETE SET NULL,

  CONSTRAINT fk_chat_message_citations_process_pdf
    FOREIGN KEY (process_pdf_id)
    REFERENCES process_pdf(id)
    ON DELETE SET NULL,

  CONSTRAINT chat_message_citations_message_position_unique
    UNIQUE (dify_message_id, position),

  CONSTRAINT chk_chat_message_citations_position
    CHECK (position > 0),

  CONSTRAINT chk_chat_message_citations_page_no
    CHECK (page_no IS NULL OR page_no > 0),

  CONSTRAINT chk_chat_message_citations_score
    CHECK (score IS NULL OR score >= 0),

  CONSTRAINT chk_chat_message_citations_retrieval_rank
    CHECK (retrieval_rank IS NULL OR retrieval_rank > 0)
);

CREATE INDEX chat_message_citations_message_idx
ON chat_message_citations (dify_message_id);

CREATE INDEX chat_message_citations_conversation_idx
ON chat_message_citations (dify_conversation_id);

CREATE INDEX chat_message_citations_user_conversation_idx
ON chat_message_citations (user_id, dify_conversation_id);

CREATE INDEX chat_message_citations_knowledge_idx
ON chat_message_citations (knowledge_id);

CREATE INDEX chat_message_citations_process_pdf_idx
ON chat_message_citations (process_pdf_id);

CREATE INDEX chat_message_citations_segment_idx
ON chat_message_citations (dify_segment_id);

CREATE INDEX chat_message_citations_document_idx
ON chat_message_citations (dify_document_id);

CREATE INDEX chat_message_citations_dataset_idx
ON chat_message_citations (dify_dataset_id);

CREATE INDEX chat_message_citations_metadata_gin
ON chat_message_citations USING GIN (metadata);

-- =========================================================
-- UPDATED_AT TRIGGER
-- =========================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_updated_at
BEFORE UPDATE ON batch
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_process_pdf_updated_at
BEFORE UPDATE ON process_pdf
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;