import * as path from 'path';
import { openPreviewWebview } from '../webview/openPreviewWebview';
import * as vscode from 'vscode';
import { fileToBase64, getIconByExtension } from '../webview/utils/editDialog';


export class EditDialogProvider implements vscode.WebviewPanelSerializer {
    public static readonly viewType = 'graphExtension.editDialog';
    private _panels: Set<vscode.WebviewPanel> = new Set();
    private _context?: vscode.ExtensionContext;
    private static readonly DIALOG_CONTEXT_KEY = 'editDialog.context';

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _onSave: (value: string, context: { nodeId: string; field: string; session_id?: string }) => void,
        context?: vscode.ExtensionContext
    ) {
        this._context = context;
    }
    public closeAllPanels() {
        for (const panel of this._panels) {
            try {
                panel.dispose();
            } catch (e) {
                console.warn('Error disposing panel:', e);
            }
        }
        this._panels.clear();
    }

    public async show(title: string, value: string, context: { nodeId: string; field: string; session_id?: string; attachments?: any }) {
        // Clean up disposed panels from the set
        for (const panel of Array.from(this._panels)) {
            let disposed = false;
            try {
                // Accessing .title or .webview on a disposed panel may throw
                void panel.title;
                void panel.webview;
            } catch (e) {
                disposed = true;
            }
            if (disposed) {
                this._panels.delete(panel);
            }
        }
        // Check if a panel with this title already exists and is not disposed
        for (const panel of this._panels) {
            let valid = true;
            try {
                void panel.title;
                void panel.webview;
            } catch (e) {
                valid = false;
            }
            if (valid && panel.title === title) {
                panel.reveal(vscode.ViewColumn.One);
                panel.webview.postMessage({ type: 'setValue', value });
                // Update context in case it's different
                (panel as any)._editContext = context;
                return;
            }
        }

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

        (panel as any)._editContext = context;
        this._panels.add(panel);
        panel.webview.html = this._getHtmlForWebview(panel.webview, value, context);
        // Persist the dialog context (including attachments)
        if (this._context) {
            await this._context.workspaceState.update(EditDialogProvider.DIALOG_CONTEXT_KEY, context);
        }

        // Handle messages from the webview
        panel.webview.onDidReceiveMessage(
            message => {
                switch (message.type) {
                    case 'save': {
                        const ctx = (panel as any)._editContext;
                        this._onSave(message.value, ctx);
                        panel.dispose();
                        break;
                    }
                    case 'cancel':
                        panel.dispose();
                        break;
                    case 'openAttachment': {
                        const ctx = (panel as any)._editContext;
                        const attachments = ctx && ctx.attachments ? ctx.attachments : [];
                        const idx = message.index;
                        if (attachments[idx]) {
                            const filePath = attachments[idx][1];
                            const ext = path.extname(filePath).toLowerCase();
                            if (ext === '.pdf' || ext === '.docx') {
                                fileToBase64(filePath).then(base64 => {
                                    openPreviewWebview(
                                        attachments[idx][0],
                                        ext.replace('.', ''),
                                        base64
                                    );
                                }).catch(err => {
                                    vscode.window.showErrorMessage('Error reading file: ' + err.message);
                                });
                            } else {
                                vscode.commands.executeCommand('vscode.open', vscode.Uri.file(filePath));
                            }
                        } else {
                            console.warn('[EditDialogProvider] Attachment index not found:', idx, attachments);
                        }
                        break;
                    }
                }
            },
            null
        );

        // Clean up when the panel is disposed
        panel.onDidDispose(
            () => {
                this._panels.delete(panel);
            },
            null
        );
    }

    public async deserializeWebviewPanel(webviewPanel: vscode.WebviewPanel, state: any) {
        // On reload, immediately dispose any orphaned edit dialog panels
        webviewPanel.dispose();
    }

    private _getHtmlForWebview(webview: vscode.Webview, initialValue: string, context?: any) {

        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'dist', 'editDialog.js'));

        // Use the context received by argument, not the one from the webview
        let attachmentsHtml = '';
        const attachments = context && context.attachments ? context.attachments : [];
        const pdfIconUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'src', 'webview', 'assets', 'pdf-file-icon.png')
        ).toString();
        if (attachments.length > 0) {
            attachmentsHtml = `<div class="attachments-list"><strong>Attachments:</strong><div class="attachments-row">` +
                attachments.map((a: [string, string], idx: number) => {
                    const icon = getIconByExtension(a[0], pdfIconUri);
                    return `<div class="attachment-item">
                        <span class="attachment-icon">${icon}</span>
                        <a href="#" onclick="openAttachment(${idx});return false;" class="attachment-link">${a[0]}</a>
                        <button class="attachment-remove" title="Remove" onclick="removeAttachment(${idx})">×</button>
                    </div>`;
                }).join('') +
                `</div></div>`;
        }

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
                        height: calc(93vh - 40px);
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
                        margin-bottom: 2px;
                    }
                    .attachments-list {
                        background-color: var(--vscode-input-background);
                        color: var(--vscode-input-foreground);
                        border: 1px solid var(--vscode-input-border);
                        border-radius: 4px;
                        padding: 12px 12px 8px 12px;
                        margin-bottom: 8px;
                        font-size: var(--vscode-editor-font-size);
                    }
                    .attachments-row {
                        display: flex;
                        flex-direction: row;
                        gap: 6px;
                        margin-top: 4px;
                        padding-bottom: 10px;
                        overflow-x: auto;
                        overflow-y: hidden;
                        white-space: nowrap;
                        align-items: stretch;
                        height: 38px;
                        scrollbar-width: thin;
                    }
                    @media (min-width: 900px) {
                        .attachments-row {
                            grid-template-columns: repeat(5, 1fr);
                        }
                    }
                    @media (min-width: 1200px) {
                        .attachments-row {
                            grid-template-columns: repeat(6, 1fr);
                        }
                    }
                    .attachment-item {
                        display: flex;
                        align-items: center;
                        background: #545454;
                        color: #fff;
                        border: 1px solid var(--vscode-input-border);
                        border-radius: 5px;
                        padding: 2px 6px 2px 4px;
                        margin-bottom: 0;
                        min-width: 160px;
                        max-width: 240px;
                        box-sizing: border-box;
                        position: relative;
                        gap: 5px;
                        font-size: 12px;
                        height: 28px;
                    }
                    .attachment-item * {
                        color: #fff !important;
                    }
                    .attachment-icon {
                        font-size: 20px;
                        margin-right: 4px;
                        display: flex;
                        align-items: center;                    
                        justify-content: center;
                        height: 24px;
                        width: 24px;
                    }
                    .attachment-icon img {
                        width: 20px;
                        height: 20px;
                        display: block;
                        margin: 0 auto;
                        vertical-align: middle;
                        padding: 0;
                    }
                    .attachment-link {
                        color: var(--vscode-textLink-foreground, #3794ff);
                        text-decoration: none;
                        font-size: 15px;
                        flex: 1;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                        max-width: 170px;
                    }
                    .attachment-link:hover {
                        text-decoration: underline;
                    }
                    .attachment-remove {
                        background: transparent;
                        border: none;
                        color: var(--vscode-editor-foreground, #fff);        
                        font-size: 16px;
                        cursor: pointer;
                        margin-left: 4px;
                        padding: 0 2px;
                        border-radius: 2px;
                        transition: background 0.15s;
                    }
                    .attachment-remove:hover {
                        background: var(--vscode-button-secondaryBackground, #444);
                        color: var(--vscode-button-secondaryForeground, #fff);
                    }
                    .button-container {
                        margin-top: 8px;
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
                    <textarea id="editor">${initialValue} some code here</textarea>
                    ${attachmentsHtml}
                </div>
                <div class="button-container">
                    <button class="cancel-button" onclick="cancel()">Cancel</button>
                    <button class="save-button" onclick="save()">Save</button>
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

                    function removeAttachment(idx) {
                        vscode.postMessage({
                            type: 'removeAttachment',
                            index: idx
                        });
                    }

                    function openAttachment(idx) {
                        console.log('[Webview] openAttachment called for idx:', idx);
                        vscode.postMessage({
                            type: 'openAttachment',
                            index: idx
                        });
                    }
                </script>
            </body>
            </html>`;
    }
} 