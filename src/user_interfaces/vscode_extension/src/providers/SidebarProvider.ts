import * as vscode from 'vscode';
import * as fs from 'fs';
import { GraphTabProvider } from './GraphTabProvider';
import { PythonServerClient } from './PythonServerClient';
import { configManager } from './ConfigManager';
import { AuthManager } from './AuthManager';

export class SidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'graphExtension.graphView';
    private _view?: vscode.WebviewView;
    private _graphTabProvider?: GraphTabProvider;
    private _pendingMessages: any[] = [];
    private _pythonClient: PythonServerClient | null = null;
    private _authManager: AuthManager;
    private _messageHandler?: (msg: any) => void;
    private _windowStateListener?: vscode.Disposable;
    // The Python server connection is deferred until the webview sends 'ready'.
    // Buffering is needed to ensure no messages are lost if the server sends messages before the webview is ready.

    constructor(private readonly _extensionUri: vscode.Uri, private readonly _context: vscode.ExtensionContext) {
        // Set up Python server message forwarding with buffering
        this._authManager = AuthManager.getInstance(_context);
        
        // Listen to auth state changes and update webview
        this._authManager.onAuthStateChanged((state) => {
            if (this._view) {
                this._view.webview.postMessage({
                    type: 'authStateChanged',
                    payload: state
                });
            }
        });

        // Set up window focus detection to request experiments when VS Code regains focus
        this._windowStateListener = vscode.window.onDidChangeWindowState((state) => {
            if (state.focused && this._pythonClient) {
                // Window regained focus - request fresh experiment list from server
                this._pythonClient.sendMessage({ type: 'get_all_experiments' });
            }
        });
    }



    public setGraphTabProvider(provider: GraphTabProvider): void {
        this._graphTabProvider = provider;
    }

    // Robustly show or reveal the webview
    public showWebview() {
        if (!this._view || (this._view as any)._disposed) {
            // Create new webview view
            vscode.commands.executeCommand('workbench.view.extension.graphExtension-sidebar');
            // The view will be resolved via resolveWebviewView
        } else {
            this._view.show?.(true);
        }
    }


    public handleEditDialogSave(value: string, context: { nodeId: string; field: string; session_id?: string; attachments?: any }): void {
        this._view?.webview.postMessage({
            type: 'updateNode',
            payload: {
                nodeId: context.nodeId,
                field: context.field,
                value,
                session_id: context.session_id,
            }
        });
    }


    public resolveWebviewView(
        webviewView: vscode.WebviewView,
_context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        // Clean up reference when disposed
        webviewView.onDidDispose(() => {
            this._view = undefined;
        });

        // Request fresh experiment list when the webview becomes visible
        webviewView.onDidChangeVisibility(() => {
            if (webviewView.visible && this._pythonClient) {
                this._pythonClient.sendMessage({ type: 'get_all_experiments' });
            }
        });

        // Flush any pending messages to the webview
        this._pendingMessages.forEach(msg => {
            if (this._view) {
                this._view.webview.postMessage(msg);
            }
        });
        this._pendingMessages = [];

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri,
                vscode.Uri.joinPath(this._extensionUri, '..', 'node_modules')
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
        this._sendCurrentTheme();
        vscode.window.onDidChangeActiveColorTheme(() => {
            this._sendCurrentTheme();
        });

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(data => {
            switch (data.type) {
                case 'restart':
                    if (!data.session_id) {
                        console.error('Restart message missing session_id! Not forwarding to Python server.');
                        return;
                    }
                    this._pythonClient?.sendMessage({ type: 'restart', session_id: data.session_id });
                    break;
                case 'open_log_tab_side_by_side':
                    console.warn('NotesLogTabProvider not available');
                    break;
                case 'update_node':
                case 'edit_input':
                case 'edit_output':
                case 'get_graph':
                case 'erase':
                    this._pythonClient?.sendMessage(data);
                    break;
                case 'setDatabaseMode':
                    this._pythonClient?.sendMessage({ 
                        type: 'set_database_mode', 
                        mode: data.mode 
                    });
                    break;
                case 'ready':
                    // Webview is ready - now connect to the Python server and set up message forwarding
                    if (!this._pythonClient) {
                        this._pythonClient = PythonServerClient.getInstance();
                        this._pythonClient.ensureConnected(); // async but don't await - webview is ready
                        // Request experiment list on every connection (including reconnections after server restart)
                        this._pythonClient.onConnection(() => {
                            this._pythonClient?.sendMessage({ type: 'get_all_experiments' });
                        });
                        // Create message handler and store reference for cleanup
                        this._messageHandler = (msg) => {
                            // Intercept session_id message to set up config management
                            if (msg.type === 'session_id' && msg.config_path) {
                                try {
                                    configManager.setConfigPath(msg.config_path);

                                    // Set up config forwarding to webview
                                    configManager.onConfigChange((config) => {
                                        if (this._view) {
                                            this._view.webview.postMessage({
                                                type: 'configUpdate',
                                                detail: config
                                            });
                                        }
                                    });
                                } catch (e) {
                                    console.warn('[SidebarProvider] Error setting config_path:', e);
                                }
                            }
                            if (this._view) {
                                this._view.webview.postMessage(msg);
                            } else {
                                this._pendingMessages.push(msg);
                            }
                        };
                        // Forward all messages from the Python server to the webview, buffer if not ready
                        this._pythonClient.onMessage(this._messageHandler);
                        this._pythonClient.startServerIfNeeded();
                    }

                    // Send current auth state to webview
                    const authState = this._authManager.getCurrentState();
                    this._view?.webview.postMessage({
                        type: 'authStateChanged',
                        payload: authState
                    });

                    // If user is already authenticated, send auth message to server
                    // This ensures the server knows the user_id for filtering experiments
                    if (authState.authenticated && authState.userId && this._pythonClient) {
                        this._pythonClient.setUserId(authState.userId);
                        this._pythonClient.sendMessage({ type: 'auth', user_id: authState.userId });
                    }

                    // Request experiments after Python client is set up and auth state is sent
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage({ type: 'get_all_experiments' });
                    }
                    break;
                case 'signIn':
                    this._authManager.signIn().then((state) => {
                        if (state.authenticated && this._pythonClient) {
                            this._pythonClient.setUserId(state.userId);
                            this._pythonClient.sendMessage({ type: 'auth', user_id: state.userId });
                        }
                    });
                    break;
                case 'signOut':
                    this._authManager.signOut().then(() => {
                        if (this._pythonClient) {
                            this._pythonClient.setUserId(undefined);
                        }
                    });
                    break;
                case 'navigateToCode':
                    // Handle code navigation
                    const { filePath, line } = this._parseCodeLocation(data.payload.codeLocation);
                    if (filePath && line) {
                        vscode.workspace.openTextDocument(filePath).then(document => {
                            vscode.window.showTextDocument(document, {
                                selection: new vscode.Range(line - 1, 0, line - 1, 0)
                            });
                        });
                    }
                    break;
                case 'openGraphTab':
                    if (this._graphTabProvider && data.payload.experiment) {
                        this._graphTabProvider.createOrShowGraphTab(data.payload.experiment);
                    } else {
                        console.warn('[GraphViewProvider] No GraphTabProvider available or missing experiment data');
                    }
                    break;
                case 'requestExperimentRefresh':
                    // ExperimentsView has mounted and is ready to display data - request experiment list
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage({ type: 'get_all_experiments' });
                    }
                    break;
            }
        });
    }

    private _sendCurrentTheme() {
        const isDark = vscode.window.activeColorTheme.kind === vscode.ColorThemeKind.Dark;
        this._view?.webview.postMessage({
            type: 'vscode-theme-change',
            payload: {
                theme: isDark ? 'vscode-dark' : 'vscode-light',
            },
        });
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const path = require('path');
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'dist', 'webview.js'));
        const codiconsUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, '..', 'node_modules', '@vscode/codicons', 'dist', 'codicon.css'));
        const templatePath = path.join(
            this._extensionUri.fsPath,
            'src',
            'webview',
            'templates',
            'graphView.html'
        );
        let html = fs.readFileSync(templatePath, 'utf8');
        
        // Set up ConfigManager bridge to webview
        const configBridge = `
            window.configManager = {
                currentConfig: null,
                onConfigChange: function(callback) {
                    window.addEventListener('configUpdate', function(event) {
                        window.configManager.currentConfig = event.detail;
                        callback(event.detail);
                    });
                },
                getCurrentConfig: function() {
                    return window.configManager.currentConfig;
                }
            };
        `;
        
        console.log('🚀 Injecting config into webview');
        
        html = html.replace('const vscode = acquireVsCodeApi();', 
            `${configBridge}\n        const vscode = acquireVsCodeApi();`);
        html = html.replace(/{{scriptUri}}/g, scriptUri.toString());
        html = html.replace(/{{codiconsUri}}/g, codiconsUri.toString());
        return html;
    }

    private _parseCodeLocation(codeLocation: string): { filePath: string | undefined; line: number | undefined } {
        const match = codeLocation.match(/(.+):(\d+)/);
        if (match) {
            const [, filePath, lineStr] = match;
            return {
                filePath,
                line: parseInt(lineStr, 10)
            };
        }
        return { filePath: undefined, line: undefined };
    }

    public dispose(): void {
        // Clean up message listener
        if (this._pythonClient && this._messageHandler) {
            this._pythonClient.removeMessageListener(this._messageHandler);
            this._messageHandler = undefined;
        }
        // Clean up window state listener
        if (this._windowStateListener) {
            this._windowStateListener.dispose();
            this._windowStateListener = undefined;
        }
        // Clean up is handled by ConfigManager
    }
}