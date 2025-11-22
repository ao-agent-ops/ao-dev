import React, { useState, useEffect, useRef } from 'react';

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
  const [currentValue, setCurrentValue] = useState(initialValue);
  const [hasChanges, setHasChanges] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setCurrentValue(initialValue);
    setHasChanges(false);
  }, [initialValue]);

  useEffect(() => {
    setHasChanges(currentValue !== initialValue);
  }, [currentValue, initialValue]);

  useEffect(() => {
    // Focus and select all text when modal opens
    if (textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.select();
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (hasChanges) {
          handleSave();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [hasChanges, currentValue]);

  const handleSave = () => {
    onSave(nodeId, field, currentValue);
    // Reset the hasChanges flag by updating the initial value reference
    setHasChanges(false);
  };

  const handleReset = () => {
    setCurrentValue(initialValue);
  };

  const buttonStyles = {
    primary: {
      background: isDarkTheme ? '#0e639c' : '#007acc',
      color: '#ffffff',
      hoverBackground: isDarkTheme ? '#1177bb' : '#005a9e',
    },
    secondary: {
      background: isDarkTheme ? '#3c3c3c' : '#e0e0e0',
      color: isDarkTheme ? '#cccccc' : '#333333',
      hoverBackground: isDarkTheme ? '#4c4c4c' : '#d0d0d0',
    },
    disabled: {
      background: isDarkTheme ? '#2d2d2d' : '#f0f0f0',
      color: isDarkTheme ? '#666666' : '#999999',
    }
  };

  return (
    <div
      style={{
        margin: 0,
        padding: '20px',
        fontFamily: 'var(--vscode-font-family, "Segoe UI", "Helvetica Neue", Arial, sans-serif)',
        fontSize: '13px',
        color: isDarkTheme ? '#cccccc' : '#333333',
        background: isDarkTheme ? '#1e1e1e' : '#ffffff',
      }}
    >
      <div style={{ width: '500px', maxWidth: '100%' }}>
        <h2
          style={{
            margin: '0 0 16px 0',
            fontSize: '16px',
            fontWeight: '600',
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
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: isDarkTheme ? '#cccccc' : '#333333',
              }}
            />
          )}
        </h2>

        <div style={{ marginBottom: '20px' }}>
          <textarea
            ref={textareaRef}
            value={currentValue}
            onChange={(e) => setCurrentValue(e.target.value)}
            rows={12}
            style={{
              width: '100%',
              maxWidth: '100%',
              minWidth: '0',
              boxSizing: 'border-box',
              padding: '12px',
              border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#d0d0d0'}`,
              borderRadius: '3px',
              background: isDarkTheme ? '#2d2d2d' : '#ffffff',
              color: isDarkTheme ? '#cccccc' : '#333333',
              fontFamily: 'var(--vscode-editor-font-family, monospace)',
              fontSize: '14px',
              resize: 'vertical',
              outline: 'none',
              minHeight: '200px',
              maxHeight: '400px',
            }}
            onFocus={(e) => {
              e.target.style.outline = `1px solid ${isDarkTheme ? '#007acc' : '#0078d4'}`;
              e.target.style.borderColor = isDarkTheme ? '#007acc' : '#0078d4';
            }}
            onBlur={(e) => {
              e.target.style.outline = 'none';
              e.target.style.borderColor = isDarkTheme ? '#3c3c3c' : '#d0d0d0';
            }}
            placeholder={`Enter ${field} text...`}
          />
        </div>

        {/* Button Group */}
        <div
          style={{
            display: 'flex',
            gap: '12px',
            justifyContent: 'flex-end',
            paddingTop: '20px',
            borderTop: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
          }}
        >
          <button
            onClick={handleReset}
            disabled={!hasChanges}
            style={{
              padding: '8px 16px',
              border: `1px solid ${hasChanges ? (isDarkTheme ? '#3c3c3c' : '#d0d0d0') : 'transparent'}`,
              borderRadius: '3px',
              cursor: hasChanges ? 'pointer' : 'not-allowed',
              fontSize: '12px',
              fontFamily: 'var(--vscode-font-family, "Segoe UI", "Helvetica Neue", Arial, sans-serif)',
              background: hasChanges ? buttonStyles.secondary.background : buttonStyles.disabled.background,
              color: hasChanges ? buttonStyles.secondary.color : buttonStyles.disabled.color,
              opacity: hasChanges ? 1 : 0.6,
            }}
            onMouseEnter={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = buttonStyles.secondary.hoverBackground;
              }
            }}
            onMouseLeave={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = buttonStyles.secondary.background;
              }
            }}
          >
            Reset
          </button>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#d0d0d0'}`,
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px',
              fontFamily: 'var(--vscode-font-family, "Segoe UI", "Helvetica Neue", Arial, sans-serif)',
              background: buttonStyles.secondary.background,
              color: buttonStyles.secondary.color,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = buttonStyles.secondary.hoverBackground;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = buttonStyles.secondary.background;
            }}
          >
            Close
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            style={{
              padding: '8px 16px',
              border: `1px solid ${hasChanges ? (isDarkTheme ? '#007acc' : '#0078d4') : 'transparent'}`,
              borderRadius: '3px',
              cursor: hasChanges ? 'pointer' : 'not-allowed',
              fontSize: '12px',
              fontFamily: 'var(--vscode-font-family, "Segoe UI", "Helvetica Neue", Arial, sans-serif)',
              background: hasChanges ? buttonStyles.primary.background : buttonStyles.disabled.background,
              color: hasChanges ? buttonStyles.primary.color : buttonStyles.disabled.color,
              opacity: hasChanges ? 1 : 0.6,
            }}
            onMouseEnter={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = buttonStyles.primary.hoverBackground;
              }
            }}
            onMouseLeave={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = buttonStyles.primary.background;
              }
            }}
          >
            Save {navigator.platform.toLowerCase().includes('mac') ? '(⌘S)' : '(Ctrl+S)'}
          </button>
        </div>

        {/* Keyboard Hints */}
        <div
          style={{
            fontSize: '11px',
            color: isDarkTheme ? '#888888' : '#666666',
            marginTop: '16px',
            textAlign: 'center',
          }}
        >
          Press ESC to close • {navigator.platform.toLowerCase().includes('mac') ? '⌘S' : 'Ctrl+S'} to save
        </div>
      </div>
    </div>
  );
};
