import { useEffect, useState, useRef} from "react";
import ReactFlow, { MiniMap, Controls, Background, MarkerType } from "reactflow";
import type { Node, Edge } from "reactflow";
import "reactflow/dist/style.css";
import "./App.css";
import type { GraphNode, GraphEdge } from "../../../user_interface/src/webview/types";
import { calculateNodePositions, NODE_WIDTH, NODE_HEIGHT } from "../../../user_interface/src/webview/utils/nodeLayout";

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
}

function App() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [graph, setGraph] = useState<{ nodes: Node[]; edges: Edge[] } | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const socket = new WebSocket("ws://localhost:4000");
    setWs(socket);

    socket.onopen = () => console.log("Connected to backend");

    socket.onmessage = (event: MessageEvent) => {
      const msg: WSMessage = JSON.parse(event.data);
      if (msg.type === "experiment_list" && msg.experiments) {
        setExperiments(msg.experiments);
      } else if (msg.type === "graph_update" && msg.payload) {
        setGraph(transformGraph(msg.payload));
      }
    };

    return () => socket.close();
  }, []);

  const transformGraph = (data: GraphData) => {
    const containerWidth = containerRef.current?.offsetWidth || 800;

    const positions = calculateNodePositions(data.nodes, data.edges, containerWidth);

    const nodes: Node[] = data.nodes.map((n) => ({
      id: n.id,
      data: {
        label: (
          <div className="node-label">
            <b>{n.label}</b>
            {/* {n.input ? `\nInput: ${n.input}` : ""}
            {n.output ? `\nOutput: ${n.output}` : ""} */}
          </div>
        ),
      },
      position: positions.get(n.id) || { x: 0, y: 0 },
      style: {
        border: `2px solid ${n.border_color || "#000"}`,
        padding: 10,
        borderRadius: 5,
        background: "#fff",
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      },
    }));

    const edges: Edge[] = data.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "step",
      style: { 
        stroke: "#000",
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: "#000",
      }
    }));

    return { nodes, edges };
  };

  const handleExperimentClick = (session_id: string) => {
    if (ws) ws.send(JSON.stringify({ type: "get_graph", session_id }));
  };

  return (
    <div className="app-container">
      {sidebarOpen && (
        <div className="sidebar">
          <h2 className="sidebar-title">Experiments</h2>
          <div className="experiment-list">
            {experiments.map((exp) => (
              <button
                key={exp.session_id}
                className="experiment-button"
                onClick={() => handleExperimentClick(exp.session_id)}
              >
                {exp.title}
                <br />
                <small className="experiment-status">({exp.status})</small>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="graph-container" ref={containerRef}>
        <button className="toggle-button" onClick={() => setSidebarOpen(!sidebarOpen)}>
          {sidebarOpen ? "Hide Experiments" : "Show Experiments"}
        </button>

        <ReactFlow
          nodes={graph?.nodes || []}
          edges={graph?.edges || []}
          fitView
          className="reactflow-container"
        >
          <MiniMap />
          <Controls />
          <Background color="#eee" gap={16} />
        </ReactFlow>
      </div>
    </div>
  );
}

export default App;