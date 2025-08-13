import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

// Dictionary of open panels by absolute path
const previewPanels: Record<string, vscode.WebviewPanel> = {};

export function openPreviewWebview(fileName: string, fileType: string, fileData: string) {
  // Use the file name as a unique key (you can use the absolute path if you prefer)
  const key = fileName;
  const activeColumn = vscode.window.activeTextEditor?.viewColumn || vscode.ViewColumn.One;

  if (previewPanels[key]) {
    // If the panel already exists, update its content and reveal it
    previewPanels[key].reveal(activeColumn);
  } else {
    // create a new panel
    const panel = vscode.window.createWebviewPanel(
      'attachmentPreview',
      `Preview: ${fileName}`,
      activeColumn,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );
    panel.webview.html = getPreviewHtml(panel, fileName, fileType, fileData);
    previewPanels[key] = panel;
    panel.onDidDispose(() => {
      delete previewPanels[key];
    });
  }
}

function getPreviewHtml(panel: vscode.WebviewPanel, fileName: string, fileType: string, fileData: string) {
  const scriptUri = panel.webview.asWebviewUri(
    vscode.Uri.joinPath(
      vscode.Uri.file(__dirname),
      '..',
      'dist',
      'webview.js'
    )
  );
  const nonce = getNonce();
  const initialData = JSON.stringify({ fileName, fileType, fileData });
  // Read the HTML template
  const templatePath = path.join(
    __dirname,
    '..',
    'src',
    'webview',
    'templates',
    'preview.html.tpl'
  );
  let html = fs.readFileSync(templatePath, 'utf8');
  html = html.replace('{{fileName}}', fileName);
  html = html.replace(/{{scriptUri}}/g, scriptUri.toString());
  html = html.replace(/{{nonce}}/g, nonce);
  html = html.replace('{{initialData}}', initialData);
  return html;
}

function getNonce() {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}
