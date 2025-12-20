import * as vscode from 'vscode';
import { GoogleAuthenticationProvider } from './GoogleAuthenticationProvider';

/**
 * Manages authentication state and provides helpers for the extension
 */
export class AuthManager {
    private static instance: AuthManager;
    private _onAuthStateChanged = new vscode.EventEmitter<AuthState>();
    private currentState: AuthState = { authenticated: false };
    private authProvider?: GoogleAuthenticationProvider;

    public readonly onAuthStateChanged = this._onAuthStateChanged.event;

    private constructor(private context: vscode.ExtensionContext) {
        // Check initial auth state
        this.checkAuthState();
    }

    public static getInstance(context?: vscode.ExtensionContext): AuthManager {
        if (!AuthManager.instance && context) {
            AuthManager.instance = new AuthManager(context);
        }
        return AuthManager.instance;
    }

    public setAuthProvider(provider: GoogleAuthenticationProvider) {
        this.authProvider = provider;
    }

    private async checkAuthState() {
        try {
            const session = await vscode.authentication.getSession('google', [], { createIfNone: false });
            if (session) {
                // Try to extract picture from session scopes/account
                const userAvatar = (session as any).account?.picture || 
                                  (session as any).picture || 
                                  `https://www.gravatar.com/avatar/${session.account.id}?d=mp&s=200`;
                
                this.currentState = {
                    authenticated: true,
                    userId: session.account.id,
                    userName: session.account.label,
                    userEmail: session.account.label,
                    userAvatar: userAvatar,
                    session: session
                };
            } else {
                this.currentState = { authenticated: false };
            }
            this._onAuthStateChanged.fire(this.currentState);
        } catch (error) {
            console.error('Failed to check auth state:', error);
            this.currentState = { authenticated: false };
            this._onAuthStateChanged.fire(this.currentState);
        }
    }

    public async signIn(): Promise<AuthState> {
        try {
            const session = await vscode.authentication.getSession(
                'google',
                ['openid', 'email', 'profile'],
                { createIfNone: true }
            );

            if (session) {
                // Try to extract picture from session scopes/account
                const userAvatar = (session as any).account?.picture ||
                                  (session as any).picture ||
                                  `https://www.gravatar.com/avatar/${session.account.id}?d=mp&s=200`;

                this.currentState = {
                    authenticated: true,
                    userId: session.account.id,
                    userName: session.account.label,
                    userEmail: session.account.label,
                    userAvatar: userAvatar,
                    session: session
                };

                // Show message with timeout - use setStatusBarMessage instead for auto-dismiss
                vscode.window.setStatusBarMessage(`Signed in as ${session.account.label}`, 5000);
            } else {
                this.currentState = { authenticated: false };
            }

            this._onAuthStateChanged.fire(this.currentState);
            return this.currentState;
        } catch (error) {
            // Don't show error if user cancelled the login
            const errorMessage = error instanceof Error ? error.message : String(error);
            if (!errorMessage.includes('User did not consent') && !errorMessage.includes('Authentication was cancelled')) {
                vscode.window.showErrorMessage(`Sign in failed: ${error}`);
            }
            this.currentState = { authenticated: false };
            this._onAuthStateChanged.fire(this.currentState);
            return this.currentState;
        }
    }

    public async signOut(): Promise<void> {
        try {
            const session = await vscode.authentication.getSession('google', [], { createIfNone: false });
            if (session) {
                // Remove the session using the auth provider
                if (this.authProvider) {
                    await this.authProvider.removeSession(session.id);
                    vscode.window.setStatusBarMessage('Signed out successfully', 5000);
                } else {
                    // Fallback: delete the sessions from secrets storage directly
                    await this.context.secrets.delete('google.auth.sessions');
                    vscode.window.setStatusBarMessage('Signed out successfully', 5000);
                }
            }

            this.currentState = { authenticated: false };
            this._onAuthStateChanged.fire(this.currentState);
        } catch (error) {
            console.error('Sign out failed:', error);
            // Even if there's an error, clear the local state
            this.currentState = { authenticated: false };
            this._onAuthStateChanged.fire(this.currentState);
        }
    }

    public getCurrentState(): AuthState {
        return this.currentState;
    }

    public async refreshState(): Promise<void> {
        await this.checkAuthState();
    }
}

export interface AuthState {
    authenticated: boolean;
    userId?: string;
    userName?: string;
    userEmail?: string;
    userAvatar?: string;
    session?: vscode.AuthenticationSession;
}
