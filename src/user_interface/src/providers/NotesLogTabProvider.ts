
import * as path from 'path';
import * as fs from 'fs';
import * as vscode from 'vscode';

export class NotesLogTabProvider {
  private _panels: Set<vscode.WebviewPanel> = new Set();
  private readonly _extensionUri: vscode.Uri;

  constructor(extensionUri: vscode.Uri) {
    this._extensionUri = extensionUri;
  }

  public openNotesTab(payload: { runName: string; result: string; notes: string }) {
    const title = `Notes: ${payload.runName}`;
    for (const panel of this._panels) {
      if (panel.title === title) {
        panel.reveal(vscode.ViewColumn.One);
        return;
      }
    }
    const panel = vscode.window.createWebviewPanel(
      'workflowExtension.notesTab',
      title,
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    this._panels.add(panel);
    panel.webview.html = this._getNotesHtml(panel.webview, payload);
    panel.onDidDispose(() => {
      this._panels.delete(panel);
    });
  }

  public openLogTab(payload: { runName: string; result: string; log: string }) {
    const title = `Log: ${payload.runName}`;
    for (const panel of this._panels) {
      if (panel.title === title) {
        panel.reveal(vscode.ViewColumn.One);
        panel.webview.html = this._getLogHtml(panel.webview, payload);
        return;
      }
    }
    const panel = vscode.window.createWebviewPanel(
      'workflowExtension.logTab',
      title,
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    panel.webview.html = this._getLogHtml(panel.webview, payload);
    this._panels.add(panel);
    panel.onDidDispose(() => {
      this._panels.delete(panel);
    });
  }

  private _getNotesHtml(webview: vscode.Webview, payload: { runName: string; result: string; notes: string }) {
    const templatePath = path.join(
      this._extensionUri.fsPath,
      'src',
      'webview',
      'templates',
      'notesView.html'
    );
    let html = fs.readFileSync(templatePath, 'utf8');
    html = html.replace(/{{notes}}/g, payload.notes || '');
    return html;
  }

  private _getLogHtml(webview: vscode.Webview, payload: { runName: string; result: string; log: string }) {
    const templatePath = path.join(
      this._extensionUri.fsPath,
      'src',
      'webview',
      'templates',
      'logView.html'
    );
    let html = fs.readFileSync(templatePath, 'utf8');
    html = html.replace(/{{logs}}/g, payload.log || '');
    return html;
  }
}