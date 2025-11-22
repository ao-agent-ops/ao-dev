import React from 'react';
import ReactDOM from 'react-dom/client';
import { PreviewPanel } from '../../../shared_components/components/PreviewPanel';
import { App } from './App';
import { GraphTabApp } from './GraphTabApp';
import { RunDetailsModalApp } from './RunDetailsModalApp';
import { NodeEditModalApp } from './NodeEditModalApp';
import './styles.css';

declare global {
  interface Window {
    __PREVIEW_DATA__?: {
      fileName: string;
      fileType: string;
      fileData: string;
    };
  }
}

if (document.getElementById('root')) {
  const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
  const data = window.__PREVIEW_DATA__;
  if (data) {
    root.render(
      <PreviewPanel fileName={data.fileName} fileType={data.fileType} fileData={data.fileData} />
    );
  } else {
    root.render(<App />);
  }
} else if (document.getElementById('graph-tab-root')) {
  // Render GraphTabApp for graph tabs
  const root = ReactDOM.createRoot(document.getElementById('graph-tab-root') as HTMLElement);
  root.render(<GraphTabApp />);
} else if (document.getElementById('run-details-root')) {
  // Render RunDetailsModalApp for run details dialog
  const root = ReactDOM.createRoot(document.getElementById('run-details-root') as HTMLElement);
  root.render(<RunDetailsModalApp />);
} else if (document.getElementById('node-edit-root')) {
  // Render NodeEditModalApp for node edit dialog
  const root = ReactDOM.createRoot(document.getElementById('node-edit-root') as HTMLElement);
  root.render(<NodeEditModalApp />);
}