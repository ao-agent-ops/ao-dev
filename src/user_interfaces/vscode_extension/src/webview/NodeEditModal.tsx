import React, { useState, useEffect, useRef } from 'react';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';

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
  const [currentValue, setCurrentValue] = useState(initialValue);
  const [hasChanges, setHasChanges] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isDarkTheme = useIsVsCodeDarkTheme();

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

  return (
    <div
      style={{
        margin: 0,
        padding: '20px',
        fontFamily: 'var(--vscode-font-family)',
        fontSize: 'var(--vscode-font-size)',
        color: 'var(--vscode-foreground)',
        background: 'var(--vscode-editor-background)',
      }}
    >
      <div style={{ width: '500px', maxWidth: '100%' }}>
        <h2
          style={{
            margin: '0 0 16px 0',
            fontSize: '16px',
            fontWeight: '600',
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
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: 'var(--vscode-foreground)',
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
              border: '1px solid var(--vscode-input-border)',
              borderRadius: '3px',
              background: 'var(--vscode-input-background)',
              color: 'var(--vscode-input-foreground)',
              fontFamily: 'var(--vscode-editor-font-family, monospace)',
              fontSize: 'var(--vscode-editor-font-size, 14px)',
              resize: 'vertical',
              outline: 'none',
              minHeight: '200px',
              maxHeight: '400px',
            }}
            onFocus={(e) => {
              e.target.style.outline = '1px solid var(--vscode-focusBorder)';
              e.target.style.borderColor = 'var(--vscode-focusBorder)';
            }}
            onBlur={(e) => {
              e.target.style.outline = 'none';
              e.target.style.borderColor = 'var(--vscode-input-border)';
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
            borderTop: '1px solid var(--vscode-editorWidget-border)',
          }}
        >
          <button
            onClick={handleReset}
            disabled={!hasChanges}
            style={{
              padding: '8px 16px',
              border: `1px solid ${hasChanges ? 'var(--vscode-button-border)' : 'var(--vscode-disabledForeground)'}`,
              borderRadius: '3px',
              cursor: hasChanges ? 'pointer' : 'not-allowed',
              fontSize: '12px',
              fontFamily: 'var(--vscode-font-family)',
              background: hasChanges ? 'var(--vscode-button-secondaryBackground)' : 'var(--vscode-input-background)',
              color: hasChanges ? 'var(--vscode-button-secondaryForeground)' : 'var(--vscode-disabledForeground)',
              opacity: hasChanges ? 1 : 0.6,
            }}
            onMouseEnter={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = 'var(--vscode-button-secondaryHoverBackground)';
              }
            }}
            onMouseLeave={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = 'var(--vscode-button-secondaryBackground)';
              }
            }}
          >
            Reset
          </button>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              border: '1px solid var(--vscode-button-border)',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px',
              fontFamily: 'var(--vscode-font-family)',
              background: 'var(--vscode-button-secondaryBackground)',
              color: 'var(--vscode-button-secondaryForeground)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--vscode-button-secondaryHoverBackground)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--vscode-button-secondaryBackground)';
            }}
          >
            Close
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            style={{
              padding: '8px 16px',
              border: `1px solid ${hasChanges ? 'var(--vscode-button-border)' : 'var(--vscode-disabledForeground)'}`,
              borderRadius: '3px',
              cursor: hasChanges ? 'pointer' : 'not-allowed',
              fontSize: '12px',
              fontFamily: 'var(--vscode-font-family)',
              background: hasChanges ? 'var(--vscode-button-background)' : 'var(--vscode-input-background)',
              color: hasChanges ? 'var(--vscode-button-foreground)' : 'var(--vscode-disabledForeground)',
              opacity: hasChanges ? 1 : 0.6,
            }}
            onMouseEnter={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = 'var(--vscode-button-hoverBackground)';
              }
            }}
            onMouseLeave={(e) => {
              if (hasChanges) {
                e.currentTarget.style.background = 'var(--vscode-button-background)';
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
            color: 'var(--vscode-descriptionForeground)',
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