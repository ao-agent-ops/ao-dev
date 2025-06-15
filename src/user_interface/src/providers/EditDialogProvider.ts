import * as vscode from 'vscode';

export class EditDialogProvider implements vscode.WebviewPanelSerializer {
    public static readonly viewType = 'graphExtension.editDialog';
    private _panels: Map<string, vscode.WebviewPanel> = new Map();

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _onSave: (value: string) => void
    ) {}

    public async show(title: string, value: string) {
        // Check if a panel with this title already exists
        for (const [_, panel] of this._panels) {
            if (panel.title === title) {
                panel.reveal(vscode.ViewColumn.One);
                panel.webview.postMessage({ type: 'setValue', value });
                return;
            }
        }

        // Create a unique identifier for this panel
        const panelId = `${title}-${Date.now()}`;

        // Create a new panel
        const panel = vscode.window.createWebviewPanel(
            EditDialogProvider.viewType,
            title,
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [this._extensionUri]
            }
        );

        this._panels.set(panelId, panel);
        panel.webview.html = this._getHtmlForWebview(panel.webview, value);

        // Handle messages from the webview
        panel.webview.onDidReceiveMessage(
            message => {
                switch (message.type) {
                    case 'save':
                        this._onSave(message.value);
                        panel.dispose();
                        break;
                    case 'cancel':
                        panel.dispose();
                        break;
                }
            },
            null
        );

        // Clean up when the panel is disposed
        panel.onDidDispose(
            () => {
                this._panels.delete(panelId);
            },
            null
        );
    }

    public async deserializeWebviewPanel(webviewPanel: vscode.WebviewPanel, state: any) {
        const panelId = `${state.title}-${Date.now()}`;
        this._panels.set(panelId, webviewPanel);
        webviewPanel.webview.html = this._getHtmlForWebview(webviewPanel.webview, state?.value || '');
    }

    private _getHtmlForWebview(webview: vscode.Webview, initialValue: string) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'dist', 'editDialog.js'));

        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Edit Dialog</title>
                <style>
                    body {
                        padding: 20px;
                        background-color: var(--vscode-editor-background);
                        color: var(--vscode-editor-foreground);
                        font-family: var(--vscode-font-family);
                    }
                    .container {
                        display: flex;
                        flex-direction: column;
                        height: calc(100vh - 40px);
                        gap: 16px;
                    }
                    textarea {
                        flex: 1;
                        padding: 12px;
                        background-color: var(--vscode-input-background);
                        color: var(--vscode-input-foreground);
                        border: 1px solid var(--vscode-input-border);
                        border-radius: 4px;
                        font-family: var(--vscode-editor-font-family);
                        font-size: var(--vscode-editor-font-size);
                        line-height: 1.5;
                        resize: none;
                    }
                    .button-container {
                        display: flex;
                        justify-content: flex-end;
                        gap: 8px;
                    }
                    button {
                        padding: 8px 16px;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 13px;
                    }
                    .cancel-button {
                        background-color: var(--vscode-button-secondaryBackground);
                        color: var(--vscode-button-secondaryForeground);
                    }
                    .save-button {
                        background-color: var(--vscode-button-background);
                        color: var(--vscode-button-foreground);
                    }
                    button:hover {
                        opacity: 0.9;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <textarea id="editor">${initialValue}</textarea>
                    <div class="button-container">
                        <button class="cancel-button" onclick="cancel()">Cancel</button>
                        <button class="save-button" onclick="save()">Save</button>
                    </div>
                </div>
                <script>
                    const vscode = acquireVsCodeApi();
                    const editor = document.getElementById('editor');
                    
                    // Handle messages from the extension
                    window.addEventListener('message', event => {
                        const message = event.data;
                        switch (message.type) {
                            case 'setValue':
                                editor.value = message.value;
                                break;
                        }
                    });

                    function save() {
                        vscode.postMessage({
                            type: 'save',
                            value: editor.value
                        });
                    }

                    function cancel() {
                        vscode.postMessage({
                            type: 'cancel'
                        });
                    }
                </script>
            </body>
            </html>`;
    }
} 