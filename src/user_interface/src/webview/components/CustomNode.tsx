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
  attachments: any;
  onUpdate: (nodeId: string, field: string, value: string) => void;
  session_id?: string;
}

export const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({
  data,
  id,
  yPos,
}) => {
  const [showPopover, setShowPopover] = useState(false);
  const [isEditingLabel, setIsEditingLabel] = useState(false);
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
            session_id: data.session_id, // include session_id
            attachments: data.attachments,
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
            session_id: data.session_id, // include session_id
            attachments: data.attachments,
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
  
  const nodeRef = useRef<HTMLDivElement>(null);
  const [popoverCoords, setPopoverCoords] = useState<{top: number, left: number} | null>(null);

  useEffect(() => {
    if (showPopover && nodeRef.current) {
      const rect = nodeRef.current.getBoundingClientRect();
      // Calculate the position so that the popover does not cover the node
      let top, left;
      const POPOVER_HEIGHT = 70; // estimated height of the popover
      const SEPARATION = 2; // Extra space around the popover
      const BOTTOM_SEPARATION = 45; // Extra space below the node
      const HORIZONTAL_OFFSET = 0; // Can you adjust this if needed

      // Adjust the popover position based on the node's position
      if (yPos < NODE_HEIGHT + 20) {
        // Popover Below the node
        top = rect.bottom + window.scrollY + SEPARATION;
      } else {
        // Popover Above the node
        top = rect.top + window.scrollY - BOTTOM_SEPARATION - POPOVER_HEIGHT;
      }
      left = rect.left + rect.width / 2 + window.scrollX + HORIZONTAL_OFFSET;
      setPopoverCoords({ top, left });
    } else if (!showPopover) {
      setPopoverCoords(null);
    }
  }, [showPopover, yPos]);

  return (
    <div
      ref={nodeRef}
      style={{
        boxSizing: "border-box",
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        background: isDarkTheme ? "#3c3c3c" : "#F5F5F5",
        border: `${NODE_BORDER_WIDTH}px solid ${data.border_color}`,
        borderRadius: 8,
        padding: 2,
        position: "relative",
      }}
      onMouseEnter={() => {
        if (leaveTimeoutRef.current) {
          clearTimeout(leaveTimeoutRef.current);
          leaveTimeoutRef.current = null;
        }
        enterTimeoutRef.current = window.setTimeout(() => {
          setShowPopover(true);
        }, 150);
      }}
      onMouseLeave={() => {
        if (enterTimeoutRef.current) {
          clearTimeout(enterTimeoutRef.current);
          enterTimeoutRef.current = null;
        }
        leaveTimeoutRef.current = window.setTimeout(() => {
          setShowPopover(false);
        }, 150);
      }}
    >
      {showPopover && !isEditingLabel && popoverCoords && (
        <NodePopover
          onAction={handleAction}
          onMouseEnter={() => setShowPopover(true)}
          onMouseLeave={() => setShowPopover(false)}
          position={yPos < NODE_HEIGHT + 20 ? 'below' : 'above'}
          top={popoverCoords.top}
          left={popoverCoords.left}
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
          color: isDarkTheme ? "#fff" : "#303030",
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
