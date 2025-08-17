import * as path from 'path';
import { openPreviewWebview } from '../webview/openPreviewWebview';
import * as vscode from 'vscode';
import { fileToBase64 } from '../webview/utils/editDialog';
import { generateAttachmentsHtml } from '../webview/utils/attachmentHtml';
import * as fs from 'fs';


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

    public async show(title: string, value: string, context: { nodeId: string; field: string; session_id?: string; attachments?: any }) {
        // Check if a panel with this title already exists
        for (const panel of this._panels) {
            if (panel.title === title) {
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
                                        base64,
                                        ctx.nodeId,
                                        ctx.session_id
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
        // Read the HTML template from the templates folder
        const templatePath = path.join(
            this._extensionUri.fsPath,
            'src',
            'webview',
            'templates',
            'editDialog.html'
        );
        let html = fs.readFileSync(templatePath, 'utf8');

        // Prepare dynamic values

        const attachments = context && context.attachments ? context.attachments : [];
        const pdfIconUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'src', 'webview', 'assets', 'pdf-file-icon.png')
        ).toString();
        const attachmentsHtml = generateAttachmentsHtml(attachments, pdfIconUri);

        // Replace placeholders in the template
        html = html.replace('{{initialValue}}', initialValue || '');
        html = html.replace('{{attachmentsHtml}}', attachmentsHtml);

        return html;
    }
} 