import * as React from 'react';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import '@react-pdf-viewer/core/lib/styles/index.css';
import mammoth from 'mammoth';

export type PreviewPanelProps = {
  fileName: string;
  fileType: string;
  fileData: Uint8Array | string;
};

export const PreviewPanel: React.FC<PreviewPanelProps> = ({ fileType, fileData }) => {
  const [docxHtml, setDocxHtml] = React.useState<string>('');

  React.useEffect(() => {
    if (fileType === 'docx' && fileData) {
      // fileData can be a base64 string or a Uint8Array
      let arrayBufferPromise: Promise<ArrayBuffer>;
      if (typeof fileData === 'string') {
        // base64 string
        const binary = atob(fileData);
        const len = binary.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
        arrayBufferPromise = Promise.resolve(bytes.buffer as ArrayBuffer);
      } else {
        arrayBufferPromise = Promise.resolve(fileData.buffer as ArrayBuffer);
        arrayBufferPromise = Promise.resolve(fileData.buffer as ArrayBuffer);
      }
      arrayBufferPromise.then(buffer => {
        mammoth.convertToHtml({ arrayBuffer: buffer })
          .then(result => setDocxHtml(result.value))
          .catch(() => setDocxHtml('<div>Error rendering DOCX</div>'));
      });
    }
  }, [fileType, fileData]);

  if (fileType === 'pdf') {
    // fileData must be a base64 string
    let pdfUrl = '';
    if (typeof fileData === 'string') {
      pdfUrl = `data:application/pdf;base64,${fileData}`;
    } else {
      const blob = new Blob([fileData as BlobPart], { type: 'application/pdf' });
      pdfUrl = URL.createObjectURL(blob);
    }
    return (
      <div style={{ height: '100vh' }}>
        <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js">
          <Viewer fileUrl={pdfUrl} />
        </Worker>
      </div>
    );
  }
  if (fileType === 'docx') {
    return (
      <div
        style={{
          background: '#eee',
          minHeight: '100vh',
          width: '100%',
          height: '100vh',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '32px 0',
        }}
      >
        <div
          style={{
            background: '#fff',
            color: '#111',
            padding: '40px 60px',
            borderRadius: 6,
            boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
            minWidth: 700,
            maxWidth: '100%',
            width: 'auto',
            margin: '0 auto',
            fontFamily: 'Segoe UI, Arial, sans-serif',
            fontSize: 16,
            lineHeight: 1.6,
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
          dangerouslySetInnerHTML={{ __html: docxHtml || 'Cargando DOCX...' }}
        />
      </div>
    );
  }
  return <div>No preview available for this file type.</div>;
};
