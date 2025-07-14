import * as vscode from 'vscode';
import { EditDialogProvider } from './EditDialogProvider';
import { PythonServerClient } from './PythonServerClient';

export class GraphViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'graphExtension.graphView';
    private _view?: vscode.WebviewView;
    private _editDialogProvider?: EditDialogProvider;
    // Removed _pendingEdit

    constructor(private readonly _extensionUri: vscode.Uri) {}

    public setEditDialogProvider(provider: EditDialogProvider): void {
        this._editDialogProvider = provider;
    }

    public handleEditDialogSave(value: string, context: { nodeId: string; field: string; session_id?: string }): void {
        if (this._view) {
            console.log('GraphViewProvider: Sending updateNode for node', context.nodeId, 'with session_id:', context.session_id);
            this._view.webview.postMessage({
                type: 'updateNode',
                payload: {
                    nodeId: context.nodeId,
                    field: context.field,
                    value,
                    session_id: context.session_id, // should be present!
                }
            });
        }
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        // Start/connect to the Python server and set up message forwarding
        const pythonClient = PythonServerClient.getInstance();
        pythonClient.startServerIfNeeded();
        pythonClient.onMessage((msg) => {
            // Forward all messages from the Python server to the webview
            if (this._view) {
                this._view.webview.postMessage(msg);
            }
        });

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
        this._sendCurrentTheme();
        vscode.window.onDidChangeActiveColorTheme(() => {
            this._sendCurrentTheme();
        });

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(data => {
            console.log(`GraphViewProvider: Received message from webview: ${data.type}`, data);
            if (data.type === 'showEditDialog') {
                console.log('GraphViewProvider: Received showEditDialog for node', data.payload.nodeId, 'with session_id:', data.payload.session_id);
            }
            if (data.type === 'restart') {
                if (!data.session_id) {
                    console.error('Restart message missing session_id! Not forwarding to Python server.');
                    return;
                }
                pythonClient.sendMessage({ type: 'restart', session_id: data.session_id });
            }
            switch (data.type) {
                case 'updateNode':
                    // Forward the updateNode message to the develop server
                    pythonClient.sendMessage(data);
                    break;
                case 'edit_input':
                    console.log('GraphViewProvider: Forwarding edit_input to Python server:', data);
                    // Forward the edit_input message to the develop server
                    pythonClient.sendMessage(data);
                    break;
                case 'edit_output':
                    console.log('GraphViewProvider: Forwarding edit_output to Python server:', data);
                    // Forward the edit_output message to the develop server
                    pythonClient.sendMessage(data);
                    break;
                case 'ready':
                    // Webview is ready - server will send graph data automatically
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
                case 'showEditDialog':
                    if (this._editDialogProvider) {
                        this._editDialogProvider.show(
                            `${data.payload.label} ${data.payload.field === 'input' ? 'Input' : 'Output'}`,
                            data.payload.value,
                            {
                                nodeId: data.payload.nodeId,
                                field: data.payload.field,
                                session_id: data.payload.session_id,
                            }
                        );
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
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'dist', 'webview.js'));

        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Graph View</title>
                <script>
                    // Polyfill process
                    window.process = {
                        env: {},
                        platform: 'browser',
                        version: '',
                        versions: {},
                        type: 'renderer',
                        arch: 'x64'
                    };
                </script>
            </head>
            <body>
                <div id="root"></div>
                <script>
                    const vscode = acquireVsCodeApi();
                    window.vscode = vscode;
                </script>
                <script src="${scriptUri}"></script>
            </body>
            </html>`;
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
}