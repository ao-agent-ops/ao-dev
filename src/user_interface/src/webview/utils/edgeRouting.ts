import { GraphEdge, BoundingBox, Point, RoutedEdge } from '../types';
import { NODE_WIDTH, NODE_HEIGHT } from './nodeLayout';

const EDGE_PADDING = 15;   // Minimum distance between edge and any node
const EDGE_SPACING = 15;   // How far apart parallel side-channels should step

// Handle offset constants (should match CustomNode.tsx)
const SIDE_HANDLE_OFFSET_RATIO = 0.15; // 15% offset from center

export function routeEdges(
  edges: GraphEdge[],
  nodePositions: Map<string, { x: number; y: number }>
): RoutedEdge[] {
  const nodeBounds = calculateNodeBounds(nodePositions);
  const routedEdges: RoutedEdge[] = [];
  // x → [y1,y2,y3,y4…] ranges already occupied by edges
  const verticalChannels = new Map<number, number[]>();

  edges.forEach(edge => {
    const sourceBounds = nodeBounds.get(edge.source);
    const targetBounds = nodeBounds.get(edge.target);
    
    // Skip edges where source or target node doesn't exist
    if (!sourceBounds || !targetBounds) {
      console.warn(`Skipping edge ${edge.id}: missing node bounds for source ${edge.source} or target ${edge.target}`);
      return;
    }

    // 1) try straight down
    let route = tryCase1_StraightDown(
      sourceBounds, targetBounds, nodeBounds,
      edge.source, edge.target
    );

    // 2) try two-corner (down → over → down)
    if (!route) {
      route = tryCase2_TwoCorners(
        sourceBounds, targetBounds, nodeBounds,
        verticalChannels,
        edge.source, edge.target
      );
    }

    // 3) try three-corner (side exit + hunt for a free channel)
    if (!route) {
      route = tryCase3_ThreeCorners(
        sourceBounds, targetBounds, nodeBounds,
        verticalChannels,
        edge.source, edge.target
      );
    }

    if (!route) {
      console.warn(` !!! ALL ROUTING FAILED for ${edge.source} -> ${edge.target}`);
    } else {
      routedEdges.push({
        ...edge,
        sourceHandle: route.sourceHandle,
        targetHandle: route.targetHandle,
        points: route.points
      });
    }
  });

  return routedEdges;
}

function calculateNodeBounds(positions: Map<string, { x: number; y: number }>): Map<string, BoundingBox> {
    const bounds = new Map<string, BoundingBox>();
    
    positions.forEach((pos, nodeId) => {
        bounds.set(nodeId, {
            x: pos.x,
            y: pos.y,
            width: NODE_WIDTH,
            height: NODE_HEIGHT
        });
    });    
    return bounds;
}

interface RouteResult {
    sourceHandle: string;
    targetHandle: string;
    points: Point[];
}

// Helper function to calculate handle Y position based on handle type
function getHandleY(bounds: BoundingBox, handleId: string): number {
    const centerY = bounds.y + bounds.height / 2;
    
    // Apply offset for side handles
    if (handleId.includes('-target')) {
        // Target handles are above center
        return centerY - (bounds.height * SIDE_HANDLE_OFFSET_RATIO);
    } else if (handleId.includes('-source')) {
        // Source handles are below center
        return centerY + (bounds.height * SIDE_HANDLE_OFFSET_RATIO);
    }
    
    // For top/bottom handles, use default positions
    if (handleId === 'top') {
        return bounds.y;
    } else if (handleId === 'bottom') {
        return bounds.y + bounds.height;
    }
    
    // Default to center
    return centerY;
}

// Case 1: Straight line from bottom to top (0 corners)
function tryCase1_StraightDown(
    source: BoundingBox,
    target: BoundingBox,
    allNodes: Map<string, BoundingBox>,
    sourceId: string,
    targetId: string
): RouteResult | null {
    // Check if target is directly below source
    const sourceCenterX = source.x + source.width / 2;
    const targetCenterX = target.x + target.width / 2;
    
    // Allow some tolerance for "directly below"
    if (Math.abs(sourceCenterX - targetCenterX) > 5) {
        return null;
    }
    
    // Check if target is below source
    if (target.y <= source.y + source.height) {
        return null;
    }
    
    const x = sourceCenterX;
    const startY = source.y + source.height;
    const endY = target.y;
    
    // Check for collisions along the vertical path
    const hasCollision = Array.from(allNodes.entries()).some(([nodeId, node]) => {
        if (nodeId === sourceId || nodeId === targetId) return false;
        
        // Check if the vertical line intersects with the node
        const intersects = x >= node.x - EDGE_PADDING &&
               x <= node.x + node.width + EDGE_PADDING &&
               startY <= node.y + node.height &&
               endY >= node.y;
               
        return intersects;
    });
    
    if (hasCollision) {
        return null;
    }
    
    return {
        sourceHandle: 'bottom',
        targetHandle: 'top',
        points: [
            { x, y: startY },
            { x, y: endY }
        ]
    };
}

// Case 2: Down, then horizontal, then down (2 corners)
function tryCase2_TwoCorners(
    source: BoundingBox,
    target: BoundingBox,
    allNodes: Map<string, BoundingBox>,
    verticalChannels: Map<number, number[]>,
    sourceId: string,
    targetId: string
): RouteResult | null {
    const sourceCenterX = source.x + source.width / 2;
    const targetCenterX = target.x + target.width / 2;
        
    // Determine direction (left or right)
    const goingRight = targetCenterX > sourceCenterX;
    
    // Calculate vertical drop point (midway between source bottom and target top)
    const dropY = source.y + source.height + (target.y - (source.y + source.height)) / 2;
    
    // Try to find a clear horizontal path
    const startX = sourceCenterX;
    const endX = targetCenterX;
        
    // Check for collisions along the path
    const points: Point[] = [
        { x: startX, y: source.y + source.height },
        { x: startX, y: dropY },
        { x: endX, y: dropY },
        { x: endX, y: target.y }
    ];
    
    // Check each segment for collisions
    const hasCollision = hasPathCollision(points, allNodes, [sourceId, targetId]);
    
    if (hasCollision) {
        return null;
    }
        
    // Record vertical channel usage
    recordVerticalChannel(verticalChannels, startX, source.y + source.height, dropY);
    recordVerticalChannel(verticalChannels, endX, dropY, target.y);
    
    return {
        sourceHandle: 'bottom',
        targetHandle: 'top',
        points
    };
}

// Case 3: Exit from side, go down, enter from same side (3 corners)
function tryCase3_ThreeCorners(
  source: BoundingBox,
  target: BoundingBox,
  allNodes: Map<string, BoundingBox>,
  verticalChannels: Map<number, number[]>,
  sourceId: string,
  targetId: string
): RouteResult | null {
  
  // Try both sides (left first, then right)
  for (const side of ['left', 'right'] as const) {    
    // Calculate Y positions with handle offsets
    const sourceHandle = `${side}-source`;
    const targetHandle = `${side}-target`;
    const sourceY = getHandleY(source, sourceHandle);
    const targetY = getHandleY(target, targetHandle);
    
    // "raw" X coordinate if no other edges existed
    const rawX = side === 'left'
      ? Math.min(source.x, target.x) - EDGE_PADDING * 2
      : Math.max(source.x + source.width, target.x + target.width) + EDGE_PADDING * 2;
    
    // now hunt up/down this channel for an *unused* X
    const routingX = findFreeChannelX(rawX, sourceY, targetY, verticalChannels);
    
    // build the 3-corner polyline
    const sourceX = side === 'left' ? source.x : source.x + source.width;
    const targetX = side === 'left' ? target.x : target.x + target.width;
    
    const points: Point[] = [
      { x: sourceX,  y: sourceY },
      { x: routingX, y: sourceY },
      { x: routingX, y: targetY },
      { x: targetX,  y: targetY }
    ];
    
    // collision test
    if (!hasPathCollision(points, allNodes, [sourceId, targetId])) {
      recordVerticalChannel(verticalChannels, routingX, sourceY, targetY);
      
      return {
        sourceHandle,
        targetHandle,
        points
      };
    }
  }
  
  // fallback to a single vertical segment
  return {
    sourceHandle: 'bottom',
    targetHandle: 'top',
    points: [
      { x: source.x + source.width/2, y: source.y + source.height },
      { x: target.x + target.width/2, y: target.y }
    ]
  };
}
  
function hasPathCollision(
    points: Point[],
    allNodes: Map<string, BoundingBox>,
    excludeNodeIds: string[]
): boolean {
    // Check each segment of the path
    for (let i = 0; i < points.length - 1; i++) {
        const start = points[i];
        const end = points[i + 1];
        
        // Check collision with each node
        for (const [nodeId, node] of allNodes.entries()) {
            if (excludeNodeIds.includes(nodeId)) continue;
            
            if (segmentIntersectsBox(start, end, node, EDGE_PADDING)) {
                return true;
            }
        }
    }
    
    return false;
}

function segmentIntersectsBox(
    start: Point,
    end: Point,
    box: BoundingBox,
    padding: number
): boolean {
    // Expand box by padding
    const expandedBox = {
        x: box.x - padding,
        y: box.y - padding,
        width: box.width + 2 * padding,
        height: box.height + 2 * padding
    };
    
    // Check if segment is horizontal or vertical
    if (start.x === end.x) {
        // Vertical segment
        const x = start.x;
        const minY = Math.min(start.y, end.y);
        const maxY = Math.max(start.y, end.y);
        
        const intersects = x >= expandedBox.x &&
               x <= expandedBox.x + expandedBox.width &&
               maxY >= expandedBox.y &&
               minY <= expandedBox.y + expandedBox.height;
        
        return intersects;
    } else {
        // Horizontal segment
        const y = start.y;
        const minX = Math.min(start.x, end.x);
        const maxX = Math.max(start.x, end.x);
        
        const intersects = y >= expandedBox.y &&
               y <= expandedBox.y + expandedBox.height &&
               maxX >= expandedBox.x &&
               minX <= expandedBox.x + expandedBox.width;
        
        return intersects;
    }
}

function recordVerticalChannel(
    channels: Map<number, number[]>,
    x: number,
    y1: number,
    y2: number
): void {
    const roundedX = Math.round(x);
    if (!channels.has(roundedX)) {
        channels.set(roundedX, []);
    }
    channels.get(roundedX)!.push(Math.min(y1, y2), Math.max(y1, y2));
}

function findFreeChannelX(
  desiredX: number,
  y1: number,
  y2: number,
  channels: Map<number, number[]>
): number {
  const deltas = [0, EDGE_SPACING, -EDGE_SPACING, 2*EDGE_SPACING, -2*EDGE_SPACING];
  
  for (const d of deltas) {
    const x = Math.round(desiredX + d);
    const used = channels.get(x) || [];
    // used = [a1,a2, a3,a4, …] meaning ranges [a1→a2], [a3→a4], …
    let overlap = false;
    
    for (let i = 0; i + 1 < used.length; i += 2) {
      const [ua, ub] = [used[i], used[i+1]];
      if (!(y2 < ua || y1 > ub)) {
        overlap = true;
        break;
      }
    }
    
    if (!overlap) {
      return x;
    }
  }
  
  // if all else fails, just return the original
  return Math.round(desiredX);
}