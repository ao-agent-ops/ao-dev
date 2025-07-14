import React, { useState, useEffect } from 'react';
import { GraphView } from './components/GraphView';
import { ExperimentsView } from './components/ExperimentsView';
import { GraphNode, GraphEdge, GraphData } from './types';
import { sendReady } from './utils/messaging';
import { sendGetGraph } from './utils/messaging';
import { useIsVsCodeDarkTheme } from './utils/themeUtils';

declare const vscode: any;

export const App: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'experiments' | 'experiment-graph'>('experiments');
    interface ProcessInfo {
        session_id: string;
        status: string;
        timestamp?: string;
    }

    const [processes, setProcesses] = useState<ProcessInfo[]>([]);
    const [experimentGraphs, setExperimentGraphs] = useState<Record<string, GraphData>>({});
    const [selectedExperiment, setSelectedExperiment] = useState<ProcessInfo | null>(null);

    const isDarkTheme = useIsVsCodeDarkTheme();

    // Handles all messages from the backend. The extension backend ensures all messages are delivered after the webview is ready.
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            const message = event.data;
            switch (message.type) {
                case 'session_id':
                    // No longer need to track handshake state
                    break;
                case 'graph_update': {
                    const sid = message.session_id;
                    const payload = message.payload;
                    setExperimentGraphs(prev => ({
                        ...prev,
                        [sid]: payload
                    }));
                    break;
                }
                case 'updateNode':
                    if (message.payload) {
                        const { nodeId, field, value, session_id } = message.payload;
                        handleNodeUpdate(nodeId, field, value, session_id);
                    }
                    break;
                case 'experiment_list':
                    setProcesses(message.experiments || []);
                    break;
            }
        };

        window.addEventListener('message', handleMessage);
        sendReady(); // Notify extension backend that the webview is ready
        return () => {
            window.removeEventListener('message', handleMessage);
        };
    }, []);

    const handleNodeUpdate = (nodeId: string, field: string, value: string, sessionId?: string) => {
        if (sessionId) {
            if (field === 'input') {
                vscode.postMessage({
                    type: 'edit_input',
                    session_id: sessionId,
                    node_id: nodeId,
                    value
                });
            } else if (field === 'output') {
                vscode.postMessage({
                    type: 'edit_output',
                    session_id: sessionId,
                    node_id: nodeId,
                    value
                });
            } else {
                vscode.postMessage({
                    type: 'updateNode',
                    session_id: sessionId,
                    nodeId,
                    field,
                    value
                });
            }
        }
    };

    const handleExperimentCardClick = (process: ProcessInfo) => {
        setSelectedExperiment(process);
        setActiveTab('experiment-graph');
        // Request the graph for this experiment from the backend
        sendGetGraph(process.session_id);
    };

    const runningExperiments = processes.filter(p => p.status === 'running');
    const finishedExperiments = processes.filter(p => p.status === 'finished');

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
          {activeTab === 'experiment-graph' && selectedExperiment && (
            <button
              onClick={() => setActiveTab('experiment-graph')}
              style={{
                padding: "10px 20px",
                border: "none",
                backgroundColor: "var(--vscode-button-background)",
                color: "var(--vscode-button-foreground)",
                cursor: "pointer",
              }}
            >
              Experiment {selectedExperiment.session_id.substring(0, 8)}...
            </button>
          )}
        </div>
        <div style={{ flex: 1, overflow: "hidden" }}>
          {activeTab === 'experiments' ? (
            <ExperimentsView runningProcesses={runningExperiments} finishedProcesses={finishedExperiments} onCardClick={handleExperimentCardClick} />
          ) : activeTab === 'experiment-graph' && selectedExperiment ? (
            (() => {
                const sessionId = selectedExperiment.session_id;
                const graphData = experimentGraphs[sessionId];
                return (
                    <GraphView
                        nodes={graphData?.nodes || []}
                        edges={graphData?.edges || []}
                        onNodeUpdate={handleNodeUpdate}
                        session_id={sessionId}
                        experiment={selectedExperiment}
                    />
                );
            })()
          ) : null}
        </div>
      </div>
    );
};