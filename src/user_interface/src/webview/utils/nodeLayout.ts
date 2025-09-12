import { GraphNode, GraphEdge } from '../types';
import { LayoutEngine } from './layoutEngine';

const NODE_WIDTH = 150;
const NODE_HEIGHT = 70;

// Create a single instance of the layout engine
const layoutEngine = new LayoutEngine();

export function calculateNodePositions(
    nodes: GraphNode[],
    edges: GraphEdge[],
    containerWidth: number
): Map<string, { x: number; y: number }> {
    // Use the layout engine
    const layout = layoutEngine.layoutGraph(nodes, edges, containerWidth);
    return layout.positions;
}

export { NODE_WIDTH, NODE_HEIGHT };