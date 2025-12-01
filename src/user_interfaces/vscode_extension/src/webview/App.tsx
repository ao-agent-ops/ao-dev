import React, { useEffect, useState } from 'react';
import { ExperimentsView } from '../../../shared_components/components/experiment/ExperimentsView';
import { GraphView } from '../../../shared_components/components/graph/GraphView';
import { WorkflowRunDetailsPanel } from '../../../shared_components/components/experiment/WorkflowRunDetailsPanel';
import { LoginScreen } from './LoginScreen';
import { GraphNode, GraphEdge, GraphData, ProcessInfo } from '../../../shared_components/types';
import { MessageSender } from '../../../shared_components/types/MessageSender';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';


// Add global type augmentation for window.vscode
declare global {
  interface Window {
    vscode?: {
      postMessage: (message: any) => void;
    };
  }
}

export const App: React.FC = () => {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [databaseMode, setDatabaseMode] = useState<'Local' | 'Remote'>('Local');
  const [user, setUser] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'experiments' | 'experiment-graph'>('experiments');
  const [selectedExperiment, setSelectedExperiment] = useState<ProcessInfo | null>(null);
  const [showDetailsPanel, setShowDetailsPanel] = useState(false);
  const [allGraphs, setAllGraphs] = useState<Record<string, GraphData>>({});
  const isDarkTheme = useIsVsCodeDarkTheme();

  // Listen for backend messages and update state
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;
      switch (message.type) {
        case "session_id":
          // Handle initial connection message with database mode
          if (message.database_mode) {
            const mode = message.database_mode === 'local' ? 'Local' : 'Remote';
            setDatabaseMode(mode);
            console.log(`Synchronized database mode to: ${mode}`);
          }
          break;
        case "database_mode_changed":
          // Handle database mode change broadcast from server
          if (message.database_mode) {
            const mode = message.database_mode === 'local' ? 'Local' : 'Remote';
            setDatabaseMode(mode);
            console.log(`Database mode changed by another UI to: ${mode}`);
          }
          break;
        case "authStateChanged":
          // Update user state from auth provider
          console.log('[App] Received authStateChanged:', message.payload);
          if (message.payload?.session) {
            const account = message.payload.session.account;
            const userAvatar = message.payload.userAvatar || 
                              account.picture || 
                              'https://www.gravatar.com/avatar/?d=mp&s=200';
            console.log('[App] Setting user from session:', account, 'avatar:', userAvatar);
            setUser({
              displayName: account.label,
              email: account.label,
              avatarUrl: userAvatar
            });
          } else {
            console.log('[App] Clearing user (no session)');
            setUser(null);
          }
          break;
        case "configUpdate":
          // Config changed - forward to config bridge
          console.log('Config update received:', message.detail);
          window.dispatchEvent(new CustomEvent('configUpdate', { detail: message.detail }));
          break;
        case "graph_update":
          // Graph updates are now handled by individual graph tabs
          break;
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
          // Node updates are now handled by individual graph tabs
          break;
        case "experiment_list":
          setProcesses(message.experiments || []);
          break;
      }
    };
    window.addEventListener('message', handleMessage);
    // Send ready message to VS Code extension
    if (window.vscode) {
      window.vscode.postMessage({ type: 'ready' });
    }
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);


  const handleExperimentCardClick = (process: ProcessInfo) => {
    // Instead of switching tabs in the sidebar, open a new graph tab
    if (window.vscode) {
      window.vscode.postMessage({
        type: 'openGraphTab',
        payload: {
          experiment: process
        }
      });
    }
  };

  const handleDatabaseModeChange = (mode: 'Local' | 'Remote') => {
    // Update local state immediately for responsive UI
    setDatabaseMode(mode);
    
    // Send message to VS Code extension to relay to server
    if (window.vscode) {
      window.vscode.postMessage({
        type: 'setDatabaseMode',
        mode: mode.toLowerCase()
      });
    }
  };

  const handleNodeUpdate = (nodeId: string, field: string, value: string, sessionId: string, attachments?: any) => {
    if (window.vscode) {
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
          type: "update_node",
          ...baseMsg,
          field,
        });
      }
    }
  };

  // Message sender for the Graph components
  const messageSender: MessageSender = {
    send: (message: any) => {
      if (window.vscode) {
        window.vscode.postMessage(message);
      }
    },
  };

  // Use experiments in the order sent by server (already sorted by name ascending)
  // Server already filters by user_id, so no client-side filtering needed
  const sortedProcesses = processes;
  
  // Filter experiments by status - now includes real similarity search results
  const similarExperiments = sortedProcesses.filter(p => p.status === 'similar');
  const runningExperiments = sortedProcesses.filter(p => p.status === 'running');
  const finishedExperiments = sortedProcesses.filter(p => p.status === 'finished');

  // Debug logging for similarity search
  console.log('App.tsx - All processes:', sortedProcesses);
  console.log('App.tsx - Similar experiments:', similarExperiments);
  console.log('App.tsx - Running experiments:', runningExperiments);
  console.log('App.tsx - Finished experiments:', finishedExperiments);


  // Show login screen if user is not authenticated
  if (!user) {
    return (
      <LoginScreen
        onLogin={() => {
          if (window.vscode) {
            window.vscode.postMessage({ type: 'signIn' });
          }
        }}
        isDarkTheme={isDarkTheme}
      />
    );
  }

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
            similarProcesses={similarExperiments}
            runningProcesses={runningExperiments}
            finishedProcesses={finishedExperiments}
            onCardClick={handleExperimentCardClick}
            isDarkTheme={isDarkTheme}
            user={user || undefined}
            onLogin={() => {
              if (window.vscode) {
                window.vscode.postMessage({ type: 'signIn' });
              }
            }}
            onLogout={() => {
              if (window.vscode) {
                window.vscode.postMessage({ type: 'signOut' });
              }
            }}
            showHeader={true}
            onModeChange={handleDatabaseModeChange}
            currentMode={databaseMode}
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
            runName={selectedExperiment.run_name || ''}
            result={selectedExperiment.result || ''}
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