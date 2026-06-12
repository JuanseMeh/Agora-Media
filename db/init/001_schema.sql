CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE media_status AS ENUM ('uploaded', 'processing', 'completed', 'failed');
CREATE TYPE media_category AS ENUM ('image', 'audio', 'document', 'video', 'other');

CREATE TABLE media_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    bucket_name TEXT NOT NULL,
    content_hash TEXT,
    media_category media_category NOT NULL,
    status media_status NOT NULL DEFAULT 'uploaded',
    metadata JSONB DEFAULT '{}'::jsonb,
    width INT,
    height INT,
    duration_seconds DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_media_files_user_id ON media_files(user_id);
CREATE INDEX idx_media_files_status ON media_files(status);
CREATE INDEX idx_media_files_category ON media_files(media_category);

CREATE TABLE media_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_id UUID NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    field_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(media_id, entity_type, entity_id, field_name)
);

CREATE INDEX idx_media_links_entity ON media_links(entity_type, entity_id);
CREATE INDEX idx_media_links_media_id ON media_links(media_id);
