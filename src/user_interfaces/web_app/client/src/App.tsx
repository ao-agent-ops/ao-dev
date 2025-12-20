import { useEffect, useState, useRef } from "react";
import { LoginScreen } from "./LoginScreen";
import "./App.css";
import type { GraphNode, GraphEdge, ProcessInfo } from "../../../shared_components/types";
import { GraphTabApp } from "../../../shared_components/components/GraphTabApp";
import { ExperimentsView} from "../../../shared_components/components/experiment/ExperimentsView";
import type { MessageSender } from "../../../shared_components/types/MessageSender";

interface Experiment {
  session_id: string;
  title: string;
  status: string;
  timestamp: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface WSMessage {
  type: string;
  experiments?: Experiment[];
  payload?: GraphData;
  session_id?: string;
  color_preview? : string[];
  database_mode?: string;
}


function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<any | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:5958";
  const [experiments, setExperiments] = useState<ProcessInfo[]>([]);
  const [selectedExperiment, setSelectedExperiment] = useState<ProcessInfo | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [showDetailsPanel, setShowDetailsPanel] = useState(false);
  const [databaseMode, setDatabaseMode] = useState<'Local' | 'Remote'>('Local');
  // const [sidebarOpen, setSidebarOpen] = useState(true);
  const [editDialog, setEditDialog] = useState<{
    nodeId: string;
    field: string;
    value: string;
    label: string;
    attachments?: any;
  } | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(250);
  const [isResizing, setIsResizing] = useState(false);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messageBufferRef = useRef<string>(''); // Buffer for incomplete WebSocket frames

  // Detect dark theme reactively
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches || false;
  });

  // Listen for theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e: MediaQueryListEvent) => {
      setIsDarkTheme(e.matches);
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  // Handle sidebar resizing
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isResizing) {
        const newWidth = e.clientX;
        // Constrain width between 150px and 600px
        if (newWidth >= 150 && newWidth <= 600) {
          setSidebarWidth(newWidth);
        }
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  const handleResizeStart = () => {
    setIsResizing(true);
  };

  // Create webapp MessageSender that always uses the current WebSocket from the ref
  const messageSender: MessageSender = {
    send: (message: any) => {
      if (message.type === "showNodeEditModal") {
        // Handle showNodeEditModal by dispatching window event (same as VS Code)
        window.dispatchEvent(new CustomEvent('show-node-edit-modal', {
          detail: message.payload
        }));
      } else if (
        message.type === "trackNodeInputView" ||
        message.type === "trackNodeOutputView"
      ) {
        // Telemetry - no action needed in webapp
      } else if (message.type === "navigateToCode") {
        // Code navigation not available in webapp
      } else if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(message));
      }
    },
  };

  useEffect(() => {
    if (!authenticated) return;
    
    // Permitir definir la URL del WebSocket por variable de entorno
    const baseWsUrl = import.meta.env.VITE_APP_WS_URL || (() => {
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsHost = window.location.hostname === "localhost"
        ? "localhost:4000"
        : window.location.host;
      return `${wsProtocol}//${wsHost}/ws`;
    })();
    
    // Include user_id in WebSocket URL if available for cleaner handshake authentication
    const wsUrl = user && user.id ? `${baseWsUrl}?user_id=${encodeURIComponent(user.id)}` : baseWsUrl;

    const socket = new WebSocket(wsUrl);
    setWs(socket);
    wsRef.current = socket; // Keep ref in sync

    socket.onopen = () => {
      console.log("Connected to backend");
      // Note: The WebSocket proxy (server.js) automatically sends the handshake
      // with role: "ui" and user_id from the URL query parameter.
      // We should NOT send our own handshake here.

      // Request the experiment list
      socket.send(JSON.stringify({ type: "get_all_experiments" }));
    };

    socket.onmessage = (event: MessageEvent) => {
      // WebSocket can fragment large messages across multiple frames
      // We need to buffer incomplete JSON until we get a complete message
      const chunk = event.data;

      // Add chunk to buffer
      messageBufferRef.current += chunk;

      // Try to parse the buffered content
      let msg: WSMessage;
      try {
        msg = JSON.parse(messageBufferRef.current);
        // Successfully parsed - clear the buffer and process the message
        messageBufferRef.current = '';
      } catch (error) {
        // JSON is incomplete - wait for more chunks
        return;
      }

      // Process the complete message
      switch (msg.type) {
        case "experiment_list":
          if (msg.experiments) {
            const updatedExperiments = msg.experiments;
            setExperiments(updatedExperiments);
            // Update selectedExperiment if it matches one in the updated list
            // This ensures metadata edits are reflected in the UI
            setSelectedExperiment((current) => {
              if (!current) return null;
              const updated = updatedExperiments.find(
                (exp: ProcessInfo) => exp.session_id === current.session_id
              );
              return updated || current;
            });
          }
          break;

        case "graph_update":
          if (msg.payload) {
            setGraphData(msg.payload);
          }
          break;

        case "color_preview_update":
          if (msg.session_id) {
            const sid = msg.session_id;
            const color_preview = msg.color_preview;

            setExperiments((prev) => {
              const updated = prev.map(process =>
                process.session_id === sid
                  ? { ...process, color_preview }
                  : process
              );
              return updated;
            });
          }
          break;

        case "session_id":
          // Handle initial connection message with database mode
          if (msg.database_mode) {
            const mode = msg.database_mode === 'local' ? 'Local' : 'Remote';
            setDatabaseMode(mode);
            console.log(`Synchronized database mode to: ${mode}`);
          }
          break;

        case "database_mode_changed":
          // Handle database mode change broadcast from server
          if (msg.database_mode) {
            const mode = msg.database_mode === 'local' ? 'Local' : 'Remote';
            setDatabaseMode(mode);
            console.log(`Database mode changed by another UI to: ${mode}`);
          }
          break;

        default:
          console.warn(`Unhandled message type: ${msg.type}`);
      }
    };

    return () => socket.close();
  }, [authenticated, user]);

  // On app mount check session (useful after OAuth redirect)
  // Fetch session and set user+authenticated state
  const checkSession = async () => {
    console.log('🔍 checkSession starting, API_BASE:', API_BASE);
    setCheckingSession(true);
    try {
      const sessionUrl = `${API_BASE}/auth/session`;
      console.log('📡 Fetching session from:', sessionUrl);
      const resp = await fetch(sessionUrl, { credentials: 'include' });
      console.log('📡 Session response status:', resp.status, 'ok:', resp.ok);
      
      if (!resp.ok) {
        console.log('❌ Response not OK, setting authenticated=false');
        setAuthenticated(false);
        setUser(null);
        return;
      }
      
      const data = await resp.json();
      console.log('📋 Session data received:', data);
      console.log('📋 Has user?', !!(data && data.user));
      
      if (data && data.user) {
        console.log('✅ Setting authenticated=true, user:', data.user);
        setAuthenticated(true);
        setUser(data.user);
      } else {
        console.log('❌ No user in data, setting authenticated=false');
        setAuthenticated(false);
        setUser(null);
      }
    } catch (err) {
      console.error('❌ Failed to check session', err);
      setAuthenticated(false);
      setUser(null);
    } finally {
      console.log('🏁 checkSession finished, calling setCheckingSession(false)');
      setCheckingSession(false);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  const handleNodeUpdate = (
    nodeId: string,
    field: string,
    value: string,
    sessionId?: string,
    attachments?: any
  ) => {
    if (selectedExperiment && ws) {
      const currentSessionId = sessionId || selectedExperiment.session_id;
      const baseMsg = {
        session_id: currentSessionId,
        node_id: nodeId,
        value,
        ...(attachments && { attachments }),
      };

      if (field === "input") {
        ws.send(JSON.stringify({ type: "edit_input", ...baseMsg }));
      } else if (field === "output") {
        ws.send(JSON.stringify({ type: "edit_output", ...baseMsg }));
      } else {
        ws.send(
          JSON.stringify({
            type: "updateNode",
            session_id: currentSessionId,
            nodeId,
            field,
            value,
            ...(attachments && { attachments }),
          })
        );
      }
    }
  };

  const handleExperimentClick = (experiment: ProcessInfo) => {
    // Clear graph data when switching experiments to avoid showing stale data
    setGraphData(null);
    setSelectedExperiment(experiment);

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "get_graph", session_id: experiment.session_id }));
    }
  };

  const handleDatabaseModeChange = (mode: 'Local' | 'Remote') => {
    // Update local state immediately for responsive UI
    setDatabaseMode(mode);
    
    // Send WebSocket message to server
    if (ws) {
      ws.send(JSON.stringify({
        type: 'set_database_mode',
        mode: mode.toLowerCase()
      }));
    }
  };

  // const running = experiments.filter((e) => e.status === "running");
  // const finished = experiments.filter((e) => e.status === "finished");

  const sortedExperiments = experiments;

  const similarExperiments = sortedExperiments[0];
  const running = sortedExperiments.filter((e) => e.status === "running");
  const finished = sortedExperiments.filter((e) => e.status === "finished");

  if (checkingSession) {
    // while we verify session do not show the login screen to avoid flicker
    return (
      <div className={`app-container ${isDarkTheme ? 'dark' : ''}`}>
        <div style={{ padding: 24 }}>
          Checking authentication...
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <LoginScreen
        onSuccess={async () => {
          setAuthenticated(true);
          // after successful login try to load session user
          await checkSession();
        }}
      />
    );
  }

  return (
    <div className={`app-container ${isDarkTheme ? 'dark' : ''}`}>
      <div className="sidebar" style={{ width: `${sidebarWidth}px` }}>
        <ExperimentsView
          similarProcesses={similarExperiments ? [similarExperiments] : []}
          runningProcesses={running}
          finishedProcesses={finished}
          onCardClick={handleExperimentClick}
          isDarkTheme={isDarkTheme}
          user={{
            displayName: user?.name || user?.displayName,
            avatarUrl: user?.picture || user?.avatarUrl,
            email: user?.email,
          }}
          onLogout={() => {
            fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' })
              .catch((err) => console.warn('Logout request failed', err));
            setAuthenticated(false);
            setUser(null);
          }}
          showHeader={true}
          onModeChange={handleDatabaseModeChange}
          currentMode={databaseMode}
        />
        <div
          className="sidebar-resize-handle"
          onMouseDown={handleResizeStart}
        />
      </div>

      <div className="graph-container" ref={graphContainerRef}>
        {selectedExperiment && graphData ? (
          <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            {/* Graph Title Header */}
            <div
              style={{
                padding: "12px 20px",
                borderBottom: `1px solid ${isDarkTheme ? "#3c3c3c" : "#e0e0e0"}`,
                backgroundColor: isDarkTheme ? "#1e1e1e" : "#ffffff",
                color: isDarkTheme ? "#e5e5e5" : "#333333",
                fontSize: "16px",
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {selectedExperiment.run_name || selectedExperiment.session_id}
            </div>
            {/* Graph */}
            <div style={{ flex: 1, minHeight: 0 }}>
              <GraphTabApp
                experiment={selectedExperiment}
                graphData={graphData}
                sessionId={selectedExperiment.session_id}
                messageSender={messageSender}
                isDarkTheme={isDarkTheme}
                onNodeUpdate={handleNodeUpdate}
              />
            </div>
          </div>
        ) : (
          <div className="no-graph">
            {selectedExperiment ? "Loading graph..." : "Select an experiment to view its graph"}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;