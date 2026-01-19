import React, { useState, useEffect, useCallback } from 'react';
import { NodeEditorView } from '../../../shared_components/components/editor/NodeEditorView';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';
import { parse, stringify } from 'lossless-json';
import { DetectedDocument } from '../../../shared_components/utils/documentDetection';

declare global {
  interface Window {
    vscode?: {
      postMessage: (message: any) => void;
    };
    nodeEditorContext?: {
      nodeId: string;
      sessionId: string;
      field: 'input' | 'output';
      label: string;
      inputValue: string;
      outputValue: string;
    };
  }
}

/**
 * Shape of the stored node JSON value.
 * `raw` must be preserved exactly.
 * `to_show` is the editable/displayed portion.
 */
interface NodeStoredValue {
  raw: string;
  to_show: unknown;
}

/**
 * lossless-json stringify can return undefined.
 * Normalize it to always return a string.
 */
const safeStringify = (
  value: unknown,
  replacer?: Parameters<typeof stringify>[1],
  space?: Parameters<typeof stringify>[2]
): string => {
  return stringify(value, replacer, space) ?? '';
};

/**
 * Extracts and parses the `to_show` field if present.
 * Falls back to parsing the raw string.
 */
const extractDisplayData = (jsonStr: string): unknown => {
  try {
    const parsed = parse(jsonStr);
    if (parsed && typeof parsed === 'object' && 'to_show' in parsed) {
      return (parsed as NodeStoredValue).to_show;
    }
    return parsed;
  } catch {
    return null;
  }
};

// Initialize from window context immediately (before component mounts)
const getInitialContext = () => {
  return window.nodeEditorContext || null;
};

const getInitialParsedData = (ctx: typeof window.nodeEditorContext, field: 'inputValue' | 'outputValue') => {
  if (!ctx) return null;
  try {
    return extractDisplayData(ctx[field]);
  } catch {
    return null;
  }
};

export const NodeEditorTabApp: React.FC = () => {
  const isDarkTheme = useIsVsCodeDarkTheme();

  // Initialize state directly from window context
  const [context, setContext] = useState(getInitialContext);
  const [inputData, setInputData] = useState(() => getInitialParsedData(window.nodeEditorContext, 'inputValue'));
  const [outputData, setOutputData] = useState(() => getInitialParsedData(window.nodeEditorContext, 'outputValue'));
  const [initialInputData, setInitialInputData] = useState(() => {
    const data = getInitialParsedData(window.nodeEditorContext, 'inputValue');
    return data ? parse(safeStringify(data)) : null;
  });
  const [initialOutputData, setInitialOutputData] = useState(() => {
    const data = getInitialParsedData(window.nodeEditorContext, 'outputValue');
    return data ? parse(safeStringify(data)) : null;
  });
  const [activeTab, setActiveTab] = useState<'input' | 'output'>(() => window.nodeEditorContext?.field || 'input');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Listen for messages from extension
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      switch (message.type) {
        case 'init':
        case 'updateNodeData':
          // Initialize or update with new node data
          const data = message.payload || message.data;
          if (data) {
            setContext(data);
            setActiveTab(data.field);

            const input = extractDisplayData(data.inputValue);
            const output = extractDisplayData(data.outputValue);

            setInputData(input);
            setOutputData(output);
            setInitialInputData(parse(safeStringify(input)));
            setInitialOutputData(parse(safeStringify(output)));
            setHasUnsavedChanges(false);
          }
          break;

        case 'saved':
          // Server confirmed save
          setHasUnsavedChanges(false);
          break;
      }
    };

    window.addEventListener('message', handleMessage);

    // Send ready message
    if (window.vscode) {
      window.vscode.postMessage({ type: 'ready' });
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  // Detect changes
  useEffect(() => {
    if (initialInputData === null && initialOutputData === null) {
      setHasUnsavedChanges(false);
      return;
    }

    const inputChanged = safeStringify(inputData) !== safeStringify(initialInputData);
    const outputChanged = safeStringify(outputData) !== safeStringify(initialOutputData);

    setHasUnsavedChanges(inputChanged || outputChanged);
  }, [inputData, outputData, initialInputData, initialOutputData]);

  // Handle save
  const handleSave = useCallback(() => {
    if (!context || !window.vscode) return;

    // Reconstruct the { raw, to_show } structure for both input and output
    const reconstructValue = (originalStr: string, editedData: unknown): string => {
      try {
        const originalParsed = parse(originalStr) as NodeStoredValue;

        if (originalParsed && typeof originalParsed === 'object' && 'to_show' in originalParsed) {
          const reconstructed: NodeStoredValue = {
            raw: originalParsed.raw,
            to_show: editedData
          };
          return safeStringify(reconstructed);
        }
      } catch {
        // fall through
      }
      return safeStringify(editedData);
    };

    // Check if input changed
    const inputChanged = safeStringify(inputData) !== safeStringify(initialInputData);
    if (inputChanged) {
      const inputValueToSave = reconstructValue(context.inputValue, inputData);
      window.vscode.postMessage({
        type: 'edit_input',
        session_id: context.sessionId,
        node_id: context.nodeId,
        value: inputValueToSave
      });
    }

    // Check if output changed
    const outputChanged = safeStringify(outputData) !== safeStringify(initialOutputData);
    if (outputChanged) {
      const outputValueToSave = reconstructValue(context.outputValue, outputData);
      window.vscode.postMessage({
        type: 'edit_output',
        session_id: context.sessionId,
        node_id: context.nodeId,
        value: outputValueToSave
      });
    }

    // Update initial data to reflect saved state
    setInitialInputData(parse(safeStringify(inputData)));
    setInitialOutputData(parse(safeStringify(outputData)));
    setHasUnsavedChanges(false);
  }, [context, inputData, outputData, initialInputData, initialOutputData]);

  // Handle document open
  const handleOpenDocument = useCallback((doc: DetectedDocument) => {
    if (window.vscode) {
      window.vscode.postMessage({
        type: 'openDocument',
        document: doc
      });
    }
  }, []);

  if (!context) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          color: isDarkTheme ? '#cccccc' : '#333333',
          backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
        }}
      >
        Loading...
      </div>
    );
  }

  return (
    <NodeEditorView
      inputData={inputData}
      outputData={outputData}
      activeTab={activeTab}
      hasUnsavedChanges={hasUnsavedChanges}
      isDarkTheme={isDarkTheme}
      nodeLabel={context.label}
      onTabChange={setActiveTab}
      onInputChange={setInputData}
      onOutputChange={setOutputData}
      onSave={handleSave}
      onOpenDocument={handleOpenDocument}
    />
  );
};
