# Telemetry Setup Guide

## 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a free account
2. Create a new project
3. Wait for the project to be ready (2-3 minutes)

## 2. Create Database Tables

In your Supabase dashboard, go to **SQL Editor** and run these commands:

```sql
-- Table for UI interaction events  
CREATE TABLE user_actions (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    event_type TEXT NOT NULL,
    event_data JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Table for code snapshots
CREATE TABLE code_snapshots (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    code_snapshot TEXT NOT NULL,  -- Base64 encoded binary data
    snapshot_size INTEGER,
    user_action_id BIGINT REFERENCES user_actions(id)
);

-- Table for aco.log(...) entries
CREATE TABLE user_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    log_msg TEXT,
    success BOOLEAN,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_action_id BIGINT REFERENCES user_actions(id)
);
```

## 3. Get Your Credentials

In your Supabase dashboard:

1. Go to **Settings** → **API**
2. Copy your **Project URL** and **anon public** key

## 4. Set Environment Variables

Add these to your environment (`.env` file or shell):

```bash
export SUPABASE_URL="https://your-project-id.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key-here"
```

## 5. Install Dependencies

```bash
pip install supabase
```

## 6. Test the Setup

```python
from telemetry.server_logger import log_server_message, log_shim_control_registration
from telemetry.snapshots import store_code_snapshot

# Test server message logging
test_msg = {
    "type": "test_message",
    "session_id": "test_session_123",
    "data": "test_data"
}
log_server_message(test_msg)
print("Server message logged")

# Test shim control registration
test_handshake = {
    "cwd": "/test/path",
    "command": "python test.py",
    "name": "test_experiment"
}
log_shim_control_registration(test_handshake, "test_session_123")
print("Shim control registration logged")

# Test enhanced message handling
session_graphs = {"test_session": {"nodes": [], "edges": []}}

test_log_msg = {
    "type": "log",
    "session_id": "test_session_log",
    "entry": "Test log message",
    "success": True
}
log_server_message(test_log_msg, session_graphs)
print("Log message processed")

# Test input edit with previous value
test_edit_msg = {
    "type": "edit_input", 
    "session_id": "test_session",
    "node_id": "node_1",
    "value": "new input"
}
log_server_message(test_edit_msg, session_graphs)
print("Edit message processed")

# Test code snapshot upload (automatic for runs, but can test manually)
from telemetry.snapshots import store_code_snapshot
success = store_code_snapshot("ferdi", "/path/to/project")
print(f"Snapshot uploaded: {success}")
```

## 7. Integration Points

### Code Snapshots (on aco-launch)

Add to your launch code:

```python
from telemetry.snapshots import store_code_snapshot_background

# In develop_shim.py or wherever aco-launch starts
store_code_snapshot_background(
    user_id="current_user",  # You'll need to determine this
    project_root=args.project_root
)
```

### UI Events

Add to your UI components (React/TypeScript):

```typescript
// Send to Python server via existing WebSocket
window.vscode.postMessage({
    type: 'telemetry_event',
    event_type: 'experiment_click',
    user_id: 'current_user',
    session_id: sessionId,
    event_data: { experiment_name: experiment.name }
});
```

Then handle in your Python server to call the telemetry functions.

## Notes

- The system gracefully handles missing credentials (logs warnings but doesn't crash)
- Code snapshots run in background threads to avoid blocking user workflows
- All operations are logged for debugging
- Free tier includes 500MB database + 1GB storage (plenty for your use case) 