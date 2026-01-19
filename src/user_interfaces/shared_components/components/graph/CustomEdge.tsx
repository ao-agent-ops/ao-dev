// CustomEdge.tsx
import React from 'react';
import { EdgeProps, getSmoothStepPath } from 'reactflow';
import { Point } from '../../types';
import { NODE_BORDER_WIDTH } from '../../utils/layoutConstants';

interface CustomEdgeData {
  points?: Point[];
  color?: string;
}

export const CustomEdge: React.FC<EdgeProps<CustomEdgeData>> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  let d: string;

  if (data?.points && data.points.length >= 2) {
    // force‐snap endpoints to the real handle centers
    const pts = [
      { x: data.points[0].x, y: data.points[0].y },
      ...data.points.slice(1, -1),
      {
        x: data.points[data.points.length - 1].x,
        y: data.points[data.points.length - 1].y,
      },
    ];

    const len = pts.length;
    const p1 = pts[len - 2];
    const p2 = pts[len - 1];
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist > 0) {
      const factor = (dist - NODE_BORDER_WIDTH) / dist;
      pts[len - 1] = {
        x: p1.x + dx * factor,
        y: p1.y + dy * factor,
      };
    }
    d = pts.reduce((acc, p, i) => (i === 0 ? `M ${p.x},${p.y}` : `${acc} L ${p.x},${p.y}`), '');
  } else {
    // fallback to the built-in smooth path
    [d] = getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      borderRadius: 8,
    });
  }

  // All edges are white
  const stroke = '#FFFFFF';

  const markerId = `arrow-${id}`;

  return (
    <svg style={{ overflow: 'visible', position: 'absolute' }}>
      <defs>
        <marker
          id={markerId}
          markerWidth="6"
          markerHeight="6"
          refX="5"
          refY="3"
          orient="auto"
          markerUnits="userSpaceOnUse"
        >
          <polygon
            points="0,0 6,3 0,6"
            fill={stroke}
          />
        </marker>
      </defs>
      <path
        id={id}
        className="react-flow__edge-path"
        d={d}
        markerEnd={`url(#${markerId})`}
        style={{ stroke, strokeWidth: 1, fill: 'none' }}
      />
    </svg>
  );
};
