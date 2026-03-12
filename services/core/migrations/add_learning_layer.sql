-- Execution Traces Table for Learning Layer
-- Stores execution traces persistently for cognitive cache and pattern mining

CREATE TABLE IF NOT EXISTS execution_traces (
    id SERIAL PRIMARY KEY,
    trace_id VARCHAR(255) UNIQUE NOT NULL,
    goal_id VARCHAR(255) NOT NULL,
    goal_title TEXT,
    goal_type VARCHAR(100),  -- NEW: for goal_type-based matching
    skill_name VARCHAR(255),
    status VARCHAR(50),
    confidence FLOAT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    events JSONB,  -- Store all events as JSON
    metadata JSONB  -- Additional metadata
);

CREATE INDEX IF NOT EXISTS idx_traces_goal_id ON execution_traces(goal_id);
CREATE INDEX IF NOT EXISTS idx_traces_goal_type ON execution_traces(goal_type);
CREATE INDEX IF NOT EXISTS idx_traces_skill_name ON execution_traces(skill_name);
CREATE INDEX IF NOT EXISTS idx_traces_status ON execution_traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_started_at ON execution_traces(started_at DESC);

-- Cognitive Cache Table - stores best skills per goal_type
CREATE TABLE IF NOT EXISTS cognitive_cache (
    id SERIAL PRIMARY KEY,
    goal_type VARCHAR(100) UNIQUE NOT NULL,
    best_skill VARCHAR(255) NOT NULL,
    confidence FLOAT NOT NULL,
    usage_count INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cognitive_cache_goal_type ON cognitive_cache(goal_type);
