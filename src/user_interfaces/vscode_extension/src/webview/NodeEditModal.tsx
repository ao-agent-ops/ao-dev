import React, { useState, useEffect, useRef } from 'react';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';
import { JSONViewer } from '../../../shared_components/components/JSONViewer';

interface NodeEditModalProps {
  nodeId: string;
  field: 'input' | 'output';
  label: string;
  value: string;
  onClose: () => void;
  onSave: (nodeId: string, field: string, value: string) => void;
}

export const NodeEditModal: React.FC<NodeEditModalProps> = ({
  nodeId,
  field,
  label,
  value: initialValue,
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
  const [savedValue, setSavedValue] = useState(getDisplayValue(initialValue));
  const [hasChanges, setHasChanges] = useState(false);
  const isDarkTheme = useIsVsCodeDarkTheme();
  const [parsedData, setParsedData] = useState<any>(null);

  useEffect(() => {
    const displayValue = getDisplayValue(initialValue);
    setCurrentValue(displayValue);
    setSavedValue(displayValue);
    setHasChanges(false);

    // Try to parse the data for the JSON viewer
    try {
      const parsed = JSON.parse(displayValue);
      setParsedData(parsed);
    } catch (e) {
      setParsedData(null);
    }
  }, [initialValue]);

  useEffect(() => {
    // Normalize JSON strings for comparison (remove whitespace differences)
    const normalizeJSON = (str: string) => {
      try {
        return JSON.stringify(JSON.parse(str));
      } catch {
        return str;
      }
    };

    const hasChanged = normalizeJSON(currentValue) !== normalizeJSON(savedValue);
    setHasChanges(hasChanged);
  }, [currentValue, savedValue]);

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
    // Update savedValue to match currentValue so hasChanges becomes false
    setSavedValue(currentValue);
  };

  const handleReset = () => {
    setCurrentValue(getDisplayValue(initialValue));
  };

  return (
    <div
      style={{
        margin: 0,
        padding: 0,
        fontFamily: 'var(--vscode-font-family)',
        fontSize: 'var(--vscode-font-size)',
        color: 'var(--vscode-foreground)',
        background: 'var(--vscode-editor-background)',
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
          backgroundColor: 'var(--vscode-editor-background)',
          borderBottom: `1px solid ${isDarkTheme ? '#3c3c3c' : '#d0d0d0'}`,
          padding: '12px 16px',
          flexShrink: 0,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: 'var(--vscode-font-size)',
            fontWeight: 'normal',
            color: 'var(--vscode-editor-foreground)',
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
            color: 'var(--vscode-foreground)',
            fontFamily: 'var(--vscode-editor-font-family, monospace)',
            fontSize: 'var(--vscode-editor-font-size, 13px)',
          }}>
            Unable to parse JSON data
          </div>
        )}
      </div>
    </div>
  );
};