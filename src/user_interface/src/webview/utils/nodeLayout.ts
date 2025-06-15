import { GraphNode, GraphEdge } from '../types';

const NODE_WIDTH = 150;
const NODE_HEIGHT = 100;
const NODE_SPACING_H = 30;
const NODE_SPACING_V = 80; // Increased for better edge routing

interface NodeInfo {
    id: string;
    level: number;
    parents: string[];
    children: string[];
}

export function calculateNodePositions(
    nodes: GraphNode[],
    edges: GraphEdge[],
    containerWidth: number
): Map<string, { x: number; y: number }> {
    const nodeMap = new Map<string, NodeInfo>();
    
    // Initialize node info
    nodes.forEach(node => {
        nodeMap.set(node.id, {
            id: node.id,
            level: -1,
            parents: [],
            children: []
        });
    });
    
    // Build parent-child relationships
    edges.forEach(edge => {
        const sourceNode = nodeMap.get(edge.source);
        const targetNode = nodeMap.get(edge.target);
        if (sourceNode && targetNode) {
            sourceNode.children.push(edge.target);
            targetNode.parents.push(edge.source);
        }
    });
    
    // Find root nodes and assign levels using BFS
    const rootNodes = Array.from(nodeMap.values()).filter(n => n.parents.length === 0);
    const queue: { id: string; level: number }[] = rootNodes.map(r => ({ id: r.id, level: 0 }));
    
    while (queue.length > 0) {
        const { id, level } = queue.shift()!;
        const node = nodeMap.get(id);
        if (!node || node.level !== -1) continue;
        
        node.level = level;
        node.children.forEach(childId => {
            queue.push({ id: childId, level: level + 1 });
        });
    }
    
    // Group nodes by level
    const levelGroups = new Map<number, NodeInfo[]>();
    nodeMap.forEach(node => {
        if (node.level === -1) return; // Skip unconnected nodes
        
        if (!levelGroups.has(node.level)) {
            levelGroups.set(node.level, []);
        }
        levelGroups.get(node.level)!.push(node);
    });
    
    // Calculate nodes per row based on container width
    const nodesPerRow = Math.max(1, Math.floor((containerWidth - NODE_SPACING_H) / (NODE_WIDTH + NODE_SPACING_H)));
    
    // Position nodes
    const positions = new Map<string, { x: number; y: number }>();
    let currentY = NODE_SPACING_V;
    
    // Sort levels
    const sortedLevels = Array.from(levelGroups.keys()).sort((a, b) => a - b);
    
    sortedLevels.forEach(level => {
        const nodesInLevel = levelGroups.get(level)!;
        
        // Group nodes by their first parent to keep families together
        const familyGroups = new Map<string, NodeInfo[]>();
        const orphans: NodeInfo[] = [];
        
        nodesInLevel.forEach(node => {
            if (node.parents.length > 0) {
                const firstParent = node.parents[0];
                if (!familyGroups.has(firstParent)) {
                    familyGroups.set(firstParent, []);
                }
                familyGroups.get(firstParent)!.push(node);
            } else {
                orphans.push(node);
            }
        });
        
        // Flatten family groups into a single array, keeping families together
        const orderedNodes: NodeInfo[] = [];
        
        // Sort families by their parent's position if available
        const sortedFamilies = Array.from(familyGroups.entries()).sort((a, b) => {
            const posA = positions.get(a[0]);
            const posB = positions.get(b[0]);
            if (posA && posB) {
                return posA.x - posB.x;
            }
            return a[0].localeCompare(b[0]);
        });
        
        sortedFamilies.forEach(([_, children]) => {
            // Sort children within family for consistency
            children.sort((a, b) => a.id.localeCompare(b.id));
            orderedNodes.push(...children);
        });
        
        // Add orphans at the end
        orphans.sort((a, b) => a.id.localeCompare(b.id));
        orderedNodes.push(...orphans);
        
        // Calculate rows needed for this level
        const rowsNeeded = Math.ceil(orderedNodes.length / nodesPerRow);
        
        // Position each node
        orderedNodes.forEach((node, index) => {
            const row = Math.floor(index / nodesPerRow);
            const col = index % nodesPerRow;
            
            // Center the last row if it's not full
            let xOffset = 0;
            if (row === rowsNeeded - 1) {
                const nodesInLastRow = orderedNodes.length - (row * nodesPerRow);
                if (nodesInLastRow < nodesPerRow) {
                    xOffset = ((nodesPerRow - nodesInLastRow) * (NODE_WIDTH + NODE_SPACING_H)) / 2;
                }
            }
            
            const x = NODE_SPACING_H + col * (NODE_WIDTH + NODE_SPACING_H) + xOffset;
            const y = currentY + row * (NODE_HEIGHT + NODE_SPACING_V);
            
            positions.set(node.id, { x, y });
        });
        
        // Update Y position for next level
        currentY += rowsNeeded * (NODE_HEIGHT + NODE_SPACING_V) + NODE_SPACING_V;
    });
    
    // Handle any unconnected nodes
    const unconnectedNodes = nodes.filter(node => !positions.has(node.id));
    if (unconnectedNodes.length > 0) {
        unconnectedNodes.forEach((node, index) => {
            const row = Math.floor(index / nodesPerRow);
            const col = index % nodesPerRow;
            const x = NODE_SPACING_H + col * (NODE_WIDTH + NODE_SPACING_H);
            const y = currentY + row * (NODE_HEIGHT + NODE_SPACING_V);
            positions.set(node.id, { x, y });
        });
    }
    
    return positions;
}

export { NODE_WIDTH, NODE_HEIGHT };