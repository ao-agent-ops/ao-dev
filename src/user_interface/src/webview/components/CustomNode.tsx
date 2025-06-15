// src/webview/components/CustomNode.tsx
import React, { useState } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { NODE_WIDTH, NODE_HEIGHT } from '../utils/nodeLayout';
import { GraphNode } from '../types';
import { NodePopover } from './NodePopover';
import { LabelEditor } from './LabelEditor';
import { sendNavigateToCode } from '../utils/messaging';

declare const vscode: any;

// Define handle offset constants for consistency
const SIDE_HANDLE_OFFSET = 15; // pixels from center
const HANDLE_TARGET_POSITION = 50 - SIDE_HANDLE_OFFSET; // 35% from top
const HANDLE_SOURCE_POSITION = 50 + SIDE_HANDLE_OFFSET; // 65% from top

interface CustomNodeData extends GraphNode {
  onUpdate: (nodeId: string, field: string, value: string) => void;
}

export const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({ data, id }) => {
  const [showPopover, setShowPopover] = useState(false);
  const [isEditingLabel, setIsEditingLabel] = useState(false);

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
      case 'editInput':
        vscode.postMessage({
          type: 'showEditDialog',
          payload: {
            nodeId: id,
            field: 'input',
            value: data.input,
            label: data.label
          }
        });
        break;
      case 'editOutput':
        vscode.postMessage({
          type: 'showEditDialog',
          payload: {
            nodeId: id,
            field: 'output',
            value: data.output,
            label: data.label
          }
        });
        break;
      case 'changeLabel':
        setIsEditingLabel(true);
        break;
      case 'seeInCode':
        sendNavigateToCode(data.codeLocation);
        break;
    }
  };

  const handleLabelSave = (newLabel: string) => {
    data.onUpdate(id, 'label', newLabel);
    setIsEditingLabel(false);
  };

  return (
    <div
      style={{
        boxSizing: 'border-box',
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        background: '#f5f5f5', // Light grey background
        border: '2px solid #e0e0e0', // Light grey border
        borderRadius: 8,
        padding: 10,
        position: 'relative',
      }}
      onMouseEnter={() => setShowPopover(true)}
      onMouseLeave={() => setShowPopover(false)}
    >
      {showPopover && !isEditingLabel && (
        <NodePopover
          onAction={handleAction}
          onMouseEnter={() => setShowPopover(true)}
          onMouseLeave={() => setShowPopover(false)}
        />
      )}
      {isEditingLabel && (
        <LabelEditor
          initialValue={data.label}
          onSave={handleLabelSave}
          onCancel={() => setIsEditingLabel(false)}
        />
      )}
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />
      
      {/* Side handles with vertical offsets */}
      <Handle type="target" position={Position.Left} id="left-target" style={leftTargetStyle} />
      <Handle type="source" position={Position.Left} id="left-source" style={leftSourceStyle} />
      <Handle type="target" position={Position.Right} id="right-target" style={rightTargetStyle} />
      <Handle type="source" position={Position.Right} id="right-source" style={rightSourceStyle} />
      
      {/* Node content - only showing label */}
      <div style={{ 
        fontSize: 12, 
        fontWeight: 'bold',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        opacity: isEditingLabel ? 0 : 1,
        color: '#000000', // Black text
        textAlign: 'center',
        padding: '0 4px',
        wordBreak: 'break-word',
        lineHeight: '1.2'
      }}>
        {data.label}
      </div>
    </div>
  );
};

// Export the handle positions for use in edge routing
export { HANDLE_TARGET_POSITION, HANDLE_SOURCE_POSITION };