import React, { useState, useEffect, useCallback } from 'react';
import { GraphView } from './components/GraphView';
import { ExperimentsView } from './components/ExperimentsView';
import { GraphNode, GraphEdge, GraphData } from './types';
import { sendReady } from './utils/messaging';
import { useIsVsCodeDarkTheme } from './utils/themeUtils';

declare const vscode: any;

const exampleGraph: GraphData = {
  nodes: [
    { id: '1', input: 'User input data', output: 'Processed user data', codeLocation: 'file.py:15', label: 'User Input Handler', border_color: '#ff3232' },
    { id: '2', input: 'Processed user data', output: 'Validated data', codeLocation: 'file.py:42', label: 'Data Validator', border_color: '#00c542' },
    { id: '3', input: 'Validated data', output: 'Database query', codeLocation: 'file.py:78', label: 'Query Builder', border_color: '#ffba0c' },
    { id: '4', input: 'Database query', output: 'Query results', codeLocation: 'file.py:23', label: 'Query Executor', border_color: '#ffba0c' },
    { id: '5', input: 'Query results', output: 'Formatted response', codeLocation: 'file.py:56', label: 'Response Formatter', border_color: '#00c542' },
    { id: '6', input: 'Validated data', output: 'Cache key', codeLocation: 'file.py:12', label: 'Cache Key Generator', border_color: '#ff3232' },
    { id: '7', input: 'Cache key', output: 'Cache status', codeLocation: 'file.py:34', label: 'Cache Manager', border_color: '#00c542' },
  ],
  edges: [
    { id: 'e1-2', source: '1', target: '2' },
    { id: 'e2-3', source: '2', target: '3' },
    { id: 'e3-4', source: '3', target: '4' },
    { id: 'e4-5', source: '4', target: '5' },
    { id: 'e2-6', source: '2', target: '6' },
    { id: 'e6-7', source: '6', target: '7' },
    { id: 'e7-5', source: '7', target: '5' },
  ],
};

export const App: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'overview' | 'experiments' | 'experiment-graph'>('overview');
    const [nodes, setNodes] = useState<GraphNode[]>([]);
    const [edges, setEdges] = useState<GraphEdge[]>([]);
    interface ProcessInfo {
        pid: number;
        script_name: string;
        session_id: string;
        status: string;
        role?: string;
        graph?: GraphData;
        timestamp?: string;
    }

    const [processes, setProcesses] = useState<ProcessInfo[]>([]);
    const [experimentGraphs, setExperimentGraphs] = useState<Record<string, GraphData>>({});
    const [selectedExperiment, setSelectedExperiment] = useState<ProcessInfo | null>(null);

    const isDarkTheme = useIsVsCodeDarkTheme();

    const handleNodeUpdate = useCallback((nodeId: string, field: string, value: string) => {
        // If in experiment-graph tab, update the selected experiment's graph
        if (activeTab === 'experiment-graph' && selectedExperiment) {
            const sessionId = selectedExperiment.session_id;
            setExperimentGraphs(prev => {
                const prevGraph = prev[sessionId];
                if (!prevGraph) {
                    console.warn(`[App] No graph found for session: ${sessionId}`);
                    return prev;
                }
                const updatedNodes = prevGraph.nodes.map(node =>
                    node.id === nodeId ? { ...node, [field]: value } : node
                );
                const updatedGraph = { ...prevGraph, nodes: updatedNodes };
                
                // Send update to backend
                vscode.postMessage({
                    type: 'updateNode',
                    session_id: sessionId,
                    nodeId,
                    field,
                    value
                });
                return { ...prev, [sessionId]: updatedGraph };
            });
        } else {
            // Overview graph (legacy, keep for now)
            setNodes(prev => prev.map(node =>
                node.id === nodeId ? { ...node, [field]: value } : node
            ));
        }
    }, [activeTab, selectedExperiment]);

    useEffect(() => {
        // Listen for messages from the extension
        const handleMessage = (event: MessageEvent) => {
            const message = event.data;
            switch (message.type) {
                case 'addNode':
                    setNodes(prev => [...prev, message.payload]);
                    break;
                case 'setGraph':
                    if (message.payload.nodes) {
                        setNodes(message.payload.nodes);
                    }
                    if (message.payload.edges) {
                        setEdges(message.payload.edges);
                    }
                    break;
                case 'updateNode':
                    // Handle node update from extension's EditDialog
                    if (message.payload) {
                        const { nodeId, field, value } = message.payload;
                        handleNodeUpdate(nodeId, field, value);
                    }
                    break;
                case 'process_list':
                    setProcesses(message.processes || []);
                    // Build experimentGraphs map
                    const graphMap: Record<string, GraphData> = {};
                    (message.processes || []).forEach((proc: ProcessInfo) => {
                        if (proc.session_id && proc.graph) {
                            graphMap[proc.session_id] = proc.graph;
                        }
                    });
                    setExperimentGraphs(graphMap);
                    break;
            }
        };

        window.addEventListener('message', handleMessage);
        
        // Notify extension that webview is ready
        sendReady();

        return () => {
            window.removeEventListener('message', handleMessage);
        };
    }, [handleNodeUpdate]);



    // Filter for shim-control only
    const shimControlProcesses = processes.filter(p => p.role === 'shim-control');
    const runningProcesses = shimControlProcesses.filter(p => p.status === 'running');
    const finishedProcesses = shimControlProcesses.filter(p => p.status === 'finished');

    const handleExperimentCardClick = (process: ProcessInfo) => {
        setSelectedExperiment(process);
        setActiveTab('experiment-graph');
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
              {selectedExperiment.script_name}
            </button>
          )}
        </div>
        <div style={{ flex: 1, overflow: "hidden" }}>
          {activeTab === "overview" ? (           
              <GraphView
                nodes={nodes}
                edges={edges}
                onNodeUpdate={handleNodeUpdate}
              />
          ) : activeTab === "experiments" ? (
            <ExperimentsView runningProcesses={runningProcesses} finishedProcesses={finishedProcesses} onCardClick={handleExperimentCardClick} />
          ) : activeTab === 'experiment-graph' && selectedExperiment ? (
            <GraphView
              nodes={experimentGraphs[selectedExperiment.session_id]?.nodes || []}
              edges={experimentGraphs[selectedExperiment.session_id]?.edges || []}
              onNodeUpdate={handleNodeUpdate}
              session_id={selectedExperiment.session_id}
            />
          ) : null}
        </div>
      </div>
    );
};