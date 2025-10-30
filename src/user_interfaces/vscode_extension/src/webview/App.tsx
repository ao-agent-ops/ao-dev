import React, { useState, useEffect } from 'react';
import { WorkflowRunDetailsPanel } from '../../../shared_components/components/experiment/WorkflowRunDetailsPanel';
import { GraphView } from '../../../shared_components/components/graph/GraphView';
import { ExperimentsView } from '../../../shared_components/components/experiment/ExperimentsView';
import { GraphNode, GraphEdge, GraphData, ProcessInfo } from '../../../shared_components/types';
import { sendReady, sendGetGraph, sendMessage } from '../../../shared_components/utils/messaging';
import { MessageSender } from '../../../shared_components/types/MessageSender';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';
import { useLocalStorage } from '../../../shared_components/hooks/useLocalStorage';


// Add global type augmentation for window.vscode
declare global {
  interface Window {
    vscode?: {
      postMessage: (message: any) => void;
    };
  }
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useLocalStorage<"experiments" | "experiment-graph">("activeTab", "experiments");
  const [processes, setProcesses] = useLocalStorage<ProcessInfo[]>("experiments", []);
  const [selectedExperiment, setSelectedExperiment] = useLocalStorage<ProcessInfo | null>("selectedExperiment", null);
  const [allGraphs, setAllGraphs] = useLocalStorage<Record<string, GraphData>>("graphs", {});
  const [showDetailsPanel, setShowDetailsPanel] = useState(false);
  const isDarkTheme = useIsVsCodeDarkTheme();

  // Create MessageSender for VS Code environment
  const messageSender: MessageSender = {
    send: (message: any) => {
      if (window.vscode) {
        window.vscode.postMessage(message);
      }
    }
  };
  // Listen for event to open detail panel
  useEffect(() => {
    const handler = () => setShowDetailsPanel(true);
    window.addEventListener('open-details-panel', handler);
    return () => window.removeEventListener('open-details-panel', handler);
  }, []);

  // Listen for backend messages and update state
  useEffect(() => {   
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;
      switch (message.type) {
        case "session_id":
          break;
        case "configUpdate":
          // Config changed - forward to config bridge
          console.log('Config update received:', message.detail);
          window.dispatchEvent(new CustomEvent('configUpdate', { detail: message.detail }));
          break;
        case "graph_update": {
          const sid = message.session_id;
          const payload = message.payload;         
          setAllGraphs((prev) => ({
            ...prev,
            [sid]: payload,
          }));
          break;
        }
        case "color_preview_update": {
          const sid = message.session_id;
          const color_preview = message.color_preview;
          console.log(`Color preview update for ${sid}:`, color_preview);
          setProcesses((prev) => {
            const updated = prev.map(process => 
              process.session_id === sid 
                ? { ...process, color_preview }
                : process
            );
            console.log('Updated processes:', updated);
            return updated;
          });
          break;
        }
        case "updateNode":
          if (message.payload) {
            const { nodeId, field, value, session_id } = message.payload;
            handleNodeUpdate(nodeId, field, value, session_id);
          }
          break;
        case "experiment_list":
          setProcesses(message.experiments || []);
          localStorage.setItem(
            "experiments",
            JSON.stringify(message.experiments || [])
          );
          // No longer automatically loading all graphs - only load when user clicks
          // Clear any cached graphs for experiments that are no longer in the list
          const currentSessionIds = new Set((message.experiments || []).map((exp: ProcessInfo) => exp.session_id));
          setAllGraphs((prev) => {
            const newGraphs: Record<string, GraphData> = {};
            Object.keys(prev).forEach(sessionId => {
              if (currentSessionIds.has(sessionId)) {
                newGraphs[sessionId] = prev[sessionId];
              }
            });
            return newGraphs;
          });
          break;
      }
    };
    window.addEventListener('message', handleMessage);
    sendReady();
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  const handleNodeUpdate = (
    nodeId: string,
    field: string,
    value: string,
    sessionId?: string,
    attachments?: any
  ) => {
    if (sessionId && window.vscode) {
      const baseMsg = {
        session_id: sessionId,
        node_id: nodeId,
        value,
        ...(attachments && { attachments }),
      };
      if (field === "input") {
        window.vscode.postMessage({ type: "edit_input", ...baseMsg });
      } else if (field === "output") {
        window.vscode.postMessage({ type: "edit_output", ...baseMsg });
      } else {
        window.vscode.postMessage({
          type: "updateNode",
          session_id: sessionId,
          nodeId,
          field,
          value,
          ...(attachments && { attachments }),
        });
      }
    }
  };

  const handleExperimentCardClick = (process: ProcessInfo) => {
    setSelectedExperiment(process);
    setActiveTab('experiment-graph');
    localStorage.setItem("selectedExperiment", JSON.stringify(process));
    localStorage.setItem("activeTab", 'experiment-graph');
    sendGetGraph(process.session_id);
  };

  // Use experiments in the order sent by server (already sorted by name ascending)
  const sortedProcesses = processes;
  
  const runningExperiments = sortedProcesses.filter(p => p.status === 'running');
  const finishedExperiments = sortedProcesses.filter(p => p.status === 'finished');

  useEffect(() => {
    if (selectedExperiment && !allGraphs[selectedExperiment.session_id]) {
      sendGetGraph(selectedExperiment.session_id);
    }
  }, [selectedExperiment, allGraphs]);

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
        {activeTab === "experiment-graph" && selectedExperiment && (
          <button
            onClick={() => setActiveTab("experiment-graph")}
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
      <div
        style={
          showDetailsPanel
            ? {
                flex: 1,
                overflow: "hidden",
                background: isDarkTheme ? "#252525" : "#F0F0F0",
              }
            : { flex: 1, overflow: "hidden" }
        }
      >
        {activeTab === "experiments" ? (
          <ExperimentsView
            runningProcesses={runningExperiments}
            finishedProcesses={finishedExperiments}
            onCardClick={handleExperimentCardClick}
            isDarkTheme={isDarkTheme}
          />
        ) : activeTab === "experiment-graph" && selectedExperiment && !showDetailsPanel ? (
          <GraphView
            nodes={allGraphs[selectedExperiment.session_id]?.nodes || []}
            edges={allGraphs[selectedExperiment.session_id]?.edges || []}
            onNodeUpdate={(nodeId, field, value) => {
              const nodes = allGraphs[selectedExperiment.session_id]?.nodes || [];
              const node = nodes.find((n: any) => n.id === nodeId);
              const attachments = node?.attachments || undefined;
              handleNodeUpdate(
                nodeId,
                field,
                value,
                selectedExperiment.session_id,
                attachments
              );
            }}
            session_id={selectedExperiment.session_id}
            experiment={selectedExperiment}
            messageSender={messageSender}
            isDarkTheme={isDarkTheme}
          />
        ) : activeTab === "experiment-graph" && selectedExperiment && showDetailsPanel ? (
          <WorkflowRunDetailsPanel
            runName={selectedExperiment.title || ''}
            result={selectedExperiment.success || ''}
            notes={selectedExperiment.notes || ''}
            log={selectedExperiment.log || ''}
            onOpenInTab={() => {}}
            onBack={() => setShowDetailsPanel(false)}
            sessionId={selectedExperiment.session_id}
          />
        ) : null}
      </div>
    </div>
  );
};