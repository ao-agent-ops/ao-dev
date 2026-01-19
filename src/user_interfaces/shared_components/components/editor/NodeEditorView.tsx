import React, { useState, useEffect, useCallback } from 'react';
import { parse, stringify } from 'lossless-json';
import { JSONViewer } from '../JSONViewer';
import { DetectedDocument } from '../../utils/documentDetection';

interface NodeEditorViewProps {
  inputData: any;
  outputData: any;
  activeTab: 'input' | 'output';
  hasUnsavedChanges: boolean;
  isDarkTheme: boolean;
  nodeLabel: string;
  onTabChange: (tab: 'input' | 'output') => void;
  onInputChange: (newData: any) => void;
  onOutputChange: (newData: any) => void;
  onSave: () => void;
  onOpenDocument?: (doc: DetectedDocument) => void;
}

export const NodeEditorView: React.FC<NodeEditorViewProps> = ({
  inputData,
  outputData,
  activeTab,
  hasUnsavedChanges,
  isDarkTheme,
  nodeLabel,
  onTabChange,
  onInputChange,
  onOutputChange,
  onSave,
  onOpenDocument,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  // Keyboard shortcut for save
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        onSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onSave]);

  const colors = isDarkTheme
    ? {
        background: '#1e1e1e',
        headerBg: '#252526',
        border: '#3c3c3c',
        text: '#cccccc',
        textMuted: '#888888',
        inputBg: '#3c3c3c',
        tabActive: '#1e1e1e',
        tabInactive: '#2d2d2d',
        tabHover: '#363636',
        accentColor: '#0e639c',
      }
    : {
        background: '#ffffff',
        headerBg: '#f3f3f3',
        border: '#e0e0e0',
        text: '#333333',
        textMuted: '#666666',
        inputBg: '#ffffff',
        tabActive: '#ffffff',
        tabInactive: '#ececec',
        tabHover: '#e0e0e0',
        accentColor: '#007acc',
      };

  // Filter data based on search query
  const filterData = useCallback((data: any, query: string): any => {
    if (!query.trim() || data === null || typeof data !== 'object') {
      return data;
    }

    const lowerQuery = query.toLowerCase();

    if (Array.isArray(data)) {
      // For arrays, filter items that have matching keys in their contents
      const filtered = data
        .map((item, index) => {
          if (typeof item === 'object' && item !== null) {
            const filteredItem = filterData(item, query);
            // Keep if the filtered item has any keys
            if (Object.keys(filteredItem).length > 0) {
              return filteredItem;
            }
          }
          return null;
        })
        .filter((item) => item !== null);
      return filtered.length > 0 ? filtered : data; // Return original if no matches to avoid empty arrays
    }

    // For objects, filter by key names
    const result: Record<string, any> = {};
    for (const [key, value] of Object.entries(data)) {
      const keyMatches = key.toLowerCase().includes(lowerQuery);

      if (keyMatches) {
        // Key matches, include entire subtree
        result[key] = value;
      } else if (typeof value === 'object' && value !== null) {
        // Key doesn't match, but check children
        const filteredChild = filterData(value, query);
        if (Array.isArray(value)) {
          if (filteredChild.length > 0) {
            result[key] = filteredChild;
          }
        } else if (Object.keys(filteredChild).length > 0) {
          result[key] = filteredChild;
        }
      }
      // Primitive values with non-matching keys are excluded
    }
    return result;
  }, []);

  const currentData = activeTab === 'input' ? inputData : outputData;
  const filteredData = filterData(currentData, searchQuery);
  const handleChange = activeTab === 'input' ? onInputChange : onOutputChange;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: colors.background,
        color: colors.text,
        fontFamily: "var(--vscode-font-family, 'Segoe UI', sans-serif)",
      }}
    >
      {/* Header with search and save */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '8px 16px',
          backgroundColor: colors.headerBg,
          borderBottom: `1px solid ${colors.border}`,
          gap: '12px',
        }}
      >
        {/* Search input */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            backgroundColor: colors.inputBg,
            border: `1px solid ${colors.border}`,
            borderRadius: '4px',
            padding: '4px 8px',
          }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill={colors.textMuted}
            style={{ marginRight: '8px', flexShrink: 0 }}
          >
            <path d="M15.7 13.3l-3.81-3.83A5.93 5.93 0 0 0 13 6c0-3.31-2.69-6-6-6S1 2.69 1 6s2.69 6 6 6c1.3 0 2.48-.41 3.47-1.11l3.83 3.81c.19.2.45.3.7.3.25 0 .52-.09.7-.3a.996.996 0 0 0 0-1.41v.01zM7 10.7c-2.59 0-4.7-2.11-4.7-4.7 0-2.59 2.11-4.7 4.7-4.7 2.59 0 4.7 2.11 4.7 4.7 0 2.59-2.11 4.7-4.7 4.7z" />
          </svg>
          <input
            type="text"
            placeholder="Search attributes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              backgroundColor: 'transparent',
              color: colors.text,
              fontSize: '13px',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '2px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill={colors.textMuted}>
                <path d="M8 8.707l3.646 3.647.708-.707L8.707 8l3.647-3.646-.707-.708L8 7.293 4.354 3.646l-.707.708L7.293 8l-3.646 3.646.707.708L8 8.707z" />
              </svg>
            </button>
          )}
        </div>

        {/* Save icon */}
        <button
          onClick={hasUnsavedChanges ? onSave : undefined}
          disabled={!hasUnsavedChanges}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '6px',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '4px',
            cursor: hasUnsavedChanges ? 'pointer' : 'default',
            opacity: hasUnsavedChanges ? 1 : 0.4,
          }}
          onMouseEnter={(e) => {
            if (hasUnsavedChanges) {
              e.currentTarget.style.backgroundColor = colors.inputBg;
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
          title={hasUnsavedChanges ? 'Save changes (Cmd+S)' : 'No changes to save'}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 16 16"
            fill={hasUnsavedChanges ? colors.text : colors.textMuted}
          >
            <path d="M13.354 1H1v14h14V2.646L13.354 1zM2 2h1v4h8V2h1.293L14 3.707V14H2V2zm3 0h4v3H5V2zm3 6H4v6h8V8H8zm3 5H5v-4h6v4z" />
          </svg>
        </button>
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: 'flex',
          backgroundColor: colors.headerBg,
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        <button
          onClick={() => onTabChange('input')}
          style={{
            padding: '8px 16px',
            backgroundColor: activeTab === 'input' ? colors.tabActive : colors.tabInactive,
            color: colors.text,
            border: 'none',
            borderBottom: activeTab === 'input' ? `2px solid ${colors.accentColor}` : '2px solid transparent',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: activeTab === 'input' ? 600 : 400,
          }}
          onMouseEnter={(e) => {
            if (activeTab !== 'input') {
              e.currentTarget.style.backgroundColor = colors.tabHover;
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'input') {
              e.currentTarget.style.backgroundColor = colors.tabInactive;
            }
          }}
        >
          Input
        </button>
        <button
          onClick={() => onTabChange('output')}
          style={{
            padding: '8px 16px',
            backgroundColor: activeTab === 'output' ? colors.tabActive : colors.tabInactive,
            color: colors.text,
            border: 'none',
            borderBottom: activeTab === 'output' ? `2px solid ${colors.accentColor}` : '2px solid transparent',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: activeTab === 'output' ? 600 : 400,
          }}
          onMouseEnter={(e) => {
            if (activeTab !== 'output') {
              e.currentTarget.style.backgroundColor = colors.tabHover;
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'output') {
              e.currentTarget.style.backgroundColor = colors.tabInactive;
            }
          }}
        >
          Output
        </button>
      </div>

      {/* JSON Editor */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
        }}
      >
        <JSONViewer
          data={filteredData}
          isDarkTheme={isDarkTheme}
          onChange={handleChange}
          onOpenDocument={onOpenDocument}
        />
      </div>
    </div>
  );
};
