import React, { useState, useEffect } from 'react';
import { GraphView } from './graph/GraphView';
import { GraphData, ProcessInfo } from '../types';
import { MessageSender } from '../types/MessageSender';
import { WorkflowRunDetailsPanel } from './experiment/WorkflowRunDetailsPanel';
import { NodeEditModal } from './modals/NodeEditModal';

interface GraphTabAppProps {
  experiment: ProcessInfo | null;
  graphData: GraphData | null;
  sessionId: string | null;
  messageSender: MessageSender;
  isDarkTheme: boolean;
  onNodeUpdate: (nodeId: string, field: string, value: string, sessionId?: string, attachments?: any) => void;
}

export const GraphTabApp: React.FC<GraphTabAppProps> = ({
  experiment,
  graphData,
  sessionId,
  messageSender,
  isDarkTheme,
  onNodeUpdate,
}) => {
  const [isGraphReady, setIsGraphReady] = useState(false);
  const [showNodeEditModal, setShowNodeEditModal] = useState(false);
  const [nodeEditData, setNodeEditData] = useState<{ nodeId: string; field: 'input' | 'output'; label: string; value: string } | null>(null);

  // Reset graph ready state when graph data changes and set a short delay
  useEffect(() => {
    if (graphData) {
      setIsGraphReady(false);
      // Use a shorter, more reasonable delay
      const timeout = setTimeout(() => {
        setIsGraphReady(true);
      }, 100); // Much shorter delay

      return () => clearTimeout(timeout);
    }
  }, [graphData]);

  // Listen for showNodeEditModal messages from messageSender
  useEffect(() => {
    const handleShowNodeEditModal = (event: CustomEvent) => {
      const { nodeId, field, label, value } = event.detail;
      setNodeEditData({ nodeId, field, label, value });
      setShowNodeEditModal(true);
    };

    window.addEventListener('show-node-edit-modal', handleShowNodeEditModal as EventListener);

    return () => {
      window.removeEventListener('show-node-edit-modal', handleShowNodeEditModal as EventListener);
    };
  }, []);

  if (!experiment || !sessionId) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: isDarkTheme ? "#252525" : "#F0F0F0",
          color: isDarkTheme ? "#FFFFFF" : "#000000"
        }}
      >
        {/* Empty state - could add a message here if needed */}
      </div>
    );
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "row",
        background: isDarkTheme ? "#252525" : "#F0F0F0",
      }}
    >
      {/* Graph View */}
      {graphData && (
        <div style={{ flex: 1, overflow: "auto", position: "relative", minWidth: 0 }}>
          {/* Loading overlay */}
          {!isGraphReady && (
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: isDarkTheme ? "#252525" : "#F0F0F0",
                zIndex: 1000,
              }}
            />
          )}

          {/* Graph (always rendered, but hidden until ready) */}
          <div
            style={{
              width: "100%",
              height: "100%",
              visibility: isGraphReady ? "visible" : "hidden"
            }}
          >
            <GraphView
              nodes={graphData.nodes || []}
              edges={graphData.edges || []}
              onNodeUpdate={(nodeId, field, value) => {
                const nodes = graphData.nodes || [];
                const node = nodes.find((n: any) => n.id === nodeId);
                const attachments = node?.attachments || undefined;
                onNodeUpdate(nodeId, field, value, sessionId, attachments);
              }}
              session_id={sessionId}
              experiment={experiment}
              messageSender={messageSender}
              isDarkTheme={isDarkTheme}
              metadataPanel={experiment ? (
                <WorkflowRunDetailsPanel
                  runName={experiment.run_name || experiment.session_id}
                  result={experiment.result || ''}
                  notes={experiment.notes || ''}
                  log={experiment.log || ''}
                  sessionId={sessionId || ''}
                  isDarkTheme={isDarkTheme}
                  messageSender={messageSender}
                />
              ) : undefined}
            />
          </div>
        </div>
      )}

      {/* Node Edit Modal */}
      {showNodeEditModal && nodeEditData && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10001,
          }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) {
              setShowNodeEditModal(false);
            }
          }}
        >
          <div
            style={{
              backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
              border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
              borderRadius: '6px',
              width: 'auto',
              height: 'auto',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <NodeEditModal
              nodeId={nodeEditData.nodeId}
              field={nodeEditData.field}
              label={nodeEditData.label}
              value={nodeEditData.value}
              isDarkTheme={isDarkTheme}
              onClose={() => setShowNodeEditModal(false)}
              onSave={(nodeId, field, value) => {
                const nodes = graphData?.nodes || [];
                const node = nodes.find((n: any) => n.id === nodeId);
                const attachments = node?.attachments || undefined;
                onNodeUpdate(nodeId, field, value, sessionId, attachments);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};
