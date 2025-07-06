import { NodeUpdateMessage } from '../types';

declare const vscode: any;

export function sendMessage(message: any) {
    console.log("sendMessage called with:", message);
    vscode.postMessage(message);
}

export function sendNodeUpdate(nodeId: string, field: string, value: string) {
    vscode.postMessage({
        type: 'nodeUpdated',
        payload: { nodeId, field, value }
    });
}

export function sendReady() {
    vscode.postMessage({
        type: 'ready'
    });
}

export function sendNavigateToCode(codeLocation: string) {
    vscode.postMessage({
        type: 'navigateToCode',
        payload: { codeLocation }
    });
}