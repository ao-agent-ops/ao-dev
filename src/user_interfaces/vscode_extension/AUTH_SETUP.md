# Google Authentication Setup for VSCode Extension

## Overview
The VSCode extension supports Google authentication so experiments can be filtered per user, similar to the web application. Users see a login screen when opening the extension and will only see their own experiments after authenticating.

## Requirements

1. **Google OAuth Credentials**: Make sure you have OAuth credentials configured in Google Cloud Console.
2. **Auth Server**: The authentication server (`auth_app.py`) must be running (either locally or deployed on AWS): `uvicorn ao.server.auth_app:app --host 0.0.0.0 --port 5958 --reload`
3. **Python Develop Server**: The develop server (`develop_server.py`) must be running and reachable from VSCode. 

## Google Cloud Console configuration

Add the following redirect URI to your Google OAuth app:

```
http://localhost:3456/callback
```

This redirect URI is used by the VSCode extension to receive the authorization code.

## Environment variables

Ensure these environment variables are present in your `.env` file:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here

# Auth Server URL (optional, default: http://localhost:5958)
VITE_API_BASE=http://localhost:5958
```

## VSCode configuration

The extension supports configuration for local or remote servers (AWS). You can configure three settings.

### Method 1: Settings UI (recommended)

1. Open **Settings** (Ctrl+,)
2. Search for "Agops AO"
3. Set the following options:

   - **Auth Server URL**: Authentication server URL
     - Local: `http://localhost:5958`
     - AWS: `https://tu-app.us-east-1.elasticbeanstalk.com` or `https://api.yourdomain.com`
   
   - **Python Server Host**: Host for the Python develop server (used for raw TCP local dev)
     - Local: `127.0.0.1`
     - Public IP example: `3.123.45.67` (EC2)

   - **Python Server Port**: Port for the Python develop server (used for raw TCP local dev)
     - Local: `5959`

   - **Python Server URL**: (optional) WebSocket URL used in production when connecting through the nginx/ws proxy
     - Production: `wss://ws.agops-project.com/ws`
     - Configure this as `ao.pythonServerUrl` in VSCode settings for production deployments

### Method 2: Settings JSON

Open **Preferences: Open Settings (JSON)** (Ctrl+Shift+P → "Preferences: Open Settings") and add:

```json
{
  // For local development
  "ao.authServerUrl": "http://localhost:5958",
  "ao.pythonServerHost": "127.0.0.1",
  "ao.pythonServerPort": 5959
}
```

Or for an AWS deployment:

```json
{
  // For a server deployed on AWS
  "ao.authServerUrl": "https://tu-app.us-east-1.elasticbeanstalk.com",
  // Preferred for production: use the websocket proxy URL (nginx terminates TLS)
  "ao.pythonServerUrl": "wss://ws.agops-project.com/ws",
  // Optional: raw host/port if you're using TCP directly
  "ao.pythonServerHost": "tu-app.us-east-1.elasticbeanstalk.com",
  "ao.pythonServerPort": 443
}
```

### Method 3: Workspace settings

To configure only the current project, create or edit `.vscode/settings.json` at the workspace root:

```json
{
  "ao.authServerUrl": "https://tu-app.us-east-1.elasticbeanstalk.com",
  "ao.pythonServerHost": "tu-app.us-east-1.elasticbeanstalk.com",
  "ao.pythonServerPort": 443
}
```

## Usage

### User flow (UI-based login)

The extension uses a UI-based login flow (instead of only commands):

1. **First time / Not authenticated:**
   - Open the "Graph View" sidebar — a login screen appears
   - The screen shows "Agops AO" with a lock icon
   - Message: "Please sign in to access your experiments"
   - Button: "Sign in with Google"

2. **Sign in:**
   - Click the "Sign in with Google" button
   - Your default browser opens
   - Complete the Google authentication flow and accept permissions
   - You should see: "Authentication Successful! You can close this window and return to VS Code"
   - Return to VSCode

3. **After sign-in:**
   - The login screen disappears
   - The "Experiments" view shows your experiments
   - The bottom area shows your user info:
     - Google profile picture
     - Name
     - Email
   - Experiments are automatically filtered to show only yours

4. **Sign out:**
   - Click your avatar at the bottom of the view
   - Choose "Logout"
   - You return to the login screen and experiments are hidden until you sign in again

### Alternative (Command Palette)

If you prefer commands, they are still available:

**Sign In:**
1. Open the Command Palette (Ctrl+Shift+P)
2. Run: `Graph Extension: Sign In with Google`
3. Follow the OAuth flow in the browser

**Sign Out:**
1. Open the Command Palette
2. Run: `Graph Extension: Sign Out`

## Architecture

### Authentication flow

1. **User initiates sign in** → `graphExtension.signIn` command
2. **Extension requests OAuth URL** → GET `${AUTH_BASE_URL}/auth/google/url?redirect_uri=http://localhost:3456/callback`
3. **Browser opens** → user authenticates with Google
4. **Google redirects** → `http://localhost:3456/callback?code=...`
5. **Extension captures the code** → local HTTP server on port 3456
6. **Exchange code for tokens** → POST `${AUTH_BASE_URL}/auth/google/callback` with `{code, redirect_uri}`
7. **Save session** → VSCode SecretStorage
8. **Update Python client** → send `user_id` in handshake and send `auth` message

### Python backend integration

- `PythonServerClient` connects to the host configured in `pythonServerHost:pythonServerPort`.
- During the initial handshake it sends `user_id` if the user is authenticated.
- Handshake format:
  ```json
  {
    "type": "hello",
    "role": "ui",
    "script": "vscode-extension",
    "user_id": "123456789"  // only when authenticated
  }
  ```
- When authentication state changes, an `auth` message is sent:
  ```json
  {
    "type": "auth",
    "user_id": "123456789"  // or undefined on logout
  }
  ```
- The Python server (`develop_server.py`) filters experiments by `user_id` (same behavior as web_app).
- Only experiments where `experiments.user_id = <current_user>` are shown.

## Differences vs Web App

| Aspect | Web App | VSCode Extension |
|--------|---------|------------------|
| UI for login | Full-screen login page | Centered webview in sidebar |
| Session storage | HTTP cookie | VSCode SecretStorage (encrypted) |
| OAuth redirect | `http://localhost:5958/auth/google/callback` or AWS callback | `http://localhost:3456/callback` |
| Callback handling | Browser redirect | Temporary local HTTP server |
| Login trigger | Button on Login screen | Button on LoginScreen or Command Palette |
| Profile picture | From Google API (`user.picture`) | From Google API (`user.picture`) |
| Logout | Dropdown menu on avatar | Dropdown menu on avatar or Command Palette |
| Server connection | Web App: WebSocket via Node proxy; VSCode: WSS (production) or direct TCP (local) | Direct TCP socket |
| Unauthenticated state | Shows LoginScreen full page | Shows LoginScreen in sidebar and hides experiments |

## Troubleshooting

### Error: "Failed to get Google OAuth URL"

Cause: Authentication server is not reachable

Fix:
- Ensure the authentication server is running
- Verify the `ao.authServerUrl` setting
- If using a remote server, check network connectivity:
  ```powershell
  Test-NetConnection -ComputerName tu-app.us-east-1.elasticbeanstalk.com -Port 443
  ```
- Check authentication server logs (CloudWatch Logs on AWS)

### Error: "Authentication was cancelled"

Cause: The OAuth flow was interrupted

Fix:
- The user closed the browser before completing the flow — retry
- Ensure no popup blockers interfere with the flow

### Experiments do not appear after sign-in

Cause: Authentication state sync issue

Fix:
- Open the webview Developer Tools: `Ctrl+Shift+P` → "Developer: Toggle Developer Tools"
- Look for logs prefixed with `[App]` or `[GraphViewProvider]`
- Verify an `authStateChanged` message with a valid `session` is received
- Try signing out and signing back in

### Experiments are not filtered correctly

Cause: `user_id` is not being sent to the Python server

Fix:
- Ensure the Python server (`develop_server.py`) is running and reachable
- Check Python server logs for the handshake and look for `"user_id"` in the message
- Verify `pythonServerHost` and `pythonServerPort` settings
- Test connectivity:
  ```powershell
  # Local
  Test-NetConnection -ComputerName 127.0.0.1 -Port 5959
  # AWS
  Test-NetConnection -ComputerName tu-app.us-east-1.elasticbeanstalk.com -Port 443
  ```

### Port 3456 already in use

Cause: Another process is using the OAuth callback port

Fix:
- Change `LOCAL_REDIRECT_PORT` in `GoogleAuthenticationProvider.ts` (for example, to 3457)
- Update the redirect URI in Google Cloud Console to `http://localhost:3457/callback`
- Rebuild the extension: `npm run compile`

### Cannot connect to Python server on AWS

Cause: Misconfiguration or inaccessible server

Fix:
- Ensure the Python server is deployed and running on EC2/Elastic Beanstalk/ECS
- Confirm the port is open in the AWS Security Groups
- If using HTTPS (port 443), confirm the server accepts direct TCP socket connections
- Consider switching to WebSocket for secure connections if needed
- Check AWS CloudWatch logs for connection attempts
- If using a Load Balancer, ensure health checks are passing
 - Consider switching to WebSocket for secure connections if needed
 - If using the VSCode extension in production with WSS, the extension requires the `ws` Node module to be installed in the extension package. Install in the `vscode_extension` folder before packaging:

```bash
cd src/user_interfaces/vscode_extension
npm install ws
npm run compile
```
 - Check AWS CloudWatch logs for connection attempts
 - If using a Load Balancer, ensure health checks are passing

### Profile picture not loading

Cause: The `picture` field is not propagated

Fix:
- In Developer Tools, verify `user.avatarUrl` is populated
- Ensure `auth_app.py` returns `user.picture`
- If missing, a generic Gravatar avatar will be used

### "Connection refused" when connecting to Python server

Cause: Server not listening or wrong configuration

Fix:
- Verify the Python server is running:
  ```powershell
  netstat -an | Select-String "5959"
  ```
- Verify configuration:
- `ao.pythonServerHost`
- `ao.pythonServerPort`
- If remote, check firewall and Security Groups
- View extension logs: `Ctrl+Shift+P` → "Developer: Show Logs"

## Testing

### Local development

To test authentication locally:

1. **Start the auth server:**
   ```powershell
   # From the project root
   Get-Content .env | ForEach-Object {
       if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
       $pair = $_ -split '=',2
       if ($pair.Length -eq 2) {
           Set-Item -Path Env:$($pair[0].Trim()) -Value $pair[1].Trim()
       }
   }
   python -m uvicorn ao.server.auth_app:app --host 0.0.0.0 --port 5958 --reload
   ```

2. **Start the develop server:**
   ```powershell
   python -m ao.server.develop_server
   ```

3. **Configure VSCode for local:**
   ```json
   {
     "ao.authServerUrl": "http://localhost:5958",
     "ao.pythonServerHost": "127.0.0.1",
     "ao.pythonServerPort": 5959
   }
   ```

4. **Test the full flow:**
   - Press F5 to open the Extension Development Host
   - Open the "Graph View" in the sidebar
   - You should see the login screen
   - Click "Sign in with Google" and complete the OAuth flow
   - Verify your experiments appear

5. **Check logs:**
   - **Auth server:** look for `/auth/google/url` and `/auth/google/callback` requests
   - **Python server:** look for the handshake with `user_id`:
     ```
     Received: {"type":"hello","role":"ui","script":"vscode-extension","user_id":"123456789"}
     ```
   - **VSCode Developer Tools:** `Ctrl+Shift+P` → "Developer: Toggle Developer Tools" and look for `[App]`, `[GraphViewProvider]`, `[PythonServerClient]` logs

6. **Verify filtering:**
   - Create an experiment from the extension
   - Ensure it has the correct `user_id` in the database
   - Sign out and verify no experiments are shown
   - Sign in with another account (if available) and verify only that account's experiments show

### Remote testing (AWS)

To test with servers deployed on AWS:

1. **Configure VSCode for AWS:**
   ```json
   {
     "ao.authServerUrl": "https://tu-app.us-east-1.elasticbeanstalk.com",
     "ao.pythonServerHost": "tu-app.us-east-1.elasticbeanstalk.com",
     "ao.pythonServerPort": 443
   }
   ```

2. **Verify services are reachable:**
   ```powershell
   # Auth server
   Invoke-WebRequest -Uri "https://tu-app.us-east-1.elasticbeanstalk.com/auth/google/url" -Method GET
   
   # Python server (if it exposes an HTTP health endpoint)
   Test-NetConnection -ComputerName tu-app.us-east-1.elasticbeanstalk.com -Port 443
   ```

3. **Update Google Cloud Console:**
   - Add your AWS auth server's callback to the authorized redirect URIs
   - If your auth server is `https://tu-app.us-east-1.elasticbeanstalk.com`, the callback will be:
     `https://tu-app.us-east-1.elasticbeanstalk.com/auth/google/callback`
   - Keep `http://localhost:3456/callback` for local development

4. **Monitor logs on AWS:**
   - AWS Console → CloudWatch → Log Groups
   - Find your app's log group (for example `/aws/elasticbeanstalk/tu-app/var/log/web.stdout.log`)
   - Look for requests to `/auth/google/*` and connections to the Python server

5. **If the Python server doesn't respond, check:**
   - Security Groups (inbound rules for ports 443/5959)
   - Network ACLs
   - Application Load Balancer configuration (if used)
   - EC2 instance status and health checks
   - VPC routing and subnet configuration (if using private VPC)

## Migration for existing experiments

Experiments created before authentication was implemented will have `user_id = NULL` and will not be visible to authenticated users. To assign them to a user:

```sql
-- SQLite
UPDATE experiments SET user_id = <user_id> WHERE user_id IS NULL;

-- PostgreSQL
UPDATE experiments SET user_id = <user_id> WHERE user_id IS NULL;
```

Where `<user_id>` is the ID of the user from the `users` table.

### Get a user's user_id

```sql
-- By email
SELECT id, email, name FROM users WHERE email = 'user@example.com';

-- List users
SELECT id, email, name, created_at FROM users ORDER BY created_at DESC;
```

## Advanced configuration

### Multiple environments

You can create different configuration profiles per environment:

**.vscode/settings.json** (local development):
```json
{
  "ao.authServerUrl": "http://localhost:5958",
  "ao.pythonServerHost": "127.0.0.1",
  "ao.pythonServerPort": 5959
}
```

**User settings** (production AWS):
```json
{
  "ao.authServerUrl": "https://prod-app.us-east-1.elasticbeanstalk.com",
  "ao.pythonServerHost": "prod-app.us-east-1.elasticbeanstalk.com",
  "ao.pythonServerPort": 443
}
```

### Environment variables for settings

You can also use environment variables on your system:

```powershell
# Windows
$env:VSCODE_AGOPS_AUTH_URL = "https://tu-app.us-east-1.elasticbeanstalk.com"
$env:VSCODE_AGOPS_PYTHON_HOST = "tu-app.us-east-1.elasticbeanstalk.com"
$env:VSCODE_AGOPS_PYTHON_PORT = "443"
```

The code in `GoogleAuthenticationProvider.ts` and `PythonServerClient.ts` reads from `process.env` with fallbacks to the configured settings.

### Advanced debugging

For deeper authentication debugging:

1. **Enable extension logs:**
   - Output panel: `View` → `Output` → select "Extension Host"
   - Look for logs from `[PythonServerClient]`, `[GraphViewProvider]`

2. **Inspect SecretStorage:**
   ```javascript
   // From the webview Developer Tools
   // You cannot directly access SecretStorage for security reasons,
   // but you can query whether a session exists via the extension API
   vscode.postMessage({ type: 'debug_auth' });
   ```

3. **Network monitoring:**
   - Developer Tools → Network tab
   - Look for requests to `/auth/google/*`
   - Verify responses and status codes

4. **Python server logs:**
   ```python
   # In develop_server.py, add detailed logging
   logger.info(f"Handshake received: {message}")
   logger.info(f"User ID from handshake: {conn_info.get('user_id')}")
   ```

## Full architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        VSCode Extension                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐          ┌────────────────────┐           │
│  │  LoginScreen.tsx │────────▶│   App.tsx          │           │
│  │  (UI)            │          │  (Webview)         │           │
│  └──────────────────┘          └────────┬───────────┘           │
│                                         │                       │
│                                         │ postMessage           │
│                                         ▼                       │
│                              ┌──────────────────────┐           │
│                              │ GraphViewProvider.ts │           │
│                              │ (Extension Host)     │           │
│                              └──────┬───────┬───────┘           │
│                                     │       │                   │
│                                     │       │                   │
│                    ┌────────────────┘       └──────────────┐    │
│                    ▼                                       ▼    │
│         ┌──────────────────┐                    ┌──────────────┐│
│         │  AuthManager.ts  │                    │ PythonServer ││
│         │                  │                    │ Client.ts    ││
│         └────────┬─────────┘                    └──────┬───────┘│
│                  │                                     │        │
│                  │ signIn/signOut                      │ TCP    │
│                  ▼                                     │        │
│    ┌──────────────────────────────┐                    │        │
│    │ GoogleAuthenticationProvider │                    │        │
│    │ (OAuth Flow)                 │                    │        │
│    └────────┬─────────────────────┘                    │        │
│             │                                          │        │
└─────────────┼──────────────────────────────────────────┼────────┘
              │ HTTP                                     │ Socket
              │ (localhost:3456 callback)                │
              ▼                                          ▼
    ┌──────────────────┐                    ┌────────────────────┐
    │  auth_app.py     │                    │ develop_server.py  │
    │  (Port 5958)     │                    │ (Port 5959)        │
    │                  │                    │                    │
    │  - /auth/google/ │                    │ - WebSocket server │
    │    url           │                    │ - Experiment mgmt  │
    │  - /auth/google/ │                    │ - User filtering   │
    │    callback      │                    │                    │
    └──────────────────┘                    └────────────────────┘
              │                                           │
              │ OAuth                                     │ DB Query
              ▼                                           ▼
    ┌──────────────────┐                    ┌────────────────────┐
    │  Google OAuth    │                    │  Database          │
    │  (accounts.google│                    │  (SQLite/Postgres) │
    │   .com)          │                    │                    │
    └──────────────────┘                    │  - users table     │
                                            │  - experiments     │
                                            │    (filtered by    │
                                            │     user_id)       │
                                            └────────────────────┘
```

## Additional resources

- **Google Cloud Console:** https://console.cloud.google.com
- **VSCode Extension API:** https://code.visualstudio.com/api
- **VSCode Authentication API:** https://code.visualstudio.com/api/references/vscode-api#authentication
