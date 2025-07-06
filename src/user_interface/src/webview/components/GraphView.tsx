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
import { GraphNode, GraphEdge } from '../types';
import { calculateNodePositions } from '../utils/nodeLayout';
import { routeEdges } from '../utils/edgeRouting';
import { sendNodeUpdate, sendMessage } from '../utils/messaging';

interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeUpdate: (nodeId: string, field: string, value: string) => void;
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
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [containerWidth, setContainerWidth] = useState(400);
  const [containerHeight, setContainerHeight] = useState(1500);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [title, setTitle] = React.useState("Graph Title Placeholder");
  
  const handleNodeUpdate = useCallback(
    (nodeId: string, field: string, value: string) => {
      onNodeUpdate(nodeId, field, value);
      sendNodeUpdate(nodeId, field as any, value);
    },
    [onNodeUpdate]
  );

  const updateLayout = useCallback(() => {
    if (initialNodes.length === 0) return;

    const positions = calculateNodePositions(
      initialNodes,
      initialEdges,
      containerWidth
    );
    const maxY =
      Math.max(...Array.from(positions.values()).map((pos) => pos.y)) + 300;
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
  ]);

  useEffect(() => {
    updateLayout();
  }, [updateLayout]);

  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const newWidth = containerRef.current.offsetWidth;
        setContainerWidth(newWidth);
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

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        overflowY: "auto", // vertical scroll bar
        overflowX: "hidden", // no horizontal overflow
      }}
    >
      <>
        <div
          style={{
            marginTop: 20,
            marginBottom: 8,
            fontWeight: "bold",
            fontSize: 18,
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ width: 52, minWidth: 32, marginLeft: 1 }} />
          <span style={{ flex: 1, textAlign: "center" }}>{title}</span>
          <button
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "#27c93f",
              border: "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
              cursor: "pointer",
              outline: "none",
              padding: 0,
              marginLeft: 12,
              marginRight: 20,
            }}
            title="Restart"
            onClick={() => {
              alert("Green button clicked!");
              console.log("Green button clicked: sending restart");
              sendMessage({ type: 'restart', id: Math.floor(Math.random() * 100000) });
            }}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M10 3a7 7 0 1 1-6.32 4"
                stroke="#fff"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <polyline
                points="3 3 7 3 7 7"
                stroke="#fff"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        {title && title.trim() !== "" && (
          <div
            style={{
              marginTop: 20,
              height: 1,
              backgroundColor: "var(--vscode-editorWidget-border)",
              width: "80%",
              marginLeft: "auto",
              marginRight: "auto",
            }}
          />
        )}
        <ReactFlowProvider>
          <div
            style={{
              width: "100%",
              height: `${containerHeight}px`,
              position: "relative",
            }}
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
              style={{ width: "100%", height: "auto" }}
            ></ReactFlow>
          </div>
        </ReactFlowProvider>
      </>
    </div>
  );
};