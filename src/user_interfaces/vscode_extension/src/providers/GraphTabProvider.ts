import * as vscode from 'vscode';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { PythonServerClient } from './PythonServerClient';
import { ProcessInfo } from '../../../shared_components/types';

export class GraphTabProvider implements vscode.WebviewPanelSerializer {
    public static readonly viewType = 'graphExtension.graphTab';
    private _panels: Map<string, vscode.WebviewPanel> = new Map();
    private _pythonClient: PythonServerClient | null = null;

    constructor(private readonly _extensionUri: vscode.Uri) {
        // Initialize Python client
        this._pythonClient = PythonServerClient.getInstance();
        this._pythonClient.ensureConnected(); // async but don't await in constructor
    }

    public async createOrShowGraphTab(experiment: ProcessInfo): Promise<void> {
        const sessionId = experiment.session_id;
        const columnToShowIn = vscode.window.activeTextEditor ? 
            vscode.ViewColumn.Beside : 
            vscode.ViewColumn.One;

        // Check if we already have a panel for this session
        let panel = this._panels.get(sessionId);
        
        if (panel) {
            // Check if panel is disposed
            if ((panel as any)._disposed || (panel as any).disposed) {
                this._panels.delete(sessionId);
                panel = undefined;
            } else {
                // Panel exists and is not disposed, just reveal it
                panel.reveal(columnToShowIn);
                return;
            }
        }

        // Create new panel
        panel = vscode.window.createWebviewPanel(
            GraphTabProvider.viewType,
            `Graph: ${experiment.run_name || sessionId.substring(0, 8)}...`,
            columnToShowIn,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    this._extensionUri,
                    vscode.Uri.joinPath(this._extensionUri, '..', 'node_modules')
                ]
            }
        );

        // Set up the webview content
        panel.webview.html = this._getHtmlForWebview(panel.webview, sessionId);

        // Store panel reference
        this._panels.set(sessionId, panel);

        // Handle panel disposal
        panel.onDidDispose(() => {
            this._panels.delete(sessionId);
        }, null);

        // Handle messages from the webview
        panel.webview.onDidReceiveMessage(data => {
            
            switch (data.type) {
                case 'ready':
                    // Send initial data to the tab
                    panel.webview.postMessage({
                        type: 'init',
                        payload: {
                            experiment,
                            sessionId
                        }
                    });
                    // Ensure Python client is available
                    if (!this._pythonClient) {
                        this._pythonClient = PythonServerClient.getInstance();
                        this._pythonClient.ensureConnected(); // async but don't await
                    }
                    // Request graph data
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage({
                            type: 'get_graph',
                            session_id: sessionId
                        });
                    } else {
                        console.error('[GraphTabProvider] Still no Python client available after getInstance()');
                    }
                    break;
                case 'restart':
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage({
                            type: 'restart',
                            session_id: sessionId
                        });
                    }
                    break;
                case 'erase':
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage({
                            type: 'erase',
                            session_id: sessionId
                        });
                    }
                    break;
                case 'update_node':
                case 'edit_input':
                case 'edit_output':
                case 'update_run_name':
                case 'update_result':
                case 'update_notes':
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage(data);
                    }
                    break;
                case 'navigateToCode':
                    const { filePath, line } = this._parseCodeLocation(data.payload.codeLocation);
                    if (filePath && line) {
                        vscode.workspace.openTextDocument(filePath).then(document => {
                            vscode.window.showTextDocument(document, {
                                selection: new vscode.Range(line - 1, 0, line - 1, 0)
                            });
                        });
                    }
                    break;
                case 'updateTabTitle':
                    const { sessionId: titleSessionId, title } = data.payload;
                    const targetPanel = this._panels.get(titleSessionId);
                    if (targetPanel && title) {
                        targetPanel.title = `Graph: ${title}`;
                    }
                    break;
                case 'get_lessons':
                    // Forward get_lessons request to Python server
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage({ type: 'get_lessons' });
                    }
                    break;
                case 'openLessonsTab':
                    // Open the lessons tab
                    this.createOrShowLessonsTab();
                    break;
                case 'openDocument':
                    this._handleOpenDocument(data.payload, panel);
                    break;
            }
        });

        // Set up message forwarding from Python server
        this._setupServerMessageForwarding(panel, sessionId);

        // Send theme info
        this._sendThemeToPanel(panel);
        vscode.window.onDidChangeActiveColorTheme(() => {
            this._sendThemeToPanel(panel);
        });
    }

    public async createOrShowLessonsTab(): Promise<void> {
        const lessonsTabId = 'lessons';
        const columnToShowIn = vscode.window.activeTextEditor ?
            vscode.ViewColumn.Beside :
            vscode.ViewColumn.One;

        // Check if we already have a lessons panel
        let panel = this._panels.get(lessonsTabId);

        if (panel) {
            // Check if panel is disposed
            if ((panel as any)._disposed || (panel as any).disposed) {
                this._panels.delete(lessonsTabId);
                panel = undefined;
            } else {
                // Panel exists and is not disposed, just reveal it
                panel.reveal(columnToShowIn);
                return;
            }
        }

        // Create new panel for lessons
        panel = vscode.window.createWebviewPanel(
            GraphTabProvider.viewType,
            'LLM Lessons',
            columnToShowIn,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    this._extensionUri,
                    vscode.Uri.joinPath(this._extensionUri, '..', 'node_modules')
                ]
            }
        );

        // Set up the webview content for lessons
        panel.webview.html = this._getHtmlForLessonsWebview(panel.webview);

        // Store panel reference
        this._panels.set(lessonsTabId, panel);

        // Handle panel disposal
        panel.onDidDispose(() => {
            this._panels.delete(lessonsTabId);
        }, null);

        // Handle messages from the webview
        panel.webview.onDidReceiveMessage(data => {
            switch (data.type) {
                case 'ready':
                    // Ensure Python client is available
                    if (!this._pythonClient) {
                        this._pythonClient = PythonServerClient.getInstance();
                        this._pythonClient.ensureConnected();
                    }
                    // Request lessons data
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage({ type: 'get_lessons' });
                    }
                    break;
                case 'add_lesson':
                case 'update_lesson':
                case 'delete_lesson':
                    // Forward lesson CRUD operations to Python server
                    if (this._pythonClient) {
                        this._pythonClient.sendMessage(data);
                    }
                    break;
                case 'navigateToRun':
                    // Navigate to a specific run's graph - handled by opening a new graph tab
                    if (data.sessionId) {
                        // We need to get the experiment info to open the graph tab
                        // For now, create a minimal experiment object
                        const experiment = {
                            session_id: data.sessionId,
                            run_name: data.sessionId.substring(0, 8) + '...',
                        };
                        this.createOrShowGraphTab(experiment as any);
                    }
                    break;
            }
        });

        // Set up message forwarding for lessons
        this._setupLessonsMessageForwarding(panel);

        // Send theme info
        this._sendThemeToPanel(panel);
        vscode.window.onDidChangeActiveColorTheme(() => {
            this._sendThemeToPanel(panel);
        });
    }

    private _setupLessonsMessageForwarding(panel: vscode.WebviewPanel): void {
        if (!this._pythonClient) {
            console.warn('[GraphTabProvider] No Python client available for lessons message forwarding');
            return;
        }

        const messageHandler = (msg: any) => {
            // Forward lessons_list messages to the lessons panel
            if (msg.type === 'lessons_list') {
                panel.webview.postMessage(msg);
            }
        };

        this._pythonClient.onMessage(messageHandler);

        // Clean up when panel is disposed
        panel.onDidDispose(() => {
            this._pythonClient?.removeMessageListener(messageHandler);
        });
    }

    private _setupServerMessageForwarding(panel: vscode.WebviewPanel, sessionId: string): void {
        if (!this._pythonClient) {
            console.warn('[GraphTabProvider] No Python client available for message forwarding');
            return;
        }

        const messageHandler = (msg: any) => {
            // Forward relevant messages to this specific tab
            if (msg.session_id === sessionId || !msg.session_id) {
                panel.webview.postMessage(msg);
            }
        };

        this._pythonClient.onMessage(messageHandler);

        // Clean up when panel is disposed
        panel.onDidDispose(() => {
            if (this._pythonClient) {
                this._pythonClient.removeMessageListener(messageHandler);
            }
        });
    }

    private _sendThemeToPanel(panel: vscode.WebviewPanel): void {
        const isDark = vscode.window.activeColorTheme.kind === vscode.ColorThemeKind.Dark;
        panel.webview.postMessage({
            type: 'vscode-theme-change',
            payload: {
                theme: isDark ? 'vscode-dark' : 'vscode-light',
            },
        });
    }

    private _getHtmlForWebview(webview: vscode.Webview, sessionId: string): string {
        const path = require('path');
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'dist', 'webview.js'));
        const codiconsUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, '..', 'node_modules', '@vscode/codicons', 'dist', 'codicon.css'));
        
        const templatePath = path.join(
            this._extensionUri.fsPath,
            'src',
            'webview',
            'templates',
            'graphTab.html'
        );

        let html: string;
        try {
            html = fs.readFileSync(templatePath, 'utf8');
        } catch (error) {
            // Fallback to inline HTML if template file doesn't exist yet
            html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Graph Tab</title>
    <link rel="stylesheet" href="{{codiconsUri}}">
    <script>
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
    <div id="graph-tab-root"></div>
    <script>
        const vscode = acquireVsCodeApi();
        window.vscode = vscode;
        window.sessionId = '${sessionId}';
    </script>
    <script src="{{scriptUri}}"></script>
</body>
</html>
            `;
        }

        html = html.replace(/{{scriptUri}}/g, scriptUri.toString());
        html = html.replace(/{{codiconsUri}}/g, codiconsUri.toString());
        html = html.replace(/{{sessionId}}/g, sessionId);
        
        return html;
    }

    private _getHtmlForLessonsWebview(webview: vscode.Webview): string {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'dist', 'webview.js'));
        const codiconsUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, '..', 'node_modules', '@vscode/codicons', 'dist', 'codicon.css'));

        const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Lessons</title>
    <link rel="stylesheet" href="${codiconsUri}">
    <script>
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
    <div id="lessons-root"></div>
    <script>
        const vscode = acquireVsCodeApi();
        window.vscode = vscode;
        window.isLessonsView = true;
    </script>
    <script src="${scriptUri}"></script>
</body>
</html>
        `;

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

    private async _handleOpenDocument(payload: { data: string; fileType: string; mimeType: string; documentKey?: string }, panel: vscode.WebviewPanel): Promise<void> {
        const { data, fileType, documentKey } = payload;

        // Whitelist of file types we'll open with system default app
        const openableTypes = ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'docx', 'xlsx'];
        const shouldOpen = openableTypes.includes(fileType);

        try {
            // Save to temp file
            const tempDir = os.tmpdir();
            const fileName = `ao-preview-${Date.now()}.${fileType}`;
            const tempPath = path.join(tempDir, fileName);

            const buffer = Buffer.from(data, 'base64');
            fs.writeFileSync(tempPath, buffer);

            // Open with system default app if whitelisted
            if (shouldOpen) {
                const uri = vscode.Uri.file(tempPath);
                await vscode.env.openExternal(uri);
            }

            // Send path back to webview
            panel.webview.postMessage({
                type: 'documentOpened',
                payload: { path: tempPath, documentKey }
            });
        } catch (error) {
            console.error('[GraphTabProvider] Failed to open document:', error);
            vscode.window.showErrorMessage(`Failed to open document: ${error}`);
        }
    }


    public async deserializeWebviewPanel(webviewPanel: vscode.WebviewPanel, state: any): Promise<void> {
        // This method is called when VS Code restarts and needs to restore the panel
        
        // Set up the webview again
        webviewPanel.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri,
                vscode.Uri.joinPath(this._extensionUri, '..', 'node_modules')
            ]
        };

        // Restore HTML content (we'll need to get session ID from state)
        const sessionId = state?.sessionId || 'unknown';
        webviewPanel.webview.html = this._getHtmlForWebview(webviewPanel.webview, sessionId);

        // Store panel reference
        this._panels.set(sessionId, webviewPanel);

        // Handle disposal
        webviewPanel.onDidDispose(() => {
            this._panels.delete(sessionId);
        });
    }

    public dispose(): void {
        this._panels.forEach(panel => panel.dispose());
        this._panels.clear();
    }
}