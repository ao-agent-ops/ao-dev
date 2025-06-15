import * as vscode from 'vscode';
import { GraphViewProvider } from './providers/GraphViewProvider';
import { EditDialogProvider } from './providers/EditDialogProvider';

export function activate(context: vscode.ExtensionContext) {
    console.log('Graph Extension is now active!');

    // Register the webview provider
    const graphViewProvider = new GraphViewProvider(context.extensionUri);
    
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(GraphViewProvider.viewType, graphViewProvider)
    );

    // Register the edit dialog provider
    const editDialogProvider = new EditDialogProvider(context.extensionUri, (value: string) => {
        // This will be set by the GraphViewProvider
        graphViewProvider.handleEditDialogSave(value);
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

export function deactivate() {}