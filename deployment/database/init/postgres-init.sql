-- ============================================================================
-- ESAB Recommender V2 - PostgreSQL Initialization Script
-- Creates database schema for session archival and analytics
-- ============================================================================

-- ==========================
-- 1. Database Setup
-- ==========================

-- Create database (if not exists, run this manually before this script)
-- CREATE DATABASE pconfig;

-- Connect to the database (if running via psql)
\c pconfig

-- ==========================
-- 2. Extensions
-- ==========================

-- UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- JSONB functions (already included in PostgreSQL)
-- CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search if needed

-- ==========================
-- 3. Create Archived Sessions Table
-- ==========================

CREATE TABLE IF NOT EXISTS archived_sessions (
    -- Primary key
    id SERIAL PRIMARY KEY,

    -- Session identifiers
    session_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,

    -- Session metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITH TIME ZONE,

    -- Session state
    current_state VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en',

    -- Conversation data (JSONB for flexible querying)
    conversation_history JSONB,
    master_parameters JSONB,
    response_json JSONB,

    -- Agent execution logs
    agent_logs JSONB,

    -- Session outcome
    status VARCHAR(50) DEFAULT 'completed',  -- completed, abandoned, finalized
    finalized BOOLEAN DEFAULT FALSE,

    -- Analytics
    message_count INTEGER DEFAULT 0,
    product_selections_count INTEGER DEFAULT 0,
    session_duration_seconds INTEGER,

    -- Indexes for common queries
    CONSTRAINT archived_sessions_session_id_key UNIQUE (session_id)
);

-- ==========================
-- 4. Create Indexes
-- ==========================

-- Index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_archived_sessions_user_id
ON archived_sessions(user_id);

-- Index for session_id lookups
CREATE INDEX IF NOT EXISTS idx_archived_sessions_session_id
ON archived_sessions(session_id);

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_archived_sessions_archived_at
ON archived_sessions(archived_at);

-- Index for status queries
CREATE INDEX IF NOT EXISTS idx_archived_sessions_status
ON archived_sessions(status);

-- GIN index for JSONB columns (for efficient JSON queries)
CREATE INDEX IF NOT EXISTS idx_archived_sessions_conversation_history
ON archived_sessions USING GIN (conversation_history);

CREATE INDEX IF NOT EXISTS idx_archived_sessions_master_parameters
ON archived_sessions USING GIN (master_parameters);

CREATE INDEX IF NOT EXISTS idx_archived_sessions_response_json
ON archived_sessions USING GIN (response_json);

-- ==========================
-- 5. Create Analytics Views (Optional)
-- ==========================

-- View: Session summary statistics
CREATE OR REPLACE VIEW session_summary_stats AS
SELECT
    COUNT(*) AS total_sessions,
    COUNT(DISTINCT user_id) AS unique_users,
    AVG(message_count) AS avg_messages_per_session,
    AVG(session_duration_seconds) AS avg_session_duration_sec,
    SUM(CASE WHEN finalized THEN 1 ELSE 0 END) AS finalized_sessions,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions,
    SUM(CASE WHEN status = 'abandoned' THEN 1 ELSE 0 END) AS abandoned_sessions
FROM archived_sessions;

-- View: User session history
CREATE OR REPLACE VIEW user_session_history AS
SELECT
    user_id,
    COUNT(*) AS total_sessions,
    AVG(message_count) AS avg_messages,
    AVG(session_duration_seconds) AS avg_duration_sec,
    MAX(archived_at) AS last_session_date,
    SUM(CASE WHEN finalized THEN 1 ELSE 0 END) AS finalized_count
FROM archived_sessions
GROUP BY user_id;

-- ==========================
-- 6. Create Functions (Optional)
-- ==========================

-- Function: Calculate session duration
CREATE OR REPLACE FUNCTION calculate_session_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.last_activity_at IS NOT NULL AND NEW.created_at IS NOT NULL THEN
        NEW.session_duration_seconds := EXTRACT(EPOCH FROM (NEW.last_activity_at - NEW.created_at))::INTEGER;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Auto-calculate session duration on insert/update
DROP TRIGGER IF EXISTS trigger_calculate_session_duration ON archived_sessions;
CREATE TRIGGER trigger_calculate_session_duration
BEFORE INSERT OR UPDATE ON archived_sessions
FOR EACH ROW
EXECUTE FUNCTION calculate_session_duration();

-- ==========================
-- 7. Grant Permissions
-- ==========================

-- Grant permissions to application user (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE ON archived_sessions TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE archived_sessions_id_seq TO your_app_user;
-- GRANT SELECT ON session_summary_stats, user_session_history TO your_app_user;

-- ==========================
-- 8. Sample Data (Optional)
-- ==========================

-- Uncomment below to insert sample archived session for testing

/*
INSERT INTO archived_sessions (
    session_id,
    user_id,
    current_state,
    language,
    conversation_history,
    master_parameters,
    response_json,
    status,
    finalized,
    message_count,
    product_selections_count,
    last_activity_at
) VALUES (
    uuid_generate_v4()::text,
    'user-test-001',
    'finalize',
    'en',
    '{"messages": [{"role": "user", "content": "I need a 500A MIG welder"}]}'::jsonb,
    '{"power_source": {"product_name": "Aristo 500ix", "process": "MIG (GMAW)"}}'::jsonb,
    '{"PowerSource": {"gin": "0446200880", "name": "Aristo 500ix"}}'::jsonb,
    'completed',
    true,
    5,
    1,
    CURRENT_TIMESTAMP
);
*/

-- ==========================
-- 9. Verify Setup
-- ==========================

-- Check table structure
\d archived_sessions

-- Check indexes
\di

-- Check views
\dv

-- Check functions
\df

-- Show sample statistics
SELECT * FROM session_summary_stats;

-- ==========================
-- 10. Database Statistics
-- ==========================

SELECT
    'archived_sessions' AS table_name,
    COUNT(*) AS row_count,
    pg_size_pretty(pg_total_relation_size('archived_sessions')) AS total_size
FROM archived_sessions;

-- ==========================
-- Initialization Complete
-- ==========================
