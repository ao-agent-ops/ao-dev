import React, { useCallback, useEffect, useState, useRef } from "react";
import ReactFlow, {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  Controls,
  ReactFlowProvider,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { CustomNode } from './CustomNode';
import { CustomEdge } from './CustomEdge';
import { GraphNode, GraphEdge, ProcessInfo } from '../types';
import { calculateNodePositions } from '../utils/nodeLayout';
import { routeEdges } from '../utils/edgeRouting';
import { sendNodeUpdate, sendMessage, sendReset } from '../utils/messaging';
import { useIsVsCodeDarkTheme } from '../utils/themeUtils';
import styles from './GraphView.module.css';
import erasePng from '../assets/erase.png';

interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeUpdate: (nodeId: string, field: keyof GraphNode, value: string) => void;
  experiment?: ProcessInfo;
  session_id?: string;
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
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [containerWidth, setContainerWidth] = useState(400);
  const [containerHeight, setContainerHeight] = useState(1500);

  const handleNodeUpdate = useCallback(
    (nodeId: string, field: keyof GraphNode, value: string) => {
      onNodeUpdate(nodeId, field, value);
      sendNodeUpdate(nodeId, field, value, session_id);
      sendReset();
    },
    [onNodeUpdate, session_id]
  );

  const updateLayout = useCallback(() => {
    const positions = calculateNodePositions(
      initialNodes,
      initialEdges,
      containerWidth
    );
    const maxY =
      Math.max(0, ...Array.from(positions.values()).map((pos) => pos.y)) + 300;
    setContainerHeight(maxY);

    const routedEdges = routeEdges(initialEdges, positions);

    const flowNodes: Node[] = initialNodes.map((node) => {
      return {
        id: node.id,
        type: "custom",
        position: positions.get(node.id) || { x: 0, y: 0 },
        data: {
          ...node,
          onUpdate: handleNodeUpdate,
          session_id,
        },
      };
    });

    const flowEdges: Edge[] = routedEdges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
      type: "custom",
      data: { points: edge.points },
      animated: false,
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [
    initialNodes,
    initialEdges,
    containerWidth,
    handleNodeUpdate,
    setNodes,
    setEdges,
    session_id,
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

  const isDarkTheme = useIsVsCodeDarkTheme();
  
  const mainLayoutStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "1fr 30px",
    alignItems: "start",
    width: "100%",
    height: "100%",
  };

  const titleContainerStyle: React.CSSProperties = {
    marginBottom: '0px',
    padding: '15px 15px 0 20px',
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '18px',
    fontWeight: 'bold',
    color: isDarkTheme ? '#FFFFFF' : '#000000',
  };

  const restartButtonStyle: React.CSSProperties = {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    background: '#27c93f',
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
    <div ref={containerRef} className={styles.container} style={{ width: '100%', height: '100%' }}>
      <div style={mainLayoutStyle}>
        <div>
          <div style={titleContainerStyle}>
            <div style={titleStyle}>
              {experiment
                ? (experiment.timestamp ? `${experiment.timestamp} (${experiment.session_id.substring(0, 8)}...)` : 'Graph')
                : 'Graph'}
            </div>
          </div>
          <ReactFlowProvider>
            <div
              className={styles.flowContainer}
              style={{ height: `${containerHeight}px`, marginTop: '0px', paddingTop: '0px' }}
            >
              <ReactFlow
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
                defaultViewport={{ x: 0, y: 0, zoom: 1 }}
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
                  margin: "0"
                }}
              />
            </div>
          </ReactFlowProvider>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, marginTop: '10px', marginRight:'30px' }}>
            <button
              style={{ ...restartButtonStyle, background: 'transparent', marginBottom: '4px'}}
              title="Clear edits"
              onClick={() => {
                if (!session_id) {
                  alert("No session_id available for erase! This is a bug.");
                  throw new Error("No session_id available for erase!");
                }
                sendMessage({ type: 'erase', session_id });
              }}
            >
              <img
                src={erasePng}
                alt="Erase"
                style={{
                  width: '100%',
                  height: '100%',
                  display: 'block',
                  borderRadius: '50%',
                  objectFit: 'cover',
                  background: 'transparent',
                  pointerEvents: 'none',
                }}
                draggable={false}
              />
            </button>
            <button
              style={{ ...restartButtonStyle, marginBottom: '8px'}}
              title="Restart"
              onClick={() => {
                if (!session_id) {
                  alert("No session_id available for restart! This is a bug.");
                  throw new Error("No session_id available for restart!");
                }
                sendMessage({ type: 'restart', session_id });
              }}
            >
              {React.createElement('svg', {
                width: "20",
                height: "20",
                viewBox: "0 0 20 20",
                fill: "none",
                xmlns: "http://www.w3.org/2000/svg",
                style: { pointerEvents: 'none' }
              },
                React.createElement('path', {
                  d: "M10 3a7 7 0 1 1-6.32 4",
                  stroke: "#fff",
                  strokeWidth: "2",
                  fill: "none",
                  strokeLinecap: "round",
                  strokeLinejoin: "round"
                }),
                React.createElement('polyline', {
                  points: "3 3 7 3 7 7",
                  stroke: "#fff",
                  strokeWidth: "2",
                  fill: "none",
                  strokeLinecap: "round",
                  strokeLinejoin: "round"
                })
              )}
            </button>
        </div>
      </div>
    </div>
  );
};