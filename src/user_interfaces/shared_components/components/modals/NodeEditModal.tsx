import React, { useState, useEffect } from 'react';
import { JSONViewer } from '../JSONViewer';

interface NodeEditModalProps {
  nodeId: string;
  field: 'input' | 'output';
  label: string;
  value: string;
  isDarkTheme: boolean;
  onClose: () => void;
  onSave: (nodeId: string, field: string, value: string) => void;
}

export const NodeEditModal: React.FC<NodeEditModalProps> = ({
  nodeId,
  field,
  label,
  value: initialValue,
  isDarkTheme,
  onClose,
  onSave
}) => {
  // Parse the initial value to extract to_show field
  const getDisplayValue = (jsonStr: string): string => {
    try {
      const parsed = JSON.parse(jsonStr);
      if (parsed && typeof parsed === 'object' && 'to_show' in parsed) {
        return JSON.stringify(parsed.to_show, null, 2);
      }
    } catch (e) {
      // If parsing fails, return original string
    }
    return jsonStr;
  };

  const [currentValue, setCurrentValue] = useState(getDisplayValue(initialValue));
  const [hasChanges, setHasChanges] = useState(false);
  const [parsedData, setParsedData] = useState<any>(null);
  const [initialParsedData, setInitialParsedData] = useState<any>(null);

  useEffect(() => {
    setCurrentValue(getDisplayValue(initialValue));
    setHasChanges(false);

    // Try to parse the data for the JSON viewer
    try {
      const parsed = JSON.parse(getDisplayValue(initialValue));
      setParsedData(parsed);
      setInitialParsedData(JSON.parse(JSON.stringify(parsed))); // Deep clone
    } catch (e) {
      setParsedData(null);
      setInitialParsedData(null);
    }
  }, [initialValue]);

  useEffect(() => {
    // Deep comparison to detect changes
    if (parsedData === null || initialParsedData === null) {
      setHasChanges(false);
      return;
    }
    const currentStr = JSON.stringify(parsedData);
    const initialStr = JSON.stringify(initialParsedData);
    const changed = currentStr !== initialStr;
    setHasChanges(changed);
  }, [parsedData, initialParsedData]);

  const handleJSONChange = (newData: any) => {
    // Update both the parsed data and the string value
    setParsedData(newData);
    setCurrentValue(JSON.stringify(newData, null, 2));
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [hasChanges, currentValue]);

  const handleSave = () => {
    // Reconstruct the full JSON structure with both raw and to_show fields
    let valueToSave = currentValue;
    try {
      const originalParsed = JSON.parse(initialValue);
      if (originalParsed && typeof originalParsed === 'object' && 'to_show' in originalParsed) {
        // Parse the edited to_show value
        const editedToShow = JSON.parse(currentValue);
        // Reconstruct with updated to_show
        const reconstructed = {
          raw: editedToShow,  // Update raw to match to_show
          to_show: editedToShow
        };
        valueToSave = JSON.stringify(reconstructed);
      }
    } catch (e) {
      // If parsing fails, save as-is
      valueToSave = currentValue;
    }

    onSave(nodeId, field, valueToSave);
    // Reset the change tracking by updating the initial reference
    setInitialParsedData(JSON.parse(JSON.stringify(parsedData)));
    setHasChanges(false);
  };

  const handleReset = () => {
    setCurrentValue(getDisplayValue(initialValue));
  };

  return (
    <div
      style={{
        margin: 0,
        padding: 0,
        fontFamily: 'var(--vscode-font-family, "Segoe UI", "Helvetica Neue", Arial, sans-serif)',
        fontSize: 'var(--vscode-font-size, 13px)',
        color: isDarkTheme ? '#cccccc' : '#333333',
        background: isDarkTheme ? '#1e1e1e' : '#ffffff',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
          borderBottom: `1px solid ${isDarkTheme ? '#3c3c3c' : '#d0d0d0'}`,
          padding: '12px 16px',
          flexShrink: 0,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: 'var(--vscode-font-size, 13px)',
            fontWeight: 'normal',
            color: isDarkTheme ? '#ffffff' : '#000000',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          Edit {label} {field === 'input' ? 'Input' : 'Output'}
          {hasChanges && (
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isDarkTheme ? '#ffffff' : '#000000',
                flexShrink: 0,
              }}
            />
          )}
        </h2>
      </div>

      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        overflow: 'auto',
      }}>
        {parsedData !== null ? (
          <JSONViewer data={parsedData} isDarkTheme={isDarkTheme} onChange={handleJSONChange} />
        ) : (
          <div style={{
            padding: '12px',
            color: isDarkTheme ? '#cccccc' : '#333333',
            fontFamily: 'var(--vscode-editor-font-family, monospace)',
            fontSize: 'var(--vscode-editor-font-size, 13px)',
          }}>
            Unable to parse JSON data
          </div>
        )}
      </div>

      {/* Keyboard Hints */}
      <div
        style={{
          fontSize: '11px',
          color: isDarkTheme ? '#858585' : '#6c6c6c',
          marginTop: '8px',
          marginBottom: '8px',
          textAlign: 'center',
        }}
      >
        Press ESC to cancel • {navigator.platform.toLowerCase().includes('mac') ? '⌘S' : 'Ctrl+S'} to save
      </div>
    </div>
  );
};
