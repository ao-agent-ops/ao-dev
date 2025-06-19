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
import { sendNodeUpdate } from '../utils/messaging';

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
  const [isEditing, setIsEditing] = React.useState(false);
  
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

    const childNodeIds = new Set<string>();
    if (hoveredNodeId) {
      initialEdges.forEach((edge) => {
        if (edge.source === hoveredNodeId) {
          childNodeIds.add(edge.target);
        }
      });
    }

    const flowNodes: Node[] = initialNodes.map((node) => {
      const isHovered = node.id === hoveredNodeId;
      const isChild = childNodeIds.has(node.id);
      const isDimmed = hoveredNodeId !== null && !isHovered && !isChild;
      return {
        id: node.id,
        type: "custom",
        position: positions.get(node.id) || { x: 0, y: 0 },
        data: {
          ...node,
          onUpdate: handleNodeUpdate,
          isHovered,
          isChild,
          isDimmed,
          setHoveredNodeId,
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
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
        color: "#e0e0e0",
      },
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
    hoveredNodeId,
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
            textAlign: "center",
            width: "100%",
          }}
          onClick={() => setIsEditing(true)}
        >
          {isEditing ? (
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => setIsEditing(false)}
              autoFocus
              style={{
                fontWeight: "bold",
                fontSize: 18,
                textAlign: "center",
                width: "100%",
              }}
            />
          ) : (
            <span>{title}</span>
          )}
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
            <Controls />
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