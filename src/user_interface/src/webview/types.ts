export interface GraphNode {
    id: string;
    input: string;
    output: string;
    codeLocation: string;
    label: string;
    position?: { x: number; y: number };
    border_color?: string;
    attachments?: any[];
}

export interface GraphEdge {
    id: string;
    source: string;
    target: string;
    type?: string;
    sourceHandle?: string;
    targetHandle?: string;
}

export interface Point {
    x: number;
    y: number;
}

export interface BoundingBox {
    x: number;
    y: number;
    width: number;
    height: number;
}

export interface RoutedEdge extends GraphEdge {
    points: Point[];
    sourceHandle: string;
    targetHandle: string;
}

export interface Message {
    type: string;
    payload?: any;
}

export interface NodeUpdateMessage extends Message {
    type: 'updateNode';
    payload: {
        nodeId: string;
        field: keyof GraphNode;
        value: string;
    };
}

export interface PopoverAction {
    id: string;
    label: string;
    icon?: string;
}

export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export interface ProcessInfo {
    session_id: string;
    title?: string;
    status: string;
    timestamp?: string;
}