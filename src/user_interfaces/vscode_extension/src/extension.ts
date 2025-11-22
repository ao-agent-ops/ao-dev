import * as vscode from 'vscode';
import { SidebarProvider } from './providers/SidebarProvider';
import { GraphTabProvider } from './providers/GraphTabProvider';

export function activate(context: vscode.ExtensionContext) {
    // Register the sidebar webview provider
    const sidebarProvider = new SidebarProvider(context.extensionUri);

    // Register the graph tab provider
    const graphTabProvider = new GraphTabProvider(context.extensionUri);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(SidebarProvider.viewType, sidebarProvider)
    );

    context.subscriptions.push(
        vscode.window.registerWebviewPanelSerializer(GraphTabProvider.viewType, graphTabProvider)
    );

    // Connect sidebar and graph tab providers
    sidebarProvider.setGraphTabProvider(graphTabProvider);

    // Register command to show the graph
    context.subscriptions.push(
        vscode.commands.registerCommand('graphExtension.showGraph', () => {
            vscode.commands.executeCommand('graphExtension.graphView.focus');
        })
    );
}