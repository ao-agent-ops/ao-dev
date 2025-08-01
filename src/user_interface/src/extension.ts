import * as vscode from 'vscode';
import { GraphViewProvider } from './providers/GraphViewProvider';
import { EditDialogProvider } from './providers/EditDialogProvider';

let editDialogProvider: EditDialogProvider | undefined;

export function activate(context: vscode.ExtensionContext) {
    console.log('Graph Extension is now active!');

    // Register the webview provider
    const graphViewProvider = new GraphViewProvider(context.extensionUri);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(GraphViewProvider.viewType, graphViewProvider)
    );

    // --- Close any orphaned edit dialog panels left open after reload ---
    // VS Code does not expose all webview panels directly, but we can close tabs and also try to dispose panels tracked by our provider
    if ((vscode.window as any).tabGroups) {
        const tabGroups = (vscode.window as any).tabGroups.all;
        for (const group of tabGroups) {
            for (const tab of group.tabs) {
                if (tab.input && tab.input.viewType === EditDialogProvider.viewType) {
                    vscode.window.tabGroups.close(tab).then(() => {},
                        (err) => { console.warn('[EXTENSION] Failed to close tab:', tab.label, err); }
                    );
                }
            }
        }
    }
    // Also close all panels tracked by the previous editDialogProvider instance if it exists
    if (editDialogProvider && typeof editDialogProvider.closeAllPanels === 'function') {
        editDialogProvider.closeAllPanels();
    }

    // Register the edit dialog provider
    editDialogProvider = new EditDialogProvider(
        context.extensionUri,
        (value: string, contextObj: { nodeId: string; field: string; session_id?: string }) => {
            graphViewProvider.handleEditDialogSave(value, contextObj);
        },
        context
    );
    context.subscriptions.push(
        vscode.window.registerWebviewPanelSerializer(EditDialogProvider.viewType, editDialogProvider)
    );

    // Store the edit dialog provider in the graph view provider
    graphViewProvider.setEditDialogProvider(editDialogProvider);

    // Register command to show the graph
    context.subscriptions.push(
        vscode.commands.registerCommand('graphExtension.showGraph', () => {
            vscode.commands.executeCommand('graphExtension.graphView.focus');
        })
    );
}

export function deactivate() {
    if (editDialogProvider) {
        editDialogProvider.closeAllPanels();
    }
}