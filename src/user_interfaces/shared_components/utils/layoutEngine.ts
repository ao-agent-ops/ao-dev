import { GraphNode, GraphEdge, LayerInfo, GraphLayout, LayoutNode } from '../types';
import { applyCenterBandCascade } from './layout/logic/collisions';
import { convertToLayoutNodes } from './layout/core/convert';
import { calculateLogicalLayers } from './layout/logic/layers';
import { calculateVisualLayers } from './layout/logic/visualLayers';
import { calculateEdges } from './layout/logic/edges';
import { calculateDimensions } from './layout/logic/dimensions';
import { NODE_WIDTH, NODE_HEIGHT, LAYER_SPACING, NODE_SPACING, BAND_SPACING } from './layoutConstants';
import { calculateBands as calculateBandsMod } from './layout/logic/bandsCalc';

export class LayoutEngine {
  private nodeWidth = NODE_WIDTH;
  private nodeHeight = NODE_HEIGHT;
  private layerSpacing = LAYER_SPACING;
  private nodeSpacing = NODE_SPACING;
  private bandSpacing = BAND_SPACING;

  public layoutGraph(nodes: GraphNode[], edges: GraphEdge[], containerWidth?: number): GraphLayout {
    // Set default container width
    const width = containerWidth || 800; // Default fallback

    // Convert workflow-extension data to LayoutEngine format
    const LayoutNodes = this.convertToLayoutEngineFormat(nodes, edges);

    // Apply Graph layout algorithm
    const layers = this.calculateLayers(LayoutNodes);
  const visualLayers = calculateVisualLayers(layers, width, { nodeWidth: this.nodeWidth, nodeHeight: this.nodeHeight, layerSpacing: this.layerSpacing, nodeSpacing: this.nodeSpacing });

  // NEW (modular): cascade drop for internal nodes with skip-layer children
  applyCenterBandCascade(visualLayers, width, this.nodeWidth, this.nodeHeight, this.nodeSpacing, this.layerSpacing);

  const bands = calculateBandsMod(LayoutNodes, visualLayers, { nodeWidth: this.nodeWidth, nodeHeight: this.nodeHeight, nodeSpacing: this.nodeSpacing, layerSpacing: this.layerSpacing, bandSpacing: this.bandSpacing, containerWidth: width });
  const routedEdges = calculateEdges(LayoutNodes, bands, width, this.layerSpacing, this.nodeHeight, this.nodeSpacing);
  const { width: totalWidth, height } = calculateDimensions(visualLayers, bands);

    // Convert back to workflow-extension format
    const positions = new Map<string, { x: number; y: number }>();
    LayoutNodes.forEach(node => {
      // Validate node position before adding
      if (node.x !== undefined && node.y !== undefined &&
        !isNaN(node.x) && !isNaN(node.y) &&
        isFinite(node.x) && isFinite(node.y)) {
        positions.set(node.id, { x: node.x, y: node.y });
      } else {
        // Fallback position if calculation failed
        console.warn(`Invalid position for node ${node.id}:`, { x: node.x, y: node.y });
        positions.set(node.id, { x: 0, y: 0 });
      }
    });

    return {
      positions,
      edges: routedEdges,
      width: totalWidth,
      height
    };
  }

  private convertToLayoutEngineFormat(nodes: GraphNode[], edges: GraphEdge[]): LayoutNode[] {
    return convertToLayoutNodes(nodes, edges);
  }
  private calculateLayers(nodes: LayoutNode[]): LayerInfo[] {
    return calculateLogicalLayers(nodes);
  }
}