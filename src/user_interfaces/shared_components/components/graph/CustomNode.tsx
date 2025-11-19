// src/webview/components/CustomNode.tsx
import React, { useEffect, useRef, useState } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { GraphNode } from '../../types';
import { NodePopover } from './NodePopover';
import { LabelEditor } from '../LabelEditor';
import { NODE_WIDTH, NODE_HEIGHT, NODE_BORDER_WIDTH } from '../../utils/layoutConstants';
import { MessageSender } from '../../types/MessageSender';

// Define handle offset constants for consistency
const SIDE_HANDLE_OFFSET = 15; // pixels from center
const HANDLE_TARGET_POSITION = 50 - SIDE_HANDLE_OFFSET; // 35% from top
const HANDLE_SOURCE_POSITION = 50 + SIDE_HANDLE_OFFSET; // 65% from top

interface CustomNodeData extends GraphNode {
  attachments: any;
  onUpdate: (nodeId: string, field: string, value: string) => void;
  session_id?: string;
  messageSender: MessageSender;
  isDarkTheme?: boolean;
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

  // Helper to create side handle styles with vertical offset
  const createSideHandleStyle = (position: number): React.CSSProperties => ({
    ...handleStyle,
    top: `${position}%`,
  });

  const leftTargetStyle = createSideHandleStyle(HANDLE_TARGET_POSITION);
  const leftSourceStyle = createSideHandleStyle(HANDLE_SOURCE_POSITION);
  const rightTargetStyle = createSideHandleStyle(HANDLE_TARGET_POSITION);
  const rightSourceStyle = createSideHandleStyle(HANDLE_SOURCE_POSITION);

  const handleAction = async (action: string) => {
    switch (action) {
      case "editInput":
        // Track node input view through MessageSender
        data.messageSender.send({
          type: "trackNodeInputView",
          payload: {
            id,
            input: data.input || '',
            session_id: data.session_id || '',
            label: data.label || ''
          }
        });

        // Request to show node edit modal
        data.messageSender.send({
          type: "showNodeEditModal",
          payload: {
            nodeId: id,
            field: "input",
            value: data.input,
            label: data.label || "Node",
          }
        });
        break;
      case "editOutput":
        // Track node output view through MessageSender
        data.messageSender.send({
          type: "trackNodeOutputView",
          payload: {
            id,
            output: data.output || '',
            session_id: data.session_id || '',
            label: data.label || ''
          }
        });
        
        // Request to show node edit modal
        data.messageSender.send({
          type: "showNodeEditModal",
          payload: {
            nodeId: id,
            field: "output",
            value: data.output,
            label: data.label || "Node",
          }
        });
        break;
      case "changeLabel":
        setIsEditingLabel(true);
        break;
      // case "seeInCode":
      //   data.messageSender.send({
      //     type: "navigateToCode",
      //     payload: { codeLocation: data.codeLocation }
      //   });
      //   break;
    }
  };

  const handleLabelSave = (newLabel: string) => {
    data.onUpdate(id, "label", newLabel);
    setIsEditingLabel(false);
  };  

  const isDarkTheme = data.isDarkTheme ?? false;
  
  const nodeRef = useRef<HTMLDivElement>(null);
  const [popoverCoords, setPopoverCoords] = useState<{top: number, left: number} | null>(null);

  useEffect(() => {
    if (showPopover && nodeRef.current) {
      const rect = nodeRef.current.getBoundingClientRect();
      // Always position popover below the node, centered precisely
      const top = rect.bottom + window.scrollY;
      // Calculate exact center point of the node, with slight left adjustment
      const centerX = rect.left + (rect.width / 2) - 3; // Move 3px to the left
      const left = centerX + window.scrollX;
      
      // Debug logging to check values
      console.log('Node rect:', { left: rect.left, width: rect.width, centerX });
      console.log('Popover position:', { top, left });
      
      setPopoverCoords({ top, left });
    } else if (!showPopover) {
      setPopoverCoords(null);
    }
  }, [showPopover]);

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
          position="below"
          top={popoverCoords.top}
          left={popoverCoords.left}
          isDarkTheme={isDarkTheme}
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

      {/* Side handles - offset positions */}
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

      {/* Centered side handles for single arrows */}
      <Handle
        type="target"
        position={Position.Left}
        id="left-center"
        style={{...handleStyle, top: '50%'}}
      />
      <Handle
        type="source"
        position={Position.Left}
        id="left-center-source"
        style={{...handleStyle, top: '50%'}}
      />
      <Handle
        type="target"
        position={Position.Right}
        id="right-center"
        style={{...handleStyle, top: '50%'}}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right-center-source"
        style={{...handleStyle, top: '50%'}}
      />

      {/* Label */}
      <div
        style={{
          fontSize: "11px",
          fontWeight: "600",
          fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          opacity: isEditingLabel ? 0 : 1,
          color: "var(--vscode-foreground, #303030)",
          textAlign: "center",
          padding: "0 4px",
          wordBreak: "break-word",
          lineHeight: "1.3",
        }}
      >
        {data.label}
      </div>
    </div>
  );
};

// Export handle positions for edge routing
export { HANDLE_TARGET_POSITION, HANDLE_SOURCE_POSITION };
