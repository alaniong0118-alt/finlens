-- Run by the official PostgreSQL entrypoint only for a new data directory.
-- The vector type must exist before the historical embedding migration runs.
CREATE EXTENSION IF NOT EXISTS vector;
