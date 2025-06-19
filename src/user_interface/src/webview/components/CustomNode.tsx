// src/webview/components/CustomNode.tsx
import React, { useEffect, useRef, useState } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { NODE_WIDTH, NODE_HEIGHT } from '../utils/nodeLayout';
import { GraphNode } from '../types';
import { NodePopover } from './NodePopover';
import { LabelEditor } from './LabelEditor';
import { sendNavigateToCode } from '../utils/messaging';
import { NODE_BORDER_WIDTH } from '../utils/layoutConstants';
import { useIsVsCodeDarkTheme } from '../utils/themeUtils';

declare const vscode: any;

// Define handle offset constants for consistency
const SIDE_HANDLE_OFFSET = 15; // pixels from center
const HANDLE_TARGET_POSITION = 50 - SIDE_HANDLE_OFFSET; // 35% from top
const HANDLE_SOURCE_POSITION = 50 + SIDE_HANDLE_OFFSET; // 65% from top

interface CustomNodeData extends GraphNode {
  onUpdate: (nodeId: string, field: string, value: string) => void;
  isHovered: boolean;
  isChild: boolean;
  isDimmed: boolean;
  setHoveredNodeId: (id: string | null) => void;
}

export const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({
  data,
  id,
  yPos,
}) => {
  const [showPopover, setShowPopover] = useState(false);
  const [isEditingLabel, setIsEditingLabel] = useState(false);
  const opacity = data.isDimmed ? 0.3 : 1;
  const enterTimeoutRef = useRef<number | null>(null);
  const leaveTimeoutRef = useRef<number | null>(null);

  const handleStyle: React.CSSProperties = {
    width: 8,
    height: 8,
    border: '2px solid #555',
    background: '#fff',
    opacity: 0, // Make handles invisible
  };

  // Style for side handles with vertical offset
  const leftTargetStyle: React.CSSProperties = {
    ...handleStyle,
    top: `${HANDLE_TARGET_POSITION}%`,
  };

  const leftSourceStyle: React.CSSProperties = {
    ...handleStyle,
    top: `${HANDLE_SOURCE_POSITION}%`,
  };

  const rightTargetStyle: React.CSSProperties = {
    ...handleStyle,
    top: `${HANDLE_TARGET_POSITION}%`,
  };

  const rightSourceStyle: React.CSSProperties = {
    ...handleStyle,
    top: `${HANDLE_SOURCE_POSITION}%`,
  };

  const handleAction = (action: string) => {
    switch (action) {
      case "editInput":
        vscode.postMessage({
          type: "showEditDialog",
          payload: {
            nodeId: id,
            field: "input",
            value: data.input,
            label: data.label,
          },
        });
        break;
      case "editOutput":
        vscode.postMessage({
          type: "showEditDialog",
          payload: {
            nodeId: id,
            field: "output",
            value: data.output,
            label: data.label,
          },
        });
        break;
      case "changeLabel":
        setIsEditingLabel(true);
        break;
      case "seeInCode":
        sendNavigateToCode(data.codeLocation);
        break;
    }
  };

  const handleLabelSave = (newLabel: string) => {
    data.onUpdate(id, "label", newLabel);
    setIsEditingLabel(false);
  };  

  const isDarkTheme = useIsVsCodeDarkTheme();
  
  return (
    <div
      style={{
        boxSizing: "border-box",
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        background: isDarkTheme ? "#3c3c3c" : "#F5F5F5",
        border: `${NODE_BORDER_WIDTH}px solid ${data.border_color}`, // Border color based on data.border_color
        borderRadius: 8,
        padding: 2,
        position: "relative",
        opacity: opacity,
        transition: "opacity 0.3s ease",
      }}
      onMouseEnter={() => {
        if (leaveTimeoutRef.current) {
          clearTimeout(leaveTimeoutRef.current);
          leaveTimeoutRef.current = null;
        }
        enterTimeoutRef.current = window.setTimeout(() => {
          data.setHoveredNodeId(id);
          setShowPopover(true);
        }, 150); // 150ms delay before showing the popover
      }}
      onMouseLeave={() => {
        if (enterTimeoutRef.current) {
          clearTimeout(enterTimeoutRef.current);
          enterTimeoutRef.current = null;
        }
        leaveTimeoutRef.current = window.setTimeout(() => {
          data.setHoveredNodeId(null);
          setShowPopover(false);
        }, 150); // 150ms delay for hiding the popover
      }}
    >
      {showPopover && !isEditingLabel && (
        <NodePopover
          onAction={handleAction}
          onMouseEnter={() => setShowPopover(true)}
          onMouseLeave={() => setShowPopover(false)}
          position={yPos < NODE_HEIGHT + 20 ? 'below' : 'above'}
        />
      )}
      {isEditingLabel && (
        <LabelEditor
          initialValue={data.label}
          onSave={handleLabelSave}
          onCancel={() => setIsEditingLabel(false)}
        />
      )}
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        style={handleStyle}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        style={handleStyle}
      />

      {/* Side handles */}
      <Handle
        type="target"
        position={Position.Left}
        id="left-target"
        style={leftTargetStyle}
      />
      <Handle
        type="source"
        position={Position.Left}
        id="left-source"
        style={leftSourceStyle}
      />
      <Handle
        type="target"
        position={Position.Right}
        id="right-target"
        style={rightTargetStyle}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right-source"
        style={rightSourceStyle}
      />

      {/* Label */}
      <div
        style={{
          fontSize: 12,
          fontWeight: "bold",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          opacity: isEditingLabel ? 0 : 1,
          color: data.isDimmed ? "#999999" : isDarkTheme ? "#fff" : "#303030",
          textAlign: "center",
          padding: "0 4px",
          wordBreak: "break-word",
          lineHeight: "1.2",
        }}
      >
        {data.label}
      </div>
    </div>
  );
};

// Export handle positions for edge routing
export { HANDLE_TARGET_POSITION, HANDLE_SOURCE_POSITION };
