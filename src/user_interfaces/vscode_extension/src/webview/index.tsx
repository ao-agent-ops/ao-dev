import React from 'react';
import ReactDOM from 'react-dom/client';
import { PreviewPanel } from '../../../shared_components/components/PreviewPanel';
import { App } from './App';
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
}