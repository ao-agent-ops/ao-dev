import * as vscode from 'vscode';
import { EditDialogProvider } from './EditDialogProvider';
import { relative } from 'path';

export class GraphViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'graphExtension.graphView';
    private _view?: vscode.WebviewView;
    private _editDialogProvider?: EditDialogProvider;
    private _pendingEdit?: {
        nodeId: string;
        field: string;
    };

    constructor(private readonly _extensionUri: vscode.Uri) {}

    public setEditDialogProvider(provider: EditDialogProvider): void {
        this._editDialogProvider = provider;
    }

    public handleEditDialogSave(value: string): void {
        if (this._pendingEdit && this._view) {
            this._view.webview.postMessage({
                type: 'nodeUpdated',
                payload: {
                    nodeId: this._pendingEdit.nodeId,
                    field: this._pendingEdit.field,
                    value
                }
            });
            this._pendingEdit = undefined;
        }
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

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
            switch (data.type) {
                case 'nodeUpdated':
                    // Handle node update - forward to backend
                    console.log('Node updated:', data.payload);
                    // Here you would send this to your backend
                    break;
                case 'ready':
                    // Webview is ready, send initial graph data if available
                    this._sendInitialData();
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
                        this._pendingEdit = {
                            nodeId: data.payload.nodeId,
                            field: data.payload.field
                        };
                        this._editDialogProvider.show(
                            `${data.payload.label} ${data.payload.field === 'input' ? 'Input' : 'Output'}`,
                            data.payload.value
                        );
                    }
                    break;
            }
        });
    }

    public addNode(nodeData: any) {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'addNode',
                payload: nodeData
            });
        }
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

    private _sendInitialData() {
        // Send initial graph data to webview
        if (this._view) {
            const baseFilePath = '/Users/ferdi/Downloads/fundraising_crm_tree_src/assistant_codegen/plans/database/db_operations.py';
            
            // Sample data with various node types and connections
            const initialNodes = [
                {
                    id: '1',
                    input: 'User input data',
                    output: 'Processed user data',
                    codeLocation: `${baseFilePath}:15`,
                    label: 'User Input Handler',
                    border_color: '#ff3232' // Red border color
                },
                {
                    id: '2',
                    input: 'Processed user data',
                    output: 'Validated data',
                    codeLocation: `${baseFilePath}:42`,
                    label: 'Data Validator',
                    border_color: '#00c542'
                },
                {
                    id: '3',
                    input: 'Validated data',
                    output: 'Database query',
                    codeLocation: `${baseFilePath}:78`,
                    label: 'Query Builder',
                    border_color: '#ffba0c'
                },
                {
                    id: '4',
                    input: 'Database query',
                    output: 'Query results',
                    codeLocation: `${baseFilePath}:23`,
                    label: 'Query Executor',
                    border_color: '#ffba0c'
                },
                {
                    id: '5',
                    input: 'Query results',
                    output: 'Formatted response',
                    codeLocation: `${baseFilePath}:56`,
                    label: 'Response Formatter',
                    border_color: '#00c542'
                },
                {
                    id: '6',
                    input: 'Validated data',
                    output: 'Cache key',
                    codeLocation: `${baseFilePath}:12`,
                    label: 'Cache Key Generator',
                    border_color: '#ff3232'
                },
                {
                    id: '7',
                    input: 'Cache key',
                    output: 'Cache status',
                    codeLocation: `${baseFilePath}:34`,
                    label: 'Cache Manager',
                    border_color: '#00c542'
                }
            ];

            const initialEdges = [
                { id: 'e1-2', source: '1', target: '2' },
                { id: 'e2-3', source: '2', target: '3' },
                { id: 'e3-4', source: '3', target: '4' },
                { id: 'e4-5', source: '4', target: '5' },
                { id: 'e2-6', source: '2', target: '6' },
                { id: 'e6-7', source: '6', target: '7' },
                { id: 'e7-5', source: '7', target: '5' }
            ];

            this._view.webview.postMessage({
                type: 'setGraph',
                payload: { nodes: initialNodes, edges: initialEdges }
            });
        }
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