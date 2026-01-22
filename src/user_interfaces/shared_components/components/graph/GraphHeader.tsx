import React, { useState, useRef, useEffect } from 'react';
import { ProcessInfo } from '../../types';

interface GraphHeaderProps {
  runName: string;
  isDarkTheme: boolean;
  sessionId?: string;
  experiments?: ProcessInfo[];
  onNavigateToExperiment?: (experiment: ProcessInfo) => void;
}

// Helper to get relative time string
const getRelativeTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'now';
  if (diffMins < 60) return `${diffMins}m`;
  if (diffHours < 24) return `${diffHours}h`;
  return `${diffDays}d`;
};

// Helper to group experiments by time period
const groupExperiments = (experiments: ProcessInfo[]): Map<string, ProcessInfo[]> => {
  const groups = new Map<string, ProcessInfo[]>();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);
  const monthAgo = new Date(today.getTime() - 30 * 86400000);

  experiments.forEach((exp) => {
    if (!exp.timestamp) return;
    const date = new Date(exp.timestamp);
    let group: string;

    if (date >= today) {
      group = 'Today';
    } else if (date >= yesterday) {
      group = 'Yesterday';
    } else if (date >= weekAgo) {
      group = 'Past Week';
    } else if (date >= monthAgo) {
      group = 'Past Month';
    } else {
      group = 'Older';
    }

    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group)!.push(exp);
  });

  return groups;
};

export const GraphHeader: React.FC<GraphHeaderProps> = ({
  runName,
  isDarkTheme,
  sessionId,
  experiments = [],
  onNavigateToExperiment,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      // Focus search input when dropdown opens
      setTimeout(() => searchInputRef.current?.focus(), 0);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Filter and group experiments
  const filteredExperiments = experiments.filter((exp) => {
    if (!searchQuery.trim()) return true;
    const name = exp.run_name || '';
    return name.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const groupedExperiments = groupExperiments(filteredExperiments);
  const groupOrder = ['Today', 'Yesterday', 'Past Week', 'Past Month', 'Older'];

  // Use VS Code CSS variables for theme-aware colors
  const colors = {
    text: 'var(--vscode-foreground)',
    textMuted: 'var(--vscode-descriptionForeground)',
    border: 'var(--vscode-panel-border, var(--vscode-widget-border))',
    bg: 'var(--vscode-sideBar-background, var(--vscode-editor-background))',
    bgHover: 'var(--vscode-list-hoverBackground)',
    inputBg: 'var(--vscode-input-background)',
    dropdownBg: 'var(--vscode-dropdown-background, var(--vscode-editor-background))',
  };

  const handleExperimentClick = (exp: ProcessInfo) => {
    setIsOpen(false);
    setSearchQuery('');
    onNavigateToExperiment?.(exp);
  };

  return (
    <div
      ref={dropdownRef}
      style={{
        padding: '9px 16px 0 16px',
        position: 'relative',
      }}
    >
      {/* Title Row - Clickable */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <span
          style={{
            fontSize: '13px',
            fontWeight: 500,
            color: colors.text,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {runName || 'Untitled'}
        </span>
        {/* Chevron Icon */}
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill={colors.text}
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.15s ease',
            flexShrink: 0,
          }}
        >
          <path d="M4.957 5.543L8 8.586l3.043-3.043.914.914L8 10.414 4.043 6.457l.914-.914z" />
        </svg>
      </div>

      {/* Horizontal Line - Full Width */}
      {sessionId && (
        <div
          style={{
            width: 'calc(100% + 16px)',
            height: '1px',
            backgroundColor: colors.border,
            margin: '8px 0',
            marginLeft: '-16px',
          }}
        />
      )}

      {/* Dropdown Panel */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: '12px',
            width: '280px',
            maxHeight: '400px',
            backgroundColor: colors.dropdownBg,
            border: `1px solid ${colors.border}`,
            borderRadius: '6px',
            boxShadow: isDarkTheme
              ? '0 4px 16px rgba(0, 0, 0, 0.4)'
              : '0 4px 16px rgba(0, 0, 0, 0.15)',
            zIndex: 1000,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Search Input */}
          <div
            style={{
              padding: '8px',
              borderBottom: `1px solid ${colors.border}`,
            }}
          >
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search sessions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 8px',
                fontSize: '12px',
                border: `1px solid ${colors.border}`,
                borderRadius: '4px',
                backgroundColor: colors.inputBg,
                color: colors.text,
                outline: 'none',
                boxSizing: 'border-box',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = isDarkTheme ? '#0e639c' : '#007acc';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = colors.border;
              }}
            />
          </div>

          {/* Experiments List */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '4px 0',
            }}
          >
            {filteredExperiments.length === 0 ? (
              <div
                style={{
                  padding: '12px 16px',
                  fontSize: '12px',
                  color: colors.textMuted,
                  textAlign: 'center',
                }}
              >
                No experiments found
              </div>
            ) : (
              groupOrder.map((group) => {
                const groupExps = groupedExperiments.get(group);
                if (!groupExps || groupExps.length === 0) return null;

                return (
                  <div key={group}>
                    {/* Group Header */}
                    <div
                      style={{
                        padding: '6px 12px 4px 12px',
                        fontSize: '11px',
                        fontWeight: 500,
                        color: colors.textMuted,
                      }}
                    >
                      {group}
                    </div>

                    {/* Group Items */}
                    {groupExps.map((exp) => (
                      <div
                        key={exp.session_id}
                        onClick={() => handleExperimentClick(exp)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 12px',
                          cursor: 'pointer',
                          backgroundColor:
                            exp.session_id === sessionId ? colors.bgHover : 'transparent',
                        }}
                        onMouseEnter={(e) => {
                          if (exp.session_id !== sessionId) {
                            e.currentTarget.style.backgroundColor = colors.bgHover;
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (exp.session_id !== sessionId) {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }
                        }}
                      >
                        <span
                          style={{
                            fontSize: '12px',
                            color: colors.text,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            flex: 1,
                            fontWeight: exp.session_id === sessionId ? 600 : 400,
                          }}
                        >
                          {exp.run_name || 'Untitled'}
                        </span>
                        <span
                          style={{
                            fontSize: '11px',
                            color: colors.textMuted,
                            marginLeft: '8px',
                            flexShrink: 0,
                          }}
                        >
                          {exp.timestamp ? getRelativeTime(exp.timestamp) : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
