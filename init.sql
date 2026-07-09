-- GateKeeper init script
-- Schema is created by SQLAlchemy on app startup.
-- This script ensures the database exists and grants permissions.

GRANT ALL PRIVILEGES ON DATABASE gatekeeper TO gatekeeper;

-- session_state table (created for Docker init; SQLAlchemy create_all also handles this)
CREATE TABLE IF NOT EXISTS session_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR NOT NULL,
    tool_name VARCHAR NOT NULL,
    args JSONB NOT NULL,
    decision VARCHAR NOT NULL,
    tags JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_session_state_session_id ON session_state (session_id);
CREATE INDEX IF NOT EXISTS ix_session_state_tool_name ON session_state (tool_name);
CREATE INDEX IF NOT EXISTS ix_session_state_created_at ON session_state (created_at);
CREATE INDEX IF NOT EXISTS ix_session_state_lookup ON session_state (session_id, tool_name, created_at);
