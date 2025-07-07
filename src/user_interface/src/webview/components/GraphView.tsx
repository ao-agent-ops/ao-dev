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
import styles from './GraphView.module.css';

interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeUpdate: (nodeId: string, field: keyof GraphNode, value: string) => void;
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

  const handleNodeUpdate = useCallback(
    (nodeId: string, field: keyof GraphNode, value: string) => {
      onNodeUpdate(nodeId, field, value);
      sendNodeUpdate(nodeId, field, value);
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
      className={styles.container}
    >
      <div className={styles.header}>
        <div className={styles.headerSpacer} />
        <span className={styles.title}>Graph Title Placeholder</span>
        <button
          className={styles.restartButton}
          title="Restart"
          onClick={() => {
            // Remove alert for production
            sendMessage({ type: 'restart', id: Math.floor(Math.random() * 100000) });
          }}
        >
          {React.createElement('svg', {
            width: "20",
            height: "20",
            viewBox: "0 0 20 20",
            fill: "none",
            xmlns: "http://www.w3.org/2000/svg"
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
      <div className={styles.divider} />
      <ReactFlowProvider>
        <div
          className={styles.flowContainer}
          style={{ height: `${containerHeight}px` }}
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
          />
        </div>
      </ReactFlowProvider>
    </div>
  );
};