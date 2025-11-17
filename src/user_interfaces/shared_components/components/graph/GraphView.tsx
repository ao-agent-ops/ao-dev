import React, { useCallback, useEffect, useState, useRef, useMemo } from "react";
import ReactFlow, {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import { CustomNode } from './CustomNode';
import { CustomEdge } from './CustomEdge';
import { GraphNode, GraphEdge, ProcessInfo } from '../../types';
import { LayoutEngine } from '../../utils/layoutEngine';
import { MessageSender } from '../../types/MessageSender';
// import { useIsVsCodeDarkTheme } from '../utils/themeUtils';
import styles from './GraphView.module.css';
import { FLOW_CONTAINER_MARGIN_TOP, NODE_WIDTH } from '../../utils/layoutConstants';
// Icons are now handled via codicons

interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeUpdate: (nodeId: string, field: keyof GraphNode, value: string) => void;
  experiment?: ProcessInfo;
  session_id?: string;
  messageSender: MessageSender;
  isDarkTheme?: boolean;
}

const nodeTypes = {
  custom: CustomNode,
};

const edgeTypes = {
  custom: CustomEdge,
};

export const GraphView: React.FC<GraphViewProps> = ({
  nodes: initialNodes,
  edges: initialEdges,
  onNodeUpdate,
  experiment,
  session_id,
  messageSender,
  isDarkTheme = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [containerWidth, setContainerWidth] = useState(400);
  const [containerHeight, setContainerHeight] = useState(1500);
  const [viewport, setViewport] = useState<{ x: number; y: number; zoom: number }>({ x: 0, y: 0, zoom: 1 });
  const [rfKey, setRfKey] = useState(0);

  // Create layout engine instance using useMemo to prevent recreation
  const layoutEngine = useMemo(() => new LayoutEngine(), []);

  const handleNodeUpdate = useCallback(
    (nodeId: string, field: keyof GraphNode, value: string) => {
      onNodeUpdate(nodeId, field, value);
      messageSender.send({
        type: 'update_node',
        node_id: nodeId,
        field,
        value,
        session_id
      });
      messageSender.send({ type: 'reset', id: Math.floor(Math.random() * 100000) });
    },
    [onNodeUpdate, session_id, messageSender]
  );

  const updateLayout = useCallback(() => {
    // Use the new layout engine instead of separate functions
    const layout = layoutEngine.layoutGraph(initialNodes, initialEdges, containerWidth);
    
    // Calculate if we have left bands that need negative positioning
  const hasLeftBands = layout.edges.some(edge => edge.band?.includes('Left'));
    
    // Find the minimum X position to adjust for left bands
    let minX = 0;
    if (hasLeftBands) {
      layout.edges.forEach(edge => {
        if (edge.points && edge.points.length > 0) {
          edge.points.forEach(point => {
            if (point.x < minX) minX = point.x;
          });
        }
      });
    }
    
    // Adjust positions if we have negative X coordinates
    const xOffset = minX < 0 ? Math.abs(minX) + 20 : 0;

  const maxY = Math.max(0, ...Array.from(layout.positions.values()).map((pos) => pos.y)) + 300;
  setContainerHeight(maxY);

  const flowNodes: Node[] = initialNodes.map((node) => {
      const position = layout.positions.get(node.id) || { x: 0, y: 0 };
      return {
        id: node.id,
        type: "custom",
        position: { x: position.x + xOffset, y: position.y },
        data: {
          ...node,
          onUpdate: handleNodeUpdate,
          session_id,
          messageSender,
          isDarkTheme,
        },
      };
    });

  const flowEdges: Edge[] = layout.edges.map((edge) => {
      // Adjust edge points if needed
      const adjustedPoints = edge.points.map(point => ({
        x: point.x + xOffset,
        y: point.y
      }));
      
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        type: "custom",
    data: { points: adjustedPoints, color: edge.color },
        animated: false,
      };
    });

    setNodes(flowNodes);
    setEdges(flowEdges);

  // Horizontal-only viewport fit (no vertical adjustments)
  const PADDING_X = 40;
  const nodeMinX = flowNodes.length ? Math.min(...flowNodes.map(n => n.position.x)) : 0;
  const nodeMaxX = flowNodes.length ? Math.max(...flowNodes.map(n => n.position.x + NODE_WIDTH)) : 0;
  const edgeXs = flowEdges.flatMap(e => (e.data as any)?.points?.map((p: any) => p.x) ?? []);
  const edgesMinX = edgeXs.length ? Math.min(...edgeXs) : nodeMinX;
  const edgesMaxX = edgeXs.length ? Math.max(...edgeXs) : nodeMaxX;
  const minXAll = Math.min(nodeMinX, edgesMinX);
  const maxXAll = Math.max(nodeMaxX, edgesMaxX);
  const widthSpan = Math.max(1, maxXAll - minXAll);
  const bboxW = widthSpan + PADDING_X * 2;
  const availableW = Math.max(1, containerWidth);
  const zoom = Math.min(1, availableW / bboxW);
  const x = -minXAll * zoom + (availableW - widthSpan * zoom) / 2;
  setViewport({ x, y: 0, zoom });
  setRfKey(k => k + 1);
  }, [
    initialNodes,
    initialEdges,
    containerWidth,
    handleNodeUpdate,
    setNodes,
    setEdges,
    session_id,
    layoutEngine
  ]);

  useEffect(() => {
    updateLayout();
  }, [updateLayout]);


  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const grid = containerRef.current.firstChild;
        let mainColWidth = containerRef.current.offsetWidth;
        if (grid && grid instanceof HTMLElement && grid.style.display === 'grid') {
          const gridCols = window.getComputedStyle(grid).gridTemplateColumns.split(' ');
          if (gridCols.length > 1) {
            mainColWidth = parseInt(gridCols[0], 10);
          }
        }
        setContainerWidth(mainColWidth);
      }
    };

    handleResize();

    const resizeObserver = new ResizeObserver(handleResize);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // const isDarkTheme = useIsVsCodeDarkTheme();
  
  const mainLayoutStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "1fr 30px",
    alignItems: "start",
    width: "100%",
    height: "100%",
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--vscode-foreground)',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const restartButtonStyle: React.CSSProperties = {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    background: 'transparent',
    border: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
    cursor: 'pointer',
    outline: 'none',
    padding: 0,
    position: 'relative',
  };

  return (
    <div
      ref={containerRef}
      className={styles.container}
      style={{ 
        width: "100%", 
        height: "100%",
        fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)"
      }}
    >
      <div style={mainLayoutStyle}>
        <div>
          <ReactFlowProvider>
            <div
              className={styles.flowContainer}
              style={{
                height: `${containerHeight}px`,
                marginTop: `${FLOW_CONTAINER_MARGIN_TOP}px`,
                paddingTop: "0px",
              }}
            >
              <ReactFlow
                key={rfKey}
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView={false}
                proOptions={{ hideAttribution: true }}
                minZoom={0.4}
                maxZoom={1}
                defaultViewport={viewport}
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable={true}
                panOnDrag={false}
                zoomOnScroll={false}
                zoomOnPinch={false}
                zoomOnDoubleClick={false}
                panOnScroll={false}
                preventScrolling={false}
                style={{
                  width: "100%",
                  height: "auto",
                  padding: "0",
                  margin: "0",
                }}
              />
            </div>
          </ReactFlowProvider>
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 4,
            marginTop: "10px",
            marginRight: "30px",
          }}
        >
          <button
            style={{
              ...restartButtonStyle,
              background: "transparent",
              marginBottom: "4px",
            }}
            title="Show details panel"
            onClick={() => {
              window.dispatchEvent(new CustomEvent('show-run-details-modal', {
                detail: { experiment }
              }));
            }}
          >
            <i className="codicon codicon-tag" style={{
              fontSize: "20px",
              color: "#c4a05aff",
              pointerEvents: "none",
            }}></i>
          </button>
          <button
            style={{
              ...restartButtonStyle,
              background: "transparent",
              marginBottom: "4px",
            }}
            title="Clear edits"
            onClick={() => {
              if (!session_id) {
                alert("No session_id available for erase! This is a bug.");
                throw new Error("No session_id available for erase!");
              }
              messageSender.send({ type: "erase", session_id });
            }}
          >
            <i className="codicon codicon-eraser" style={{
              fontSize: "20px",
              color: "#c36e5dff",
              pointerEvents: "none",
            }}></i>
          </button>
          <button
            style={{ ...restartButtonStyle, marginBottom: "8px" }}
            title="Restart"
            onClick={() => {
              if (!session_id) {
                alert("No session_id available for restart! This is a bug.");
                throw new Error("No session_id available for restart!");
              }
              messageSender.send({ type: "restart", session_id });
            }}
          >
            <i className="codicon codicon-debug-restart" style={{
              fontSize: "20px",
              color: "#7fc17bff",
              pointerEvents: "none",
            }}></i>
          </button>
        </div>
      </div>
    </div>
  );
};