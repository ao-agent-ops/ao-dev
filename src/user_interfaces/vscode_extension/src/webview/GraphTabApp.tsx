import React, { useState, useEffect, useRef } from 'react';
import { GraphTabApp as SharedGraphTabApp } from '../../../shared_components/components/GraphTabApp';
import { GraphData, ProcessInfo } from '../../../shared_components/types';
import { MessageSender } from '../../../shared_components/types/MessageSender';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';
import { GraphHeader } from '../../../shared_components/components/graph/GraphHeader';
import { DocumentContextProvider, useDocumentContext } from '../../../shared_components/contexts/DocumentContext';

// Global type augmentation for window.vscode
declare global {
  interface Window {
    vscode?: {
      postMessage: (message: any) => void;
    };
    sessionId?: string;
    isGraphTab?: boolean;
  }
}

// Inner component that uses the document context
const GraphTabAppInner: React.FC = () => {
  const [experiment, setExperiment] = useState<ProcessInfo | null>(null);
  const [experiments, setExperiments] = useState<ProcessInfo[]>([]);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const isDarkTheme = useIsVsCodeDarkTheme();
  const { setDocumentOpened } = useDocumentContext();

  // Override body overflow to allow scrolling
  useEffect(() => {
    document.body.style.overflow = 'auto';
    return () => {
      document.body.style.overflow = 'hidden'; // Reset on cleanup
    };
  }, []);

  // Create MessageSender for VS Code environment
  const messageSender: MessageSender = {
    send: (message: any) => {
      if (window.vscode) {
        window.vscode.postMessage(message);
      }
    }
  };

  // Track if we've initialized to avoid re-init on sessionId change (use ref to avoid stale closure)
  const hasInitializedRef = useRef(false);

  // Initialize and listen for messages
  useEffect(() => {
    // Get session ID from window only on first mount (not when sessionId changes)
    if (window.sessionId && !hasInitializedRef.current) {
      setSessionId(window.sessionId);
    }

    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      switch (message.type) {
        case 'init':
          // Only initialize once - ignore subsequent init messages after user navigation
          if (hasInitializedRef.current) {
            break;
          }
          // Initialize the tab with experiment data
          const initExperiment = message.payload.experiment;
          // Handle transition from title to run_name for backwards compatibility
          const normalizedExperiment = {
            ...initExperiment,
            run_name: initExperiment.run_name || initExperiment.title || '',
          };
          setExperiment(normalizedExperiment);
          setSessionId(message.payload.sessionId);
          hasInitializedRef.current = true;
          break;
        case 'graph_update':
          // Always accept graph updates - the provider already filters by session
          // This avoids stale closure issues when switching experiments
          setGraphData(message.payload);
          break;
        case 'configUpdate':
          // Forward config updates to config bridge
          window.dispatchEvent(new CustomEvent('configUpdate', { detail: message.detail }));
          break;
        case 'updateNode':
          // Handle node updates from edit dialogs
          if (message.payload && graphData) {
            const { nodeId, field, value, session_id } = message.payload;
            if (session_id === sessionId) {
              handleNodeUpdate(nodeId, field, value, session_id);
            }
          }
          break;
        case 'experiment_update':
          // Update experiment data if it matches our session
          if (message.session_id === sessionId && message.experiment) {
            setExperiment(message.experiment);
          }
          break;
        case 'experiment_list':
          // Handle experiment list updates from server
          if (message.experiments) {
            // Store all experiments for the dropdown
            const allExperiments = message.experiments.map((exp: any) => ({
              session_id: exp.session_id,
              status: exp.status,
              timestamp: exp.timestamp,
              run_name: exp.run_name,
              result: exp.result,
              notes: exp.notes,
              log: exp.log,
              color_preview: exp.color_preview,
              version_date: exp.version_date
            }));
            setExperiments(allExperiments);
            // Note: Don't auto-update experiment here to avoid overwriting
            // user's selection due to stale closure issues
          }
          break;
        case 'vscode-theme-change':
          // Theme changes are handled by the useIsVsCodeDarkTheme hook
          break;
        case 'documentOpened':
          // Track opened document path for UI update
          if (message.payload?.documentKey && message.payload?.path) {
            setDocumentOpened(message.payload.documentKey, message.payload.path);
          }
          break;
      }
    };

    window.addEventListener('message', handleMessage);

    // Send ready message to indicate the webview is loaded
    if (window.vscode) {
      window.vscode.postMessage({ type: 'ready' });
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [sessionId, setDocumentOpened]);

  const handleNodeUpdate = (
    nodeId: string,
    field: string,
    value: string,
    sessionIdParam?: string,
    attachments?: any
  ) => {
    const currentSessionId = sessionIdParam || sessionId;
    if (currentSessionId && window.vscode) {
      const baseMsg = {
        session_id: currentSessionId,
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
          session_id: currentSessionId,
          nodeId,
          field,
          value,
          ...(attachments && { attachments }),
        });
      }
    }
  };

  const handleNavigateToExperiment = (exp: ProcessInfo) => {
    // Switch to the selected experiment in the current tab
    setExperiment(exp);
    setSessionId(exp.session_id);
    setGraphData(null); // Clear current graph while loading

    // Request new graph data
    if (window.vscode) {
      window.vscode.postMessage({
        type: 'switchExperiment',
        sessionId: exp.session_id,
        experiment: exp
      });
    }
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: isDarkTheme ? "#252525" : "#F0F0F0",
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <SharedGraphTabApp
          experiment={experiment}
          graphData={graphData}
          sessionId={sessionId}
          messageSender={messageSender}
          isDarkTheme={isDarkTheme}
          onNodeUpdate={handleNodeUpdate}
          headerContent={experiment ? (
            <GraphHeader
              runName={experiment.run_name || ''}
              isDarkTheme={isDarkTheme}
              sessionId={sessionId || undefined}
              experiments={experiments}
              onNavigateToExperiment={handleNavigateToExperiment}
            />
          ) : undefined}
        />
      </div>
    </div>
  );
};

// Wrap with DocumentContextProvider
export const GraphTabApp: React.FC = () => (
  <DocumentContextProvider>
    <GraphTabAppInner />
  </DocumentContextProvider>
);
