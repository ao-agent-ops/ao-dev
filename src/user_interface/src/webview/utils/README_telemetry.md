# UI Telemetry Implementation

This document describes the simplified telemetry implementation for tracking user interactions in the TypeScript UI components.

## Overview

The telemetry system now has a simplified architecture:

1. **Server Message Logging**: Most telemetry (node edits, experiment interactions, etc.) is handled automatically by logging all server messages in `develop_server.py`
2. **Node Input/Output Views**: UI-specific tracking when users view input or output content of graph nodes (with separate event types and actual content)
3. **Shim Control Registration**: Automatic logging when users run `aco-launch script.py`

## Architecture

### Files

- `src/webview/utils/telemetry.ts` - Simplified telemetry client for node input/output view tracking
- `src/webview/utils/config.ts` - Configuration management for credentials
- `src/webview/components/CustomNode.tsx` - Node input/output view tracking
- `src/providers/GraphViewProvider.ts` - Injects configuration into webview
- `src/telemetry/server_logger.py` - Main telemetry logic for server messages
- `package.json` - `@supabase/supabase-js` dependency

### Configuration

The telemetry system gets its configuration (DB url/key, user name) from the global config file.

### Events Tracked

#### 1. Server Messages (Automatic)
- **Location**: `src/server/develop_server.py`
- **Events**: Selective server messages with enhanced data
- **Implementation**: Single line call to `log_server_message(msg, session_graphs)` in `process_message()`
- **Special Handling**:
  - `deregister`: Includes full graph state with inputs/outputs in event_data
  - `edit_input`/`edit_output`: Stored as `input_edit`/`output_edit` with previous values
  - `restart`: Triggers code snapshots
  - `add_subrun`: Triggers code snapshots for first-time runs
  - `log`: Creates `user_logs` entries with foreign key references
- **Ignored**: `get_graph`, `clear`, `add_node`, `shutdown` (not logged)

#### 2. Shim Control Registration (Automatic)
- **Location**: `src/server/develop_server.py`
- **Event**: When user runs `aco-launch script.py` and shim-control registers
- **Implementation**: `log_shim_control_registration(handshake, session_id)`
- **Code Snapshots**: Automatically captured on every script launch

#### 3. Node Input/Output View (UI-specific)
- **Event Types**: `node_input_view` and `node_output_view`
- **Trigger**: User clicks "Edit Input" or "Edit Output" on a graph node
- **Data**: 
  - `node_input_view`: `{ node_id: string, input_value: string, node_type: string }`
  - `node_output_view`: `{ node_id: string, output_value: string, node_type: string }`

## Database Schema

Events are stored in the `user_actions` table:
```sql
CREATE TABLE user_actions (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  session_id TEXT,
  event_type TEXT NOT NULL,
  event_data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
```

Code snapshots are stored in the `code_snapshots` table with foreign key references:
```sql
CREATE TABLE code_snapshots (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  code_snapshot TEXT NOT NULL,  -- Base64 encoded zip data
  snapshot_size INTEGER,
  user_action_id BIGINT REFERENCES user_actions(id)
);
```

User logs are stored in the `user_logs` table with foreign key references:
```sql
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

## Usage

### Server-side (Automatic)
```python
# In develop_server.py - already implemented
log_server_message(msg, session_graphs)  # Logs selective messages with enhanced data
log_shim_control_registration(handshake, session_id)  # Logs script launches + snapshots
```

### UI-side (Manual)
```typescript
import { trackNodeInputView, trackNodeOutputView } from '../utils/telemetry';

// Track node input view
await trackNodeInputView(nodeId, inputValue, sessionId, nodeType);

// Track node output view
await trackNodeOutputView(nodeId, outputValue, sessionId, nodeType);
```

## Error Handling

- If Supabase credentials are not configured, telemetry is silently disabled
- Failed telemetry calls are logged to console but don't interrupt functionality
- All telemetry calls are asynchronous and non-blocking

## Privacy & Performance

- All telemetry data is sent asynchronously without blocking interactions
- Only essential interaction data is collected (no content or sensitive information)
- Users can disable telemetry by not providing Supabase configuration
- Server message logging captures the complete interaction flow automatically
- Code snapshots are captured automatically for runs and stored with foreign key references 