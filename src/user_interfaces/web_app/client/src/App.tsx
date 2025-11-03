import { useEffect, useState, useRef } from "react";
import { LoginScreen } from "./LoginScreen";
import "./App.css";
import type { GraphNode, GraphEdge, ProcessInfo } from "../../../shared_components/types";
import { GraphView } from "../../../shared_components/components/graph/GraphView";
import { ExperimentsView} from "../../../shared_components/components/experiment/ExperimentsView";
import type { MessageSender } from "../../../shared_components/types/MessageSender";
import { EditDialog } from "../../../shared_components/components/EditDialog";
import { WorkflowRunDetailsPanel } from "../../../shared_components/components/experiment/WorkflowRunDetailsPanel";

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
}


function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [experiments, setExperiments] = useState<ProcessInfo[]>([]);
  const [selectedExperiment, setSelectedExperiment] = useState<ProcessInfo | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [showDetailsPanel, setShowDetailsPanel] = useState(false);
  // const [sidebarOpen, setSidebarOpen] = useState(true);
  const [editDialog, setEditDialog] = useState<{
    nodeId: string;
    field: string;
    value: string;
    label: string;
    attachments?: any;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Detect dark theme
  const isDarkTheme = window.matchMedia?.("(prefers-color-scheme: dark)").matches || false;

  // Create webapp MessageSender
  const messageSender: MessageSender = {
    send: (message: any) => {
      if (message.type === "showEditDialog") {
        setEditDialog(message.payload);
      } else if (
        message.type === "trackNodeInputView" ||
        message.type === "trackNodeOutputView"
      ) {
        console.log("Telemetry:", message.type, message.payload);
      } else if (message.type === "navigateToCode") {
        console.log("Code navigation not available in webapp");
      } else if (ws) {
        ws.send(JSON.stringify(message));
      }
    },
  };

  useEffect(() => {
    if (!authenticated) return;
    // Permitir definir la URL del WebSocket por variable de entorno
    const wsUrl = import.meta.env.VITE_APP_WS_URL || (() => {
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsHost = window.location.hostname === "localhost"
        ? "localhost:4000"
        : window.location.host;
      return `${wsProtocol}//${wsHost}/ws`;
    })();

    const socket = new WebSocket(wsUrl);
    setWs(socket);

    socket.onopen = () => console.log("Connected to backend");

    socket.onmessage = (event: MessageEvent) => {
      const msg: WSMessage = JSON.parse(event.data);
      switch (msg.type) {
        case "experiment_list":
          if (msg.experiments) {
            setExperiments(msg.experiments);
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
            console.log(`Color preview update for ${sid}:`, color_preview);
    
            setExperiments((prev) => {
              const updated = prev.map(process =>
                process.session_id === sid
                  ? { ...process, color_preview }
                  : process
              );
              console.log('Updated processes:', updated);
              return updated;
            });
          }
          break;
    
        default:
          console.warn(`Unhandled message type: ${msg.type}`);
      }

    };

    return () => socket.close();
  }, [authenticated]);

  const handleNodeUpdate = (nodeId: string, field: keyof GraphNode, value: string) => {
    if (selectedExperiment && ws) {
      if (field == "input") {
        ws.send(
          JSON.stringify({
            type: "edit_input",
            session_id: selectedExperiment.session_id,
            node_id: nodeId,
            value,
          })
        )
      } else if (field == "output") {
        ws.send(
          JSON.stringify({
            type: "edit_output",
            session_id: selectedExperiment.session_id,
            node_id: nodeId,
            value,
          })
        )
      } else {
        ws.send(
          JSON.stringify({
            type: "updateNode",
            session_id: selectedExperiment.session_id,
            nodeId,
            field,
            value,
          })
        );
      }
    }
  };

  const handleExperimentClick = (experiment: ProcessInfo) => {
    setSelectedExperiment(experiment);
    setShowDetailsPanel(true);
    if (ws) ws.send(JSON.stringify({ type: "get_graph", session_id: experiment.session_id }));
  };

  // const running = experiments.filter((e) => e.status === "running");
  // const finished = experiments.filter((e) => e.status === "finished");

  const sortedExperiments = experiments;
  
  const similarExperiments = sortedExperiments[0];
  const running = sortedExperiments.filter((e) => e.status === "running");
  const finished = sortedExperiments.filter((e) => e.status === "finished");

  if (!authenticated) {
    return <LoginScreen onSuccess={() => setAuthenticated(true)} />;
  }

  return (
    <div className={`app-container ${isDarkTheme ? 'dark' : ''}`}>
      <div className="sidebar">
        <ExperimentsView
          similarProcesses={similarExperiments ? [similarExperiments] : []}
          runningProcesses={running}
          finishedProcesses={finished}
          onCardClick={handleExperimentClick}
          isDarkTheme={isDarkTheme}
        />
      </div>

      <div className="graph-container" ref={containerRef}>
        {/* <button className="toggle-button" onClick={() => setSidebarOpen(!sidebarOpen)}>
          {sidebarOpen ? "Hide Experiments" : "Show Experiments"}
        </button> */}

        {selectedExperiment && graphData ? (
          <GraphView
            nodes={graphData.nodes}
            edges={graphData.edges}
            onNodeUpdate={handleNodeUpdate}
            session_id={selectedExperiment.session_id}
            experiment={selectedExperiment}
            messageSender={messageSender}
            isDarkTheme={isDarkTheme}
          />
        ) : (
          <div className="no-graph">
            {selectedExperiment ? "Loading graph..." : "Select an experiment to view its graph"}
          </div>
        )}
      </div>

      {showDetailsPanel && selectedExperiment && (
        <div className="details-panel">
          <WorkflowRunDetailsPanel
            runName={selectedExperiment.title || selectedExperiment.session_id}
            result=""
            notes=""
            log=""
            onBack={() => setShowDetailsPanel(true)}
          />
        </div>
      )}

      {editDialog && (
        <EditDialog
          title={`Edit ${editDialog.label}`}
          value={editDialog.value}
          onSave={(newValue) => {
            handleNodeUpdate(
              editDialog.nodeId,
              editDialog.field as keyof GraphNode,
              newValue
            );
            setEditDialog(null);
          }}
          onCancel={() => setEditDialog(null)}
          isDarkTheme={isDarkTheme}
        />
      )}
    </div>
  );
}

export default App;