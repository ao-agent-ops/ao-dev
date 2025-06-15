import React, { useCallback, useEffect, useState, useRef } from 'react';
import ReactFlow, {
    Node,
    Edge,
    useNodesState,
    useEdgesState,
    Controls,
    Background,
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
    onNodeUpdate 
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [containerWidth, setContainerWidth] = useState(400);

    const handleNodeUpdate = useCallback((nodeId: string, field: string, value: string) => {
        onNodeUpdate(nodeId, field, value);
        sendNodeUpdate(nodeId, field as any, value);
    }, [onNodeUpdate]);

    const updateLayout = useCallback(() => {
        if (initialNodes.length === 0) return;

        // Calculate node positions
        const positions = calculateNodePositions(initialNodes, initialEdges, containerWidth);
        
        // Route edges with collision avoidance
        const routedEdges = routeEdges(initialEdges, positions);

        // Create React Flow nodes
        const flowNodes: Node[] = initialNodes.map(node => ({
            id: node.id,
            type: 'custom',
            position: positions.get(node.id) || { x: 0, y: 0 },
            data: {
                ...node,
                onUpdate: handleNodeUpdate
            }
        }));

        // Create React Flow edges with custom routing
        const flowEdges: Edge[] = routedEdges.map(edge => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            sourceHandle: edge.sourceHandle,
            targetHandle: edge.targetHandle,
            type: 'custom',
            data: { points: edge.points },
            animated: false,
            markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 20,
                height: 20,
                color: '#e0e0e0',
            },
        }));

        setNodes(flowNodes);
        setEdges(flowEdges);
    }, [initialNodes, initialEdges, containerWidth, handleNodeUpdate, setNodes, setEdges]);

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
        
        // Use ResizeObserver for better performance
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
            width: '100%',
            height: '100%',
            overflowY: 'auto',   // <-- vertical scroll bar
            overflowX: 'hidden', // <-- disable horizontal overflow
            }}
        >
            <ReactFlowProvider>
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
                    panOnDrag={true}
                    zoomOnScroll={false}
                    zoomOnPinch={true}
                    zoomOnDoubleClick={false}
                    panOnScroll={false}
                    preventScrolling={false}
                    style={{ width: '100%', height: 'auto' }}
                >
                    <Background />
                </ReactFlow>
            </ReactFlowProvider>
        </div>
    );
};