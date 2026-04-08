-- FTech AI Factory – initial schema
-- Run once against an empty PostgreSQL database.
-- The application uses Alembic for subsequent migrations.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enums
DO $$ BEGIN
  CREATE TYPE task_status AS ENUM ('backlog','dev','qa','docs','deploy','done','failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE agent_name AS ENUM ('development','qa','documentation','deploy','knowledge');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Tasks (Kanban cards)
CREATE TABLE IF NOT EXISTS tasks (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id         VARCHAR(100),
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    acceptance_criteria TEXT,
    status              task_status NOT NULL DEFAULT 'backlog',
    retries             INTEGER NOT NULL DEFAULT 0,
    payload             JSONB,
    result              JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_external_id ON tasks(external_id);

-- Execution log
CREATE TABLE IF NOT EXISTS task_executions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id     UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    agent       agent_name NOT NULL,
    success     BOOLEAN NOT NULL DEFAULT FALSE,
    output      JSONB,
    error       TEXT,
    duration_ms FLOAT NOT NULL DEFAULT 0,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_executions_task_id ON task_executions(task_id);

-- Knowledge / RAG store
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source      VARCHAR(512) NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content     TEXT NOT NULL,
    embedding   VECTOR(4096),           -- adjust dim to match your model
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge_documents(source);
-- pgvector HNSW index for fast approximate nearest-neighbour search
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_documents USING hnsw (embedding vector_cosine_ops);
