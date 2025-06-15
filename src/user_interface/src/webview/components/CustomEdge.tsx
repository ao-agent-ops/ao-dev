// CustomEdge.tsx
import React from 'react';
import { EdgeProps, getSmoothStepPath } from 'reactflow';
import { Point } from '../types';

interface CustomEdgeData {
  points?: Point[];
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
  markerEnd,
}) => {
  let d: string;

  if (data?.points && data.points.length >= 2) {
    // force‐snap endpoints to the real handle centers
    const pts = [
      { x: sourceX, y: sourceY },
      ...data.points.slice(1, -1),
      { x: targetX, y: targetY },
    ];

    d = pts.reduce((acc, p, i) =>
      i === 0
        ? `M ${p.x},${p.y}`
        : `${acc} L ${p.x},${p.y}`,
      ''
    );
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

  return (
    <path
      id={id}
      className="react-flow__edge-path"
      d={d}
      markerEnd={markerEnd}
      style={{ stroke: '#e0e0e0', strokeWidth: 2, fill: 'none' }}
    />
  );
};
