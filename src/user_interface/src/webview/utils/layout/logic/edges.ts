import { LayoutNode, BandInfo, RoutedEdge } from '../core/types';
import { createDirectPath } from '../paths/direct';
import { createBandPath, createBandPathWithHorizontalConnector } from '../paths/bands';
import { BAND_ENTRY_STAGGER_STEP, BAND_ENTRY_STAGGER_CLAMP } from '../core/constants';
import { wouldDirectLineCrossNodes, hasNodesBetweenInVisualLayers } from './collisions';

export function calculateEdges(nodes: LayoutNode[], bands: BandInfo[], containerWidth: number, layerSpacing: number, nodeHeight: number, nodeSpacing: number): RoutedEdge[] {
  const edges: RoutedEdge[] = [];
  if (!nodes.length) return edges;
  const maxNodesPerRow = Math.max(1, Math.floor((containerWidth - nodeSpacing) / ( (nodes[0]?.width || 0) + nodeSpacing)));
  const isSingleColumn = maxNodesPerRow === 1;
  // Precompute counts of band edges entering each target to stagger entries
  const bandEntriesPerTarget = new Map<string, number>();
  const bandEntryIndex = new Map<string, number>();

  nodes.forEach(n => {
    n.children.forEach(childId => {
      const target = nodes.find(x => x.id === childId);
      if (!target) return;
      const isDirect = target.layer === n.layer! + 1;
      // We'll stagger only band edges (non-direct or forced band)
      if (!isDirect) {
        bandEntriesPerTarget.set(childId, (bandEntriesPerTarget.get(childId) || 0) + 1);
      }
    });
  });

  nodes.forEach(source => {
    source.children.forEach((childId, idx) => {
      const target = nodes.find(n => n.id === childId);
      if (!target || source.x == null || source.y == null || target.x == null || target.y == null) return;
  const edge: RoutedEdge = { id: `${source.id}-${childId}`, source: source.id, target: childId, type: 'direct', points: [], sourceHandle: 'bottom', targetHandle: 'top' };
      const isDirect = target.layer === source.layer! + 1;
      if (isDirect) {
        const hasNodesInBetween = hasNodesBetweenInVisualLayers(source, target, nodes, layerSpacing);
        const wouldCross = wouldDirectLineCrossNodes(source, target, nodes);
        let useBand = false;
        if (isSingleColumn) {
          const nodesBetween = nodes.filter(n => n.y! > source.y! + source.height! && n.y! + n.height! < target.y!);
          useBand = nodesBetween.length > 0 || idx > 0;
        } else {
          useBand = wouldCross || hasNodesInBetween;
        }
        if (useBand) {
          edge.type = 'band';
          edge.band = source.band;
          const band = bands.find(b => b.name === source.band);
          if (band) {
            const needsHorizontal = !isSingleColumn && source.children.length > 1 && (wouldCross || hasNodesInBetween);
            const childNodes = source.children.map(cid => nodes.find(n => n.id === cid)).filter(Boolean) as LayoutNode[];
            // Compute a small offset for multiple band entries into the same target
            let entryOffset = 0;
            if (!isDirect) {
              const total = bandEntriesPerTarget.get(childId) || 0;
              const seen = bandEntryIndex.get(childId) || 0;
              if (total > 1) {
                // Stagger across ~[-6, +6] px depending on index
                const span = Math.min(BAND_ENTRY_STAGGER_CLAMP * 2, Math.max(BAND_ENTRY_STAGGER_STEP, (total - 1) * BAND_ENTRY_STAGGER_STEP));
                const step = total > 1 ? span / (total - 1) : 0;
                entryOffset = -span / 2 + seen * step;
              }
              bandEntryIndex.set(childId, seen + 1);
            }
            edge.points = needsHorizontal
              ? createBandPathWithHorizontalConnector(source, target, band.x, band.side, childNodes, entryOffset)
              : createBandPath(source, target, band.x, band.side, entryOffset);
            edge.sourceHandle = band.side === 'right' ? 'right-source' : 'left-source';
            // Always target the top handle when using band edges so the connector enters above center
            edge.targetHandle = needsHorizontal ? 'top' : 'top';
            edge.color = band.color;
          }
        } else {
          edge.points = createDirectPath(source, target, nodeHeight);
        }
      } else {
        edge.type = 'band';
        edge.band = source.band;
        const band = bands.find(b => b.name === source.band);
        if (band) {
          // Stagger entries for non-direct (skip-layer) edges
          const total = bandEntriesPerTarget.get(childId) || 0;
          const seen = bandEntryIndex.get(childId) || 0;
          const span = total > 1 ? Math.min(BAND_ENTRY_STAGGER_CLAMP * 2, Math.max(BAND_ENTRY_STAGGER_STEP, (total - 1) * BAND_ENTRY_STAGGER_STEP)) : 0;
          const step = total > 1 ? span / (total - 1) : 0;
          const entryOffset = total > 1 ? (-span / 2 + seen * step) : 0;
          bandEntryIndex.set(childId, seen + 1);
          edge.points = createBandPath(source, target, band.x, band.side, entryOffset);
          edge.sourceHandle = band.side === 'right' ? 'right-source' : 'left-source';
          // Always target the top handle for band edges
          edge.targetHandle = 'top';
          edge.color = band.color;
        }
      }
      if (edge.points.length) edges.push(edge);
    });
  });
  return edges;
}
