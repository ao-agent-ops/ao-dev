import * as vscode from 'vscode';
import * as http from 'http';

interface GoogleUserInfo {
    id: string;
    email: string;
    name: string;
    picture?: string;
}

export class GoogleAuthenticationProvider implements vscode.AuthenticationProvider, vscode.Disposable {
    private static readonly AUTH_TYPE = 'google';
    private static readonly AUTH_NAME = 'Google';
    private static readonly SESSIONS_SECRET_KEY = 'google.auth.sessions';
    private static readonly LOCAL_REDIRECT_PORT = 3456; // Local port for OAuth callback
    
    private _sessionChangeEmitter = new vscode.EventEmitter<vscode.AuthenticationProviderAuthenticationSessionsChangeEvent>();
    private _disposable: vscode.Disposable;

    // Auth server base URL (same as web_app)
    private readonly AUTH_BASE_URL: string;

    constructor(private readonly context: vscode.ExtensionContext) {
        // Read auth server URL from configuration, fallback to localhost
        const config = vscode.workspace.getConfiguration('ao');
        this.AUTH_BASE_URL = config.get<string>('authServerUrl') || 'http://localhost:5958';

        this._disposable = vscode.authentication.registerAuthenticationProvider(
            GoogleAuthenticationProvider.AUTH_TYPE,
            GoogleAuthenticationProvider.AUTH_NAME,
            this,
            { supportsMultipleAccounts: false }
        );
    }

    get onDidChangeSessions() {
        return this._sessionChangeEmitter.event;
    }

    async getSessions(scopes?: string[]): Promise<vscode.AuthenticationSession[]> {
        const allSessions = await this.context.secrets.get(GoogleAuthenticationProvider.SESSIONS_SECRET_KEY);
        
        if (allSessions) {
            try {
                const sessions: vscode.AuthenticationSession[] = JSON.parse(allSessions);
                return sessions;
            } catch (e) {
                console.error('Failed to parse stored sessions', e);
            }
        }

        return [];
    }

    async createSession(scopes: string[]): Promise<vscode.AuthenticationSession> {
        try {
            const redirectUri = `http://localhost:${GoogleAuthenticationProvider.LOCAL_REDIRECT_PORT}/callback`;
            
            // Step 1: Get Google OAuth URL from our auth server with custom redirect_uri
            const urlResp = await fetch(`${this.AUTH_BASE_URL}/auth/google/url?redirect_uri=${encodeURIComponent(redirectUri)}`);
            if (!urlResp.ok) {
                throw new Error('Failed to get Google OAuth URL');
            }
            const { url } = await urlResp.json();

            // Step 2: Start local server to handle OAuth callback
            const code = await this.waitForOAuthCallback(url);
            
            if (!code) {
                throw new Error('Authentication was cancelled');
            }

            // Step 3: Exchange code for user info via our auth server
            const tokenResp = await fetch(`${this.AUTH_BASE_URL}/auth/google/callback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, redirect_uri: redirectUri })
            });

            if (!tokenResp.ok) {
                const errorText = await tokenResp.text();
                throw new Error(`Failed to exchange code for token: ${errorText}`);
            }

            const { user, accessToken } = await tokenResp.json();

            // Ensure we have a database user ID
            if (!user.id) {
                throw new Error('Auth server did not return a database user ID');
            }

            // Step 4: Create session with user picture - always use database ID, not Google ID
            const session: vscode.AuthenticationSession = {
                id: String(user.id),
                accessToken: accessToken,
                account: {
                    id: String(user.id),
                    label: user.email,
                    picture: user.picture // Include Google profile picture
                } as any, // Use 'as any' to extend the Account interface
                scopes: scopes
            };

            // Step 5: Store session
            await this.storeSessions([session]);

            // Notify listeners
            this._sessionChangeEmitter.fire({ added: [session], removed: [], changed: [] });

            return session;
        } catch (error) {
            // Don't show error message if user cancelled
            const errorMessage = error instanceof Error ? error.message : String(error);
            if (!errorMessage.includes('Authentication was cancelled')) {
                vscode.window.showErrorMessage(`Google authentication failed: ${error}`);
            }
            console.error('Create session error:', error);
            throw error;
        }
    }

    private async waitForOAuthCallback(authUrl: string): Promise<string | undefined> {
        return new Promise((resolve, reject) => {
            const server = http.createServer(async (req, res) => {
                const url = new URL(req.url!, `http://localhost:${GoogleAuthenticationProvider.LOCAL_REDIRECT_PORT}`);
                
                if (url.pathname === '/callback') {
                    const code = url.searchParams.get('code');
                    const error = url.searchParams.get('error');
                    
                    if (error) {
                        res.writeHead(400, { 'Content-Type': 'text/html' });
                        res.end('<html><body><h1>Authentication Failed</h1><p>You can close this window.</p></body></html>');
                        server.close();
                        resolve(undefined);
                        return;
                    }
                    
                    if (code) {
                        res.writeHead(200, { 'Content-Type': 'text/html' });
                        res.end('<html><body><h1>Authentication Successful!</h1><p>You can close this window and return to VS Code.</p></body></html>');
                        server.close();
                        resolve(code);
                        return;
                    }
                }
                
                res.writeHead(404);
                res.end();
            });

            server.listen(GoogleAuthenticationProvider.LOCAL_REDIRECT_PORT, async () => {
                // Open browser for user to authenticate
                const opened = await vscode.env.openExternal(vscode.Uri.parse(authUrl));

                // If user cancelled the "open external website" dialog, close server and reject
                if (!opened) {
                    server.close();
                    resolve(undefined);
                }
            });

            server.on('error', (err) => {
                reject(err);
            });

            // Timeout after 2 minutes
            setTimeout(() => {
                server.close();
                resolve(undefined);
            }, 120000);
        });
    }

    async removeSession(sessionId: string): Promise<void> {
        const sessions = await this.getSessions();
        const sessionIndex = sessions.findIndex(s => s.id === sessionId);
        
        if (sessionIndex > -1) {
            const session = sessions[sessionIndex];
            sessions.splice(sessionIndex, 1);
            await this.storeSessions(sessions);
            
            this._sessionChangeEmitter.fire({ added: [], removed: [session], changed: [] });
        }
    }

    private async storeSessions(sessions: vscode.AuthenticationSession[]): Promise<void> {
        await this.context.secrets.store(
            GoogleAuthenticationProvider.SESSIONS_SECRET_KEY,
            JSON.stringify(sessions)
        );
    }

    dispose() {
        this._disposable.dispose();
    }
}
