import React, { useState, useEffect } from 'react';
import { GraphTabApp as SharedGraphTabApp } from '../../../shared_components/components/GraphTabApp';
import { GraphData, ProcessInfo } from '../../../shared_components/types';
import { MessageSender } from '../../../shared_components/types/MessageSender';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';
import { GraphHeader } from '../../../shared_components/components/graph/GraphHeader';
import { Lesson } from '../../../shared_components/components/lessons/LessonsView';

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

export const GraphTabApp: React.FC = () => {
  const [experiment, setExperiment] = useState<ProcessInfo | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const isDarkTheme = useIsVsCodeDarkTheme();

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
      // Handle showNodeEditModal locally by dispatching window event
      if (message.type === 'showNodeEditModal') {
        window.dispatchEvent(new CustomEvent('show-node-edit-modal', {
          detail: message.payload
        }));
      } else if (window.vscode) {
        window.vscode.postMessage(message);
      }
    }
  };

  // Initialize and listen for messages
  useEffect(() => {
    // Get session ID from window
    if (window.sessionId) {
      setSessionId(window.sessionId);
    }

    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      switch (message.type) {
        case 'init':
          // Initialize the tab with experiment data
          const initExperiment = message.payload.experiment;
          // Handle transition from title to run_name for backwards compatibility
          const normalizedExperiment = {
            ...initExperiment,
            run_name: initExperiment.run_name || initExperiment.title || '',
          };
          setExperiment(normalizedExperiment);
          setSessionId(message.payload.sessionId);
          break;
        case 'graph_update':
          if (message.session_id === sessionId || message.session_id === window.sessionId) {
            setGraphData(message.payload);
          }
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
          // Use either the state sessionId or window.sessionId as fallback
          const currentSessionId = sessionId || window.sessionId;
          if (message.experiments && currentSessionId) {
            const updatedExperiment = message.experiments.find(
              (exp: any) => exp.session_id === currentSessionId
            );
            if (updatedExperiment) {
              // Map server experiment format to ProcessInfo format
              const processInfo = {
                session_id: updatedExperiment.session_id,
                status: updatedExperiment.status,
                timestamp: updatedExperiment.timestamp,
                run_name: updatedExperiment.run_name,
                result: updatedExperiment.result,
                notes: updatedExperiment.notes,
                log: updatedExperiment.log,
                color_preview: updatedExperiment.color_preview,
                version_date: updatedExperiment.version_date
              };
              setExperiment(processInfo);

              // Update tab title when experiment data changes
              if (window.vscode && processInfo.run_name) {
                window.vscode.postMessage({
                  type: 'updateTabTitle',
                  payload: {
                    sessionId: currentSessionId,
                    title: processInfo.run_name
                  }
                });
              }
            }
          }
          break;
        case 'vscode-theme-change':
          // Theme changes are handled by the useIsVsCodeDarkTheme hook
          break;
        case 'lessons_list':
          // Update lessons for header stats
          setLessons(message.lessons || []);
          break;
      }
    };

    window.addEventListener('message', handleMessage);

    // Send ready message to indicate the webview is loaded
    // Also request lessons data for header stats
    if (window.vscode) {
      window.vscode.postMessage({ type: 'ready' });
      window.vscode.postMessage({ type: 'get_lessons' });
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [sessionId]);

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

  const handleNavigateToLessons = () => {
    // Open lessons tab in VSCode
    if (window.vscode) {
      window.vscode.postMessage({ type: 'openLessonsTab' });
    }
  };

  return (
    <div
      style={{
        width: "100%",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: isDarkTheme ? "#252525" : "#F0F0F0",
      }}
    >
      {/* Graph Header with lesson stats */}
      {experiment && sessionId && (
        <GraphHeader
          runName={experiment.run_name || ''}
          sessionId={sessionId}
          lessons={lessons}
          isDarkTheme={isDarkTheme}
          onNavigateToLessons={handleNavigateToLessons}
        />
      )}
      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        <SharedGraphTabApp
          experiment={experiment}
          graphData={graphData}
          sessionId={sessionId}
          messageSender={messageSender}
          isDarkTheme={isDarkTheme}
          onNodeUpdate={handleNodeUpdate}
        />
      </div>
    </div>
  );
};
