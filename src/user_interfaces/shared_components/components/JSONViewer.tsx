import React, { useState } from 'react';
import { parse, stringify } from 'lossless-json';
import { detectDocument, formatFileSize, getDocumentKey, DetectedDocument } from '../utils/documentDetection';
import { useDocumentContext } from '../contexts/DocumentContext';

interface JSONViewerProps {
  data: any;
  isDarkTheme: boolean;
  depth?: number;
  onChange?: (newData: any) => void;
  onOpenDocument?: (doc: DetectedDocument) => void;
}

interface JSONNodeProps {
  keyName: string | null;
  value: any;
  isDarkTheme: boolean;
  depth: number;
  isLast: boolean;
  path: string[];
  onChange?: (path: string[], newValue: any) => void;
  siblingData?: Record<string, unknown>;
  onOpenDocument?: (doc: DetectedDocument) => void;
}

const JSONNode: React.FC<JSONNodeProps> = ({ keyName, value, isDarkTheme, depth, isLast, path, onChange, siblingData, onOpenDocument }) => {
  // Expand everything by default
  const [isExpanded, setIsExpanded] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  // Track the original type to preserve it during editing
  const [originalType] = useState<string>(typeof value);
  // Toggle to show raw base64 instead of document button
  const [showRawDocument, setShowRawDocument] = useState(false);
  // Get opened document paths from context
  const { openedPaths } = useDocumentContext();

  const colors = isDarkTheme
    ? {
        key: '#9cdcfe',
        string: '#ce9178',
        number: '#b5cea8',
        boolean: '#569cd6',
        null: '#569cd6',
        bracket: '#d4d4d4',
        background: '#1e1e1e',
        hoverBackground: '#2a2a2a',
        inputBackground: '#2d2d2d',
        inputBorder: '#3c3c3c',
      }
    : {
        key: '#0451a5',
        string: '#a31515',
        number: '#098658',
        boolean: '#0000ff',
        null: '#0000ff',
        bracket: '#333333',
        background: '#ffffff',
        hoverBackground: '#f3f3f3',
        inputBackground: '#ffffff',
        inputBorder: '#d0d0d0',
      };

  const indent = depth * 15;

  // Check if a value is a LosslessNumber from lossless-json library
  const isLosslessNumber = (val: any): boolean => {
    return val !== null && typeof val === 'object' && val.isLosslessNumber === true;
  };

  // Get the actual value, unwrapping LosslessNumber if needed
  const unwrapValue = (val: any): any => {
    if (isLosslessNumber(val)) {
      return Number(val.value);
    }
    return val;
  };

  const isExpandable = (val: any) => {
    // LosslessNumber objects should not be expandable - they're just numbers
    if (isLosslessNumber(val)) {
      return false;
    }
    return (
      val !== null &&
      typeof val === 'object' &&
      (Array.isArray(val) ? val.length > 0 : Object.keys(val).length > 0)
    );
  };

  const getValuePreview = (val: any): string => {
    if (Array.isArray(val)) {
      return val.length === 0 ? '[]' : `[${val.length} items]`;
    }
    if (val !== null && typeof val === 'object') {
      const keys = Object.keys(val);
      return keys.length === 0 ? '{}' : `{${keys.length} keys}`;
    }
    return '';
  };

  const parseEditValue = (editVal: string): any => {
    const trimmed = editVal.trim();

    // If the original value was a string, keep it as a string
    if (originalType === 'string') {
      return editVal;
    }

    // Try to parse as JSON literal
    if (trimmed === 'null') {
      return null;
    } else if (trimmed === 'true') {
      return true;
    } else if (trimmed === 'false') {
      return false;
    } else if (!isNaN(Number(trimmed)) && trimmed !== '') {
      // Number - lossless-json will preserve float vs int distinction
      return Number(trimmed);
    } else {
      // String - return as-is, lossless-json handles type preservation
      return editVal;
    }
  };

  const saveEdit = () => {
    if (!onChange) return;
    const newValue = parseEditValue(editValue);
    onChange(path, newValue);
    setIsEditing(false);
  };

  const handleChange = (newEditValue: string) => {
    setEditValue(newEditValue);
    if (!isEditing) setIsEditing(true);

    // Immediately propagate changes to parent for change detection
    if (onChange) {
      const newValue = parseEditValue(newEditValue);
      onChange(path, newValue);
    }
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setEditValue('');
  };

  const renderValue = (val: any) => {
    const editable = onChange !== undefined;

    const getTextareaStyle = (color: string) => ({
      fontFamily: 'var(--vscode-editor-font-family, monospace)',
      fontSize: 'var(--vscode-editor-font-size, 13px)',
      padding: '2px 4px',
      border: `1px solid ${colors.inputBorder}`,
      borderRadius: '2px',
      backgroundColor: colors.inputBackground,
      color: color,
      outline: 'none',
      width: '100%',
      resize: 'both' as const,
      lineHeight: '1.4',
      overflow: 'auto',
      cursor: editable ? 'text' : 'default',
      boxSizing: 'border-box' as const,
    });

    // Calculate rows based on content length
    const getRows = (content: string) => {
      if (content.length < 100) return 1;
      if (content.length < 500) return 5;
      if (content.length < 2000) return 15;
      return 30;
    };

    // Check for base64-encoded documents (PDF, images, etc.)
    if (typeof val === 'string' && onOpenDocument && !showRawDocument) {
      const doc = detectDocument(val, siblingData);
      if (doc) {
        const docKey = getDocumentKey(doc.data);
        const openedPath = openedPaths.get(docKey);

        const iconMap: Record<string, string> = {
          pdf: 'file-pdf',
          png: 'file-media',
          jpeg: 'file-media',
          gif: 'file-media',
          webp: 'file-media',
          docx: 'file',
          xlsx: 'file',
          zip: 'file-zip',
          unknown: 'file-binary',
        };

        const buttonStyle: React.CSSProperties = {
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 8px',
          border: `1px solid ${colors.inputBorder}`,
          borderRadius: '4px',
          backgroundColor: isDarkTheme ? '#2d2d2d' : '#f3f3f3',
          color: isDarkTheme ? '#cccccc' : '#333333',
          cursor: 'pointer',
          fontFamily: 'var(--vscode-font-family, sans-serif)',
          fontSize: 'var(--vscode-font-size, 13px)',
        };

        const linkStyle: React.CSSProperties = {
          background: 'none',
          border: 'none',
          color: isDarkTheme ? '#569cd6' : '#0451a5',
          cursor: 'pointer',
          textDecoration: 'underline',
          fontFamily: 'var(--vscode-font-family, sans-serif)',
          fontSize: 'var(--vscode-font-size, 13px)',
          padding: '4px',
        };

        const pathStyle: React.CSSProperties = {
          fontFamily: 'var(--vscode-editor-font-family, monospace)',
          fontSize: 'var(--vscode-editor-font-size, 12px)',
          color: isDarkTheme ? '#888888' : '#666666',
        };

        // Use friendly label - "Open file" for zip/unknown since we can't distinguish DOCX/XLSX/etc
        const labelMap: Record<string, string> = {
          pdf: 'PDF',
          png: 'PNG',
          jpeg: 'JPEG',
          gif: 'GIF',
          webp: 'WebP',
          docx: 'DOCX',
          xlsx: 'XLSX',
          zip: 'file',
          unknown: 'file',
        };

        return (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button style={buttonStyle} onClick={() => onOpenDocument(doc)}>
              <i className={`codicon codicon-${iconMap[doc.type]}`} />
              {` Open ${labelMap[doc.type]} (${formatFileSize(doc.size)})`}
            </button>
            {openedPath && (
              <span style={pathStyle}>File available at {openedPath}</span>
            )}
            <button style={linkStyle} onClick={() => setShowRawDocument(true)}>
              Show raw
            </button>
          </div>
        );
      }
    }

    // Handle LosslessNumber objects - render them as regular numbers
    if (isLosslessNumber(val)) {
      const numValue = unwrapValue(val);
      return (
        <textarea
          rows={getRows(numValue.toString())}
          value={isEditing ? editValue : numValue.toString()}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (!isEditing) {
              setEditValue(numValue.toString());
              setIsEditing(true);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              cancelEdit();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault();
              saveEdit();
            }
          }}
          readOnly={!editable}
          style={getTextareaStyle(colors.number)}
        />
      );
    }
    // Always display values in a textarea for editability
    if (val === null) {
      return (
        <textarea
          rows={getRows('null')}
          value={editValue || 'null'}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (!isEditing) {
              setEditValue('null');
              setIsEditing(true);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              cancelEdit();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault();
              saveEdit();
            }
          }}
          readOnly={!editable}
          style={getTextareaStyle(colors.null)}
        />
      );
    }
    if (typeof val === 'string') {
      // Display strings directly - lossless-json preserves types
      const displayValue = isEditing ? editValue : val;
      return (
        <textarea
          rows={getRows(displayValue)}
          value={displayValue}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (!isEditing) {
              setEditValue(val);
              setIsEditing(true);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              cancelEdit();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault();
              saveEdit();
            }
          }}
          readOnly={!editable}
          style={getTextareaStyle(colors.string)}
        />
      );
    }
    if (typeof val === 'number') {
      return (
        <textarea
          rows={getRows(val.toString())}
          value={isEditing ? editValue : val.toString()}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (!isEditing) {
              setEditValue(val.toString());
              setIsEditing(true);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              cancelEdit();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault();
              saveEdit();
            }
          }}
          readOnly={!editable}
          style={getTextareaStyle(colors.number)}
        />
      );
    }
    if (typeof val === 'boolean') {
      return (
        <textarea
          rows={getRows(val.toString())}
          value={isEditing ? editValue : val.toString()}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (!isEditing) {
              setEditValue(val.toString());
              setIsEditing(true);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              cancelEdit();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault();
              saveEdit();
            }
          }}
          readOnly={!editable}
          style={getTextareaStyle(colors.boolean)}
        />
      );
    }
    return null;
  };

  const toggleExpand = () => {
    if (isExpandable(value)) {
      setIsExpanded(!isExpanded);
    }
  };

  if (!isExpandable(value)) {
    // Simple value - render with key above textarea
    return (
      <div
        style={{
          paddingLeft: `${indent}px`,
          fontFamily: 'var(--vscode-editor-font-family, monospace)',
          fontSize: 'var(--vscode-editor-font-size, 13px)',
          lineHeight: '20px',
          marginBottom: '4px',
        }}
      >
        {keyName !== null && (
          <div style={{ marginBottom: '2px' }}>
            <span style={{ color: colors.key }}>"{keyName?.split('.').pop() || keyName}"</span>
            <span style={{ color: colors.bracket }}>:</span>
          </div>
        )}
        <div>
          {renderValue(value)}
        </div>
      </div>
    );
  }

  // Complex value - render with expand/collapse
  const isArray = Array.isArray(value);
  const entries = isArray ? value.map((v, i) => [i.toString(), v]) : Object.entries(value);

  return (
    <div>
      <div
        onClick={toggleExpand}
        style={{
          paddingLeft: `${indent}px`,
          fontFamily: 'var(--vscode-editor-font-family, monospace)',
          fontSize: 'var(--vscode-editor-font-size, 13px)',
          lineHeight: '20px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = colors.hoverBackground;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
      >
        <i
          className={`codicon ${isExpanded ? 'codicon-chevron-down' : 'codicon-chevron-right'}`}
          style={{ marginRight: '4px', fontSize: '16px' }}
        />
        {keyName !== null && (
          <>
            <span style={{ color: colors.key }}>"{keyName?.split('.').pop() || keyName}"</span>
            <span style={{ color: colors.bracket }}>: </span>
          </>
        )}
        <span style={{ color: colors.bracket }}>
          {isArray ? '[' : '{'}
          {!isExpanded && (
            <>
              <span style={{ color: colors.bracket, opacity: 0.6 }}>
                {getValuePreview(value)}
              </span>
              {isArray ? ']' : '}'}
            </>
          )}
        </span>
      </div>

      {isExpanded && (
        <>
          {entries.map(([key, val], index) => (
            <JSONNode
              key={key}
              keyName={isArray ? null : key}
              value={val}
              isDarkTheme={isDarkTheme}
              depth={depth + 1}
              isLast={index === entries.length - 1}
              path={[...path, key]}
              onChange={onChange}
              siblingData={isArray ? undefined : value}
              onOpenDocument={onOpenDocument}
            />
          ))}
          <div
            style={{
              paddingLeft: `${indent}px`,
              fontFamily: 'var(--vscode-editor-font-family, monospace)',
              fontSize: 'var(--vscode-editor-font-size, 13px)',
              lineHeight: '20px',
            }}
          >
            <span style={{ color: colors.bracket }}>{isArray ? ']' : '}'}</span>
          </div>
        </>
      )}
    </div>
  );
};

export const JSONViewer: React.FC<JSONViewerProps> = ({ data, isDarkTheme, depth = 0, onChange, onOpenDocument }) => {
  const handleChange = (path: string[], newValue: any) => {
    if (!onChange) return;

    // Clone the data and update the value at the specified path using lossless-json
    const newData = parse(stringify(data) || '{}') as any;
    let current: any = newData;

    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]];
    }

    current[path[path.length - 1]] = newValue;
    onChange(newData);
  };

  // If data is an object or array, render its children directly without the wrapper
  const isObject = data !== null && typeof data === 'object' && !Array.isArray(data);
  const isArray = Array.isArray(data);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      overflow: 'auto',
      padding: '12px',
      backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
    }}>
      {(isObject || isArray) ? (
        // Render children directly, starting at depth -1 so first level is depth 0
        <>
          {Object.entries(data).map(([key, val], index, arr) => (
            <JSONNode
              key={key}
              keyName={isArray ? null : key}
              value={val}
              isDarkTheme={isDarkTheme}
              depth={0}
              isLast={index === arr.length - 1}
              path={[key]}
              onChange={onChange ? handleChange : undefined}
              siblingData={isArray ? undefined : data}
              onOpenDocument={onOpenDocument}
            />
          ))}
        </>
      ) : (
        // For primitive values, render normally
        <JSONNode
          keyName={null}
          value={data}
          isDarkTheme={isDarkTheme}
          depth={depth}
          isLast={true}
          path={[]}
          onChange={onChange ? handleChange : undefined}
          onOpenDocument={onOpenDocument}
        />
      )}
    </div>
  );
};
