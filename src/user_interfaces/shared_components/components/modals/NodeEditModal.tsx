import React, { useState, useEffect } from 'react';
import { JSONViewer } from '../JSONViewer';
import { parse, stringify } from 'lossless-json';

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
      const parsed = parse(jsonStr);
      if (parsed && typeof parsed === 'object' && 'to_show' in parsed) {
        return stringify(parsed.to_show, null, 2);
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
      const parsed = parse(getDisplayValue(initialValue));
      setParsedData(parsed);
      setInitialParsedData(parse(stringify(parsed))); // Deep clone
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
    const currentStr = stringify(parsedData);
    const initialStr = stringify(initialParsedData);
    const changed = currentStr !== initialStr;
    setHasChanges(changed);
  }, [parsedData, initialParsedData]);

  const handleJSONChange = (newData: any) => {
    // Update both the parsed data and the string value
    setParsedData(newData);
    setCurrentValue(stringify(newData, null, 2));
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
      const originalParsed = parse(initialValue);
      if (originalParsed && typeof originalParsed === 'object' && 'to_show' in originalParsed) {
        // Parse the edited to_show value
        const editedToShow = parse(currentValue);
        // Reconstruct with updated to_show but preserve original raw
        const reconstructed = {
          raw: originalParsed.raw,  // Preserve the original raw - do not touch it!
          to_show: editedToShow
        };
        valueToSave = stringify(reconstructed);
      }
    } catch (e) {
      // If parsing fails, save as-is
      valueToSave = currentValue;
    }

    onSave(nodeId, field, valueToSave);
    // Reset the change tracking by updating the initial reference
    setInitialParsedData(parse(stringify(parsedData)));
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
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
          </h2>
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            style={{
              background: 'none',
              border: 'none',
              padding: '4px',
              cursor: hasChanges ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              color: hasChanges ? (isDarkTheme ? '#ffffff' : '#000000') : (isDarkTheme ? '#666666' : '#999999'),
              opacity: hasChanges ? 1 : 0.5,
            }}
            title="Save (Cmd+S / Ctrl+S)"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
              <path d="M14.414 3.207L12.793 1.586C12.421 1.213 11.905 1 11.379 1H3C1.897 1 1 1.897 1 3V13C1 14.103 1.897 15 3 15H13C14.103 15 15 14.103 15 13V4.621C15 4.095 14.787 3.579 14.414 3.207ZM9 2V3.5C9 3.776 8.776 4 8.5 4H6.5C6.224 4 6 3.776 6 3.5V2H9ZM5 14V9.5C5 9.224 5.224 9 5.5 9H10.5C10.776 9 11 9.224 11 9.5V14H5ZM14 13C14 13.551 13.551 14 13 14H12V9.5C12 8.673 11.327 8 10.5 8H5.5C4.673 8 4 8.673 4 9.5V14H3C2.449 14 2 13.551 2 13V3C2 2.449 2.449 2 3 2H5V3.5C5 4.327 5.673 5 6.5 5H8.5C9.327 5 10 4.327 10 3.5V2H11.379C11.642 2 11.9 2.107 12.086 2.293L13.707 3.914C13.893 4.1 14 4.358 14 4.621V13Z"/>
            </svg>
          </button>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            padding: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            color: isDarkTheme ? '#ffffff' : '#000000',
          }}
          title="Cancel (ESC)"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
            <path d="M8.70701 8.00001L12.353 4.35401C12.548 4.15901 12.548 3.84201 12.353 3.64701C12.158 3.45201 11.841 3.45201 11.646 3.64701L8.00001 7.29301L4.35401 3.64701C4.15901 3.45201 3.84201 3.45201 3.64701 3.64701C3.45201 3.84201 3.45201 4.15901 3.64701 4.35401L7.29301 8.00001L3.64701 11.646C3.45201 11.841 3.45201 12.158 3.64701 12.353C3.74501 12.451 3.87301 12.499 4.00101 12.499C4.12901 12.499 4.25701 12.45 4.35501 12.353L8.00101 8.70701L11.647 12.353C11.745 12.451 11.873 12.499 12.001 12.499C12.129 12.499 12.257 12.45 12.355 12.353C12.55 12.158 12.55 11.841 12.355 11.646L8.70901 8.00001H8.70701Z"/>
          </svg>
        </button>
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
