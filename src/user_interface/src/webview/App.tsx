import React, { useState, useEffect } from 'react';
import { GraphView } from './components/GraphView';
import { GraphNode, GraphEdge } from './types';
import { sendReady } from './utils/messaging';
import { useIsVsCodeDarkTheme } from './utils/themeUtils';

declare const vscode: any;

export const App: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'overview' | 'experiments'>('overview');
    const [nodes, setNodes] = useState<GraphNode[]>([]);
    const [edges, setEdges] = useState<GraphEdge[]>([]);

    const isDarkTheme = useIsVsCodeDarkTheme();

    useEffect(() => {
        // Listen for messages from the extension
        const handleMessage = (event: MessageEvent) => {
            const message = event.data;
            console.log('Received message:', message); // Debug log
            switch (message.type) {
                case 'addNode':
                    console.log('Adding node:', message.payload); // Debug log
                    setNodes(prev => [...prev, message.payload]);
                    break;
                case 'setGraph':
                    console.log('Setting graph:', message.payload); // Debug log
                    if (message.payload.nodes) {
                        setNodes(message.payload.nodes);
                    }
                    if (message.payload.edges) {
                        setEdges(message.payload.edges);
                    }
                    break;
            }
        };

        window.addEventListener('message', handleMessage);
        
        // Notify extension that webview is ready
        console.log('Sending ready message'); // Debug log
        sendReady();

        return () => {
            window.removeEventListener('message', handleMessage);
        };
    }, []);

    // Debug log for state changes
    useEffect(() => {
        console.log('Nodes updated:', nodes);
        console.log('Edges updated:', edges);
    }, [nodes, edges]);

    const handleNodeUpdate = (nodeId: string, field: string, value: string) => {
        setNodes(prev => prev.map(node => 
            node.id === nodeId ? { ...node, [field]: value } : node
        ));
    };

    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: isDarkTheme ? "#252525" : "#F0F0F0",
        }}
      >
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid var(--vscode-editorWidget-border)",
          }}
        >
          <button
            onClick={() => setActiveTab("overview")}
            style={{
              padding: "10px 20px",
              border: "none",
              backgroundColor:
                activeTab === "overview"
                  ? "var(--vscode-button-background)"
                  : "transparent",
              color:
                activeTab === "overview"
                  ? "var(--vscode-button-foreground)"
                  : "var(--vscode-editor-foreground)",
              cursor: "pointer",
            }}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab("experiments")}
            style={{
              padding: "10px 20px",
              border: "none",
              backgroundColor:
                activeTab === "experiments"
                  ? "var(--vscode-button-background)"
                  : "transparent",
              color:
                activeTab === "experiments"
                  ? "var(--vscode-button-foreground)"
                  : "var(--vscode-editor-foreground)",
              cursor: "pointer",
            }}
          >
            Experiments
          </button>
        </div>
        <div style={{ flex: 1, overflow: "hidden" }}>
          {activeTab === "overview" ? (           
              <GraphView
                nodes={nodes}
                edges={edges}
                onNodeUpdate={handleNodeUpdate}
              />
          ) : (
            <div style={{ padding: '20px' }}>Experiments tab content goes here</div>
          )}
        </div>
      </div>
    );
};