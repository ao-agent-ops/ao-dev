import * as vscode from 'vscode';
import { GraphViewProvider } from './providers/GraphViewProvider';
import { EditDialogProvider } from './providers/EditDialogProvider';
import { NotesLogTabProvider } from './providers/NotesLogTabProvider';

export function activate(context: vscode.ExtensionContext) {
    // Register the webview provider
    const graphViewProvider = new GraphViewProvider(context.extensionUri);

    const notesLogTabProvider = new NotesLogTabProvider(context.extensionUri);
    graphViewProvider.setNotesLogTabProvider(notesLogTabProvider);

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

    // Register the edit dialog provider
    const editDialogProvider = new EditDialogProvider(context.extensionUri, (value: string, contextObj: { nodeId: string; field: string; session_id?: string }) => {
        graphViewProvider.handleEditDialogSave(value, contextObj);
    });
   
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