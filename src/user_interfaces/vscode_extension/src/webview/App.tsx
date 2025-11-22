import React, { useEffect, useState } from 'react';
import { ExperimentsView } from '../../../shared_components/components/experiment/ExperimentsView';
import { ProcessInfo } from '../../../shared_components/types';
import { sendReady } from '../../../shared_components/utils/messaging';
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
    sendReady();
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

  // Use experiments in the order sent by server (already sorted by name ascending)
  const sortedProcesses = processes;
  
  // const similarExperiments = sortedProcesses.filter(p => p.status === 'similar');
  const similarExperiments = sortedProcesses[0];
  const runningExperiments = sortedProcesses.filter(p => p.status === 'running');
  const finishedExperiments = sortedProcesses.filter(p => p.status === 'finished');


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
      {/* The Experiments header and dropdown are now handled by ExperimentsView when showHeader=true */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        <ExperimentsView
          similarProcesses={similarExperiments ? [similarExperiments] : []}
          runningProcesses={runningExperiments}
          finishedProcesses={finishedExperiments}
          onCardClick={handleExperimentCardClick}
          isDarkTheme={isDarkTheme}
          showHeader={true}
          onModeChange={handleDatabaseModeChange}
          currentMode={databaseMode}
        />
      </div>
    </div>
  );
};