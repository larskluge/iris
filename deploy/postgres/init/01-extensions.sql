-- Runs once on a fresh Postgres data volume (docker-entrypoint-initdb.d).
-- Letta stores embeddings in a pgvector column and migrates assuming the
-- extension already exists.
CREATE EXTENSION IF NOT EXISTS vector;
