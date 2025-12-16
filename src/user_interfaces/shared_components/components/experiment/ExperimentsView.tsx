import React, { useState, useLayoutEffect } from 'react';
import { ProcessInfo } from '../../types';

interface UserInfo {
  displayName?: string;
  avatarUrl?: string;
  email?: string;
}

interface ExperimentsViewProps {
  similarProcesses: ProcessInfo[];
  runningProcesses: ProcessInfo[];
  finishedProcesses: ProcessInfo[];
  onCardClick?: (process: ProcessInfo) => void;
  isDarkTheme?: boolean;
  user?: UserInfo;
  onLogout?: () => void;
  onLogin?: () => void;
  showHeader?: boolean;
  onModeChange?: (mode: 'Local' | 'Remote') => void;
  currentMode?: 'Local' | 'Remote';
}

export const ExperimentsView: React.FC<ExperimentsViewProps> = ({
  similarProcesses,
  runningProcesses,
  finishedProcesses,
  onCardClick,
  isDarkTheme = false,
  user,
  onLogout,
  onLogin,
  showHeader = false,
  onModeChange,
  currentMode = 'Local',
}) => {
  const [hoveredCards, setHoveredCards] = useState<Set<string>>(new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['running', 'finished']));
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchCaseSensitive, setSearchCaseSensitive] = useState(false);
  const [searchWholeWord, setSearchWholeWord] = useState(false);
  const [searchInputFocused, setSearchInputFocused] = useState(false);

  // Section sizes (percentages of available height)
  const [runningSizePercent, setRunningSizePercent] = useState(20);
  // finishedSizePercent is calculated as: 100 - runningSizePercent

  const [resizing, setResizing] = useState<'running' | null>(null);
  const [startY, setStartY] = useState(0);
  const [startSize, setStartSize] = useState(0);

  // Sign out icon from VSCode codicons
  const IconSignOut = ({ size = 16 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
      <path d="M4.5 2C3.119 2 2 3.119 2 4.5V11.5C2 12.881 3.119 14 4.5 14H9.5C9.776 14 10 13.776 10 13.5C10 13.224 9.776 13 9.5 13H4.5C3.672 13 3 12.328 3 11.5V4.5C3 3.672 3.672 3 4.5 3H9.5C9.776 3 10 2.776 10 2.5C10 2.224 9.776 2 9.5 2H4.5Z"/>
      <path d="M13.854 7.646L10.854 4.646C10.659 4.451 10.342 4.451 10.147 4.646C9.952 4.841 9.952 5.158 10.147 5.353L12.293 7.499H5.5C5.224 7.499 5 7.723 5 7.999C5 8.275 5.224 8.499 5.5 8.499H12.293L10.147 10.645C9.952 10.84 9.952 11.157 10.147 11.352C10.342 11.547 10.659 11.547 10.854 11.352L13.854 8.352C14.049 8.157 14.049 7.841 13.854 7.646Z"/>
    </svg>
  );

  const IconGoogle = ({ size = 20 }: { size?: number }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width={size} height={size}>
      <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
      <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
      <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
      <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
    </svg>
  );

  // Request experiment list when component mounts and is ready to display data
  useLayoutEffect(() => {
    // Check if we're in a VS Code environment
    if (typeof window !== 'undefined' && (window as any).vscode) {
      (window as any).vscode.postMessage({ type: 'requestExperimentRefresh' });
    }
  }, []); // Empty dependency array - only runs once on mount

  // Handle resize dragging
  const handleMouseDown = (section: 'running', e: React.MouseEvent) => {
    e.preventDefault();
    setResizing(section);
    setStartY(e.clientY);
    setStartSize(runningSizePercent);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!resizing) return;

    const containerHeight = window.innerHeight - footerHeight - 100; // Approximate available height
    const deltaY = e.clientY - startY;
    const deltaPercent = (deltaY / containerHeight) * 100;

    if (resizing === 'running') {
      const newSize = Math.max(10, Math.min(80, startSize + deltaPercent));
      setRunningSizePercent(newSize);
    }
  };

  const handleMouseUp = () => {
    setResizing(null);
  };

  // Add/remove mouse event listeners for dragging
  useLayoutEffect(() => {
    if (resizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [resizing, startY, startSize]);

  // Footer layout constants
  const footerHeight = 60; // px

  // Debug logging
  console.log('ExperimentsView render - runningProcesses:', runningProcesses);
  console.log('ExperimentsView render - finishedProcesses:', finishedProcesses);
  console.log('ExperimentsView render - user:', user);
  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: isDarkTheme ? '#1e1e1e' : '#F0F2F0',
    color: 'var(--vscode-foreground)',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const userSectionContainerStyle: React.CSSProperties = {
    position: 'fixed',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
    borderTop: `1px solid ${isDarkTheme ? '#2b2b2b' : '#e5e5e5'}`,
    zIndex: 10,
    padding: '8px 16px',
  };

  const userRowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    cursor: user ? 'pointer' : 'default',
    flex: '1',
  };

  const loginButtonStyle: React.CSSProperties = {
    width: '100%',
    padding: '6px 16px',
    fontSize: '13px',
    fontWeight: 'normal',
    color: isDarkTheme ? '#cccccc' : '#333333',
    backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
    border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#cccccc'}`,
    borderRadius: 0,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    transition: 'background-color 0.1s',
  };

  const avatarStyle: React.CSSProperties = {
    width: 44,
    height: 44,
    borderRadius: '50%',
    objectFit: 'cover',
    backgroundColor: '#ddd',
  };

  const nameBlockStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    lineHeight: 1,
    minWidth: 0,
  };

  const nameStyle: React.CSSProperties = {
    fontSize: 14,
    fontWeight: 600,
    color: isDarkTheme ? '#FFFFFF' : '#111111',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  };

  const emailStyle: React.CSSProperties = {
    marginTop:5,
    fontSize: 12,
    color: isDarkTheme ? '#BBBBBB' : '#666666',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  };

  const handleCardHover = (cardId: string, isEntering: boolean) => {
    setHoveredCards((prev) => {
      const newSet = new Set(prev);
      if (isEntering) {
        newSet.add(cardId);
      } else {
        newSet.delete(cardId);
      }
      return newSet;
    });
  };

  const handleLogoutClick = () => {
    if (onLogout) onLogout();
    else console.log('Logout clicked (no handler provided)');
  };

  const handleLoginClick = () => {
    if (onLogin) onLogin();
    else console.log('Login clicked (no handler provided)');
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(sectionId)) {
        newSet.delete(sectionId);
      } else {
        newSet.add(sectionId);
      }
      return newSet;
    });
  };

  const handleModeChange = (mode: 'Local' | 'Remote') => {
    console.log(mode);
    setDropdownOpen(false);

    // Call parent handler to send message to server
    if (onModeChange) {
      onModeChange(mode);
    }
  };

  // Filter processes based on search query
  const filterProcesses = (processes: ProcessInfo[]) => {
    if (!searchQuery.trim()) return processes;

    return processes.filter(process => {
      const runName = process.run_name || '';
      const sessionId = process.session_id || '';
      const notes = process.notes || '';

      // Prepare search query and text based on case sensitivity
      const query = searchCaseSensitive ? searchQuery : searchQuery.toLowerCase();
      const textToSearch = [
        searchCaseSensitive ? runName : runName.toLowerCase(),
        searchCaseSensitive ? sessionId : sessionId.toLowerCase(),
        searchCaseSensitive ? notes : notes.toLowerCase(),
      ];

      // Check if any field matches
      return textToSearch.some(text => {
        if (searchWholeWord) {
          // Whole word matching: use word boundaries
          const regex = new RegExp(`\\b${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, searchCaseSensitive ? '' : 'i');
          return regex.test(text);
        } else {
          // Simple substring matching
          return text.includes(query);
        }
      });
    });
  };

  // Apply filtering to all process lists
  const filteredRunning = filterProcesses(runningProcesses);
  const filteredFinished = filterProcesses(finishedProcesses);

  const renderExperimentSection = (
    processes: ProcessInfo[],
    sectionTitle: string,
    sectionPrefix: string,
    sizePercent: number,
    showResizeHandle: boolean
  ) => {
    const isExpanded = expandedSections.has(sectionPrefix);

    const sectionHeaderStyle: React.CSSProperties = {
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      padding: '4px 16px',
      fontSize: '11px',
      fontWeight: 700,
      letterSpacing: '0.5px',
      textTransform: 'uppercase',
      color: isDarkTheme ? '#cccccc' : '#616161',
      cursor: 'pointer',
      userSelect: 'none',
      fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
    };

    const chevronStyle: React.CSSProperties = {
      fontSize: '16px',
      transition: 'transform 0.1s ease',
      display: 'flex',
      alignItems: 'center',
    };

    const listContainerStyle: React.CSSProperties = {
      display: 'flex',
      flexDirection: 'column',
      height: isExpanded ? `${sizePercent}%` : 'auto',
      minHeight: isExpanded ? '0' : undefined,
      overflow: 'hidden',
    };

    const listItemsStyle: React.CSSProperties = {
      overflowY: 'auto',
      overflowX: 'hidden',
      flex: 1,
      paddingBottom: '12px',
    };

    const listItemStyle: React.CSSProperties = {
      display: 'flex',
      alignItems: 'center',
      padding: '2px 16px 2px 24px',
      fontSize: '13px',
      color: isDarkTheme ? '#cccccc' : '#333333',
      cursor: 'pointer',
      userSelect: 'none',
      fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
      height: '22px',
      lineHeight: '22px',
    };

    const emptyMessageStyle: React.CSSProperties = {
      padding: '8px 16px 8px 24px',
      fontSize: '12px',
      color: isDarkTheme ? '#858585' : '#8e8e8e',
      fontStyle: 'italic',
      fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
    };

    const resizeHandleStyle: React.CSSProperties = {
      height: '4px',
      cursor: 'ns-resize',
      backgroundColor: 'transparent',
      borderTop: `1px solid ${isDarkTheme ? '#2b2b2b' : '#e5e5e5'}`,
      borderBottom: `1px solid ${isDarkTheme ? '#2b2b2b' : '#e5e5e5'}`,
      transition: 'background-color 0.1s',
    };

    return (
      <>
        <div style={listContainerStyle}>
          <div
            style={sectionHeaderStyle}
            onClick={() => toggleSection(sectionPrefix)}
          >
            <i
              className={`codicon ${isExpanded ? 'codicon-chevron-down' : 'codicon-chevron-right'}`}
              style={chevronStyle}
            />
            <span>{sectionTitle}</span>
          </div>
          {isExpanded && (
            <div style={listItemsStyle}>
              {processes.length > 0 ? (
                processes.map((process) => {
                  const cardId = `${sectionPrefix}-${process.session_id}`;
                  const isHovered = hoveredCards.has(cardId);

                  // Determine status icon based on process state
                  const getStatusIcon = () => {
                    if (process.status === 'running') {
                      return <i className="codicon codicon-loading codicon-modifier-spin" style={{ marginRight: '8px', fontSize: '16px' }} />;
                    }
                    const result = process.result?.toLowerCase();
                    if (result === 'failed') {
                      return <i className="codicon codicon-error" style={{ marginRight: '8px', fontSize: '16px', color: '#e05252' }} />;
                    }
                    if (result === 'satisfactory') {
                      return <i className="codicon codicon-pass" style={{ marginRight: '8px', fontSize: '16px', color: '#7fc17b' }} />;
                    }
                    return <i className="codicon codicon-circle-outline" style={{ marginRight: '8px', fontSize: '16px', opacity: 0.6 }} />;
                  };

                  // Format timestamp to dd/mm/yyyy hh:mm
                  const formatDate = (timestamp?: string) => {
                    if (!timestamp) return 'No date';
                    try {
                      const date = new Date(timestamp);
                      const day = String(date.getDate()).padStart(2, '0');
                      const month = String(date.getMonth() + 1).padStart(2, '0');
                      const year = date.getFullYear();
                      const hours = String(date.getHours()).padStart(2, '0');
                      const minutes = String(date.getMinutes()).padStart(2, '0');
                      return `${day}/${month}/${year} ${hours}:${minutes}`;
                    } catch {
                      return timestamp;
                    }
                  };

                  return (
                    <div
                      key={process.session_id}
                      style={{
                        ...listItemStyle,
                        backgroundColor: isHovered
                          ? (isDarkTheme ? '#2a2d2e' : '#e8e8e8')
                          : 'transparent',
                      }}
                      onClick={() => onCardClick && onCardClick(process)}
                      onMouseEnter={() => handleCardHover(cardId, true)}
                      onMouseLeave={() => handleCardHover(cardId, false)}
                    >
                      {getStatusIcon()}
                      <span style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}>
                        {formatDate(process.timestamp)}
                      </span>
                      <span style={{
                        fontSize: '11px',
                        color: isDarkTheme ? '#858585' : '#8e8e8e',
                        marginLeft: '8px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '150px'
                      }}>
                        {process.run_name || 'Untitled'}
                      </span>
                    </div>
                  );
                })
              ) : (
                <div style={emptyMessageStyle}>
                  No {sectionTitle.toLowerCase()}
                </div>
              )}
            </div>
          )}
        </div>
        {showResizeHandle && isExpanded && (
          <div
            style={resizeHandleStyle}
            onMouseDown={(e) => handleMouseDown(sectionPrefix as 'running', e)}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = isDarkTheme ? '#007acc' : '#0078d4';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          />
        )}
      </>
    );
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: `1px solid ${isDarkTheme ? '#2b2b2b' : '#e5e5e5'}`,
    padding: '8px 16px',
    flexShrink: 0,
  };

  const dropdownStyle: React.CSSProperties = {
    position: 'relative',
  };

  const dropdownButtonStyle: React.CSSProperties = {
    padding: '4px 8px',
    fontSize: '12px',
    backgroundColor: isDarkTheme ? '#3c3c3c' : '#f3f3f3',
    color: isDarkTheme ? '#cccccc' : '#333333',
    border: `1px solid ${isDarkTheme ? '#555555' : '#cccccc'}`,
    borderRadius: '4px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const dropdownMenuStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    right: 0,
    marginTop: '4px',
    backgroundColor: isDarkTheme ? '#3c3c3c' : '#ffffff',
    border: `1px solid ${isDarkTheme ? '#555555' : '#cccccc'}`,
    borderRadius: '4px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
    zIndex: 1000,
    minWidth: '100px',
  };

  const dropdownItemStyle: React.CSSProperties = {
    padding: '6px 12px',
    fontSize: '12px',
    color: isDarkTheme ? '#cccccc' : '#333333',
    cursor: 'pointer',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const headerTitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--vscode-editor-foreground)',
  };

  const searchBarContainerStyle: React.CSSProperties = {
    padding: '8px 16px',
    flexShrink: 0,
  };

  const searchInputWrapperStyle: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    backgroundColor: isDarkTheme ? '#3c3c3c' : '#ffffff',
    border: searchInputFocused
      ? `1px solid ${isDarkTheme ? '#007acc' : '#007acc'}`
      : `1px solid ${isDarkTheme ? '#3c3c3c' : '#cccccc'}`,
    borderRadius: 0,
  };

  const searchIconStyle: React.CSSProperties = {
    position: 'absolute',
    left: '8px',
    color: isDarkTheme ? '#858585' : '#666666',
    pointerEvents: 'none',
    fontSize: '13px',
  };

  const searchBarInputStyle: React.CSSProperties = {
    flex: 1,
    padding: '4px 8px 4px 28px',
    fontSize: '13px',
    backgroundColor: 'transparent',
    color: isDarkTheme ? '#cccccc' : '#333333',
    border: 'none',
    outline: 'none',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const searchToggleButtonStyle = (isActive: boolean): React.CSSProperties => ({
    padding: '2px 4px',
    fontSize: '13px',
    backgroundColor: isActive ? (isDarkTheme ? '#094771' : '#0078d4') : 'transparent',
    color: isActive ? '#ffffff' : (isDarkTheme ? '#cccccc' : '#666666'),
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background-color 0.1s, color 0.1s',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
    minWidth: '22px',
    height: '22px',
  });

  const renderDropdown = () => (
    <div style={dropdownStyle}>
      <button
        style={dropdownButtonStyle}
        onClick={() => setDropdownOpen(!dropdownOpen)}
      >
        <i className="codicon codicon-database" />
        {currentMode}
        <i className={`codicon ${dropdownOpen ? 'codicon-chevron-up' : 'codicon-chevron-down'}`} />
      </button>
      {dropdownOpen && (
        <div style={dropdownMenuStyle}>
          <div
            style={{
              ...dropdownItemStyle,
              backgroundColor: currentMode === 'Local' ? (isDarkTheme ? '#094771' : '#e3f2fd') : 'transparent',
            }}
            onClick={() => handleModeChange('Local')}
          >
            Local
          </div>
          <div
            style={{
              ...dropdownItemStyle,
              backgroundColor: currentMode === 'Remote' ? (isDarkTheme ? '#094771' : '#e3f2fd') : 'transparent',
            }}
            onClick={() => handleModeChange('Remote')}
          >
            Remote
          </div>
        </div>
      )}
    </div>
  );

  // Show lock screen if in Remote mode without user
  const showLockScreen = currentMode === 'Remote' && !user;

  return (
    <div style={containerStyle}>
      {showHeader && (
        <div style={headerStyle}>
          <h3 style={headerTitleStyle}>Experiments</h3>
          {renderDropdown()}
        </div>
      )}
      {showLockScreen ? (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          padding: '40px 20px',
          textAlign: 'center'
        }}>
          <div style={{ marginBottom: '20px' }}>
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="11" width="18" height="10" rx="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h2 style={{ marginBottom: '10px', fontSize: '18px', fontWeight: 600 }}>Authentication Required</h2>
          <p style={{ marginBottom: '30px', opacity: 0.8, fontSize: '14px' }}>
            Please sign in to access remote experiments
          </p>
        </div>
      ) : (
        <>
          {/* Search Bar */}
          <div style={searchBarContainerStyle}>
            <div style={searchInputWrapperStyle}>
              <i className="codicon codicon-search" style={searchIconStyle} />
              <input
                type="text"
                placeholder="Search experiments..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => setSearchInputFocused(true)}
                onBlur={() => setSearchInputFocused(false)}
                style={searchBarInputStyle}
              />
              <button
                style={searchToggleButtonStyle(searchCaseSensitive)}
                onClick={() => setSearchCaseSensitive(!searchCaseSensitive)}
                title="Match Case"
                onMouseEnter={(e) => {
                  if (!searchCaseSensitive) {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = isDarkTheme ? '#094771' : '#0078d4';
                    (e.currentTarget as HTMLButtonElement).style.color = '#ffffff';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!searchCaseSensitive) {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
                    (e.currentTarget as HTMLButtonElement).style.color = isDarkTheme ? '#cccccc' : '#666666';
                  }
                }}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
                  <path fillRule="evenodd" clipRule="evenodd" d="M4.02602 3.34176C4.16218 2.93404 4.83818 2.93398 4.97426 3.34176L6.97426 9.34274C6.97526 9.34674 6.97817 9.35544 6.97817 9.35544L7.97426 12.3427C8.06126 12.6047 7.91984 12.8875 7.65786 12.9756C7.60486 12.9926 7.55165 13.0009 7.49965 13.0009C7.29082 13.0008 7.09602 12.868 7.02602 12.6591L6.14028 10.0009H2.86L1.97426 12.6591C1.88728 12.919 1.60634 13.0634 1.34243 12.9746C1.08043 12.8866 0.93902 12.6038 1.02602 12.3418L2.02211 9.35544C2.02311 9.35144 2.02602 9.34274 2.02602 9.34274L4.02602 3.34176ZM3.19399 8.99997H5.80629L4.49965 5.08102L3.19399 8.99997Z"/>
                  <path fillRule="evenodd" clipRule="evenodd" d="M11.8581 6.66794C13.165 6.73296 13.9427 7.48427 13.9967 8.69626L13.9997 8.83297V12.5078C13.9957 12.7568 13.809 12.9621 13.568 12.9951L13.4997 13C13.2469 12.9998 13.0376 12.8121 13.0045 12.5683L12.9997 12.5V12.4297C12.3407 12.8066 11.7316 13 11.1666 13C9.94081 12.9998 8.99965 12.1369 8.99965 10.833C8.99967 9.68299 9.79211 8.82889 11.1061 8.66989C11.7279 8.59493 12.3589 8.64164 12.9987 8.80954C12.9915 8.07194 12.6279 7.70704 11.8082 7.66598C11.1672 7.63398 10.7158 7.72415 10.4518 7.90915C10.2258 8.06799 9.91347 8.01301 9.75551 7.78708C9.59671 7.56115 9.65178 7.24878 9.87758 7.09079C10.3165 6.78283 10.9138 6.64715 11.6666 6.6611L11.8581 6.66794ZM12.7965 9.8154C12.2587 9.66749 11.7361 9.62551 11.2262 9.68747C10.4042 9.78747 9.99868 10.2244 9.99868 10.8574C9.99884 11.5881 10.474 12.0242 11.1657 12.0244C11.6196 12.0244 12.1777 11.8137 12.8336 11.3818L12.9987 11.2695V9.87594L12.7965 9.8154Z"/>
                </svg>
              </button>
              <button
                style={searchToggleButtonStyle(searchWholeWord)}
                onClick={() => setSearchWholeWord(!searchWholeWord)}
                title="Match Whole Word"
                onMouseEnter={(e) => {
                  if (!searchWholeWord) {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = isDarkTheme ? '#094771' : '#0078d4';
                    (e.currentTarget as HTMLButtonElement).style.color = '#ffffff';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!searchWholeWord) {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
                    (e.currentTarget as HTMLButtonElement).style.color = isDarkTheme ? '#cccccc' : '#666666';
                  }
                }}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
                  <path d="M15.5 12.5C15.776 12.5 16 12.724 16 13V13.5C16 14.327 15.327 15 14.5 15H1.5C0.673 15 0 14.327 0 13.5V13C0 12.724 0.224 12.5 0.5 12.5C0.776 12.5 1 12.724 1 13V13.5C1 13.775 1.224 14 1.5 14H14.5C14.776 14 15 13.775 15 13.5V13C15 12.724 15.224 12.5 15.5 12.5Z"/>
                  <path fillRule="evenodd" clipRule="evenodd" d="M4.8584 5.6709C6.16516 5.73603 6.94308 6.48734 6.99707 7.69922L7 7.83594V11.5107C6.996 11.7596 6.80919 11.9649 6.56836 11.998L6.5 12.0029C6.24709 12.0029 6.038 11.8152 6.00488 11.5713L6 11.5029V11.4326C5.341 11.8096 4.73199 12.0029 4.16699 12.0029C2.941 12.0029 2 11.1399 2 9.83594C2.00003 8.68597 2.79247 7.83185 4.10645 7.67285C4.7283 7.59793 5.35918 7.64552 5.99902 7.81348C5.99202 7.07548 5.62762 6.70995 4.80762 6.66895C4.16686 6.637 3.7161 6.72717 3.45215 6.91211C3.22615 7.07111 2.91386 7.01604 2.75586 6.79004C2.5969 6.56404 2.65194 6.25174 2.87793 6.09375C3.31692 5.78579 3.91404 5.65006 4.66699 5.66406L4.8584 5.6709ZM5.79688 8.81836C5.25888 8.67037 4.73558 8.62843 4.22559 8.69043C3.40389 8.79054 2.99902 9.22747 2.99902 9.86035C2.99917 10.5911 3.47413 11.0273 4.16602 11.0273C4.62001 11.0273 5.17799 10.8168 5.83398 10.3848L5.99902 10.2725V8.87891L5.79688 8.81836Z"/>
                  <path fillRule="evenodd" clipRule="evenodd" d="M9.55078 2.00586C9.78578 2.02986 9.97307 2.21715 9.99707 2.45215C10 2.46907 10 2.48601 10 2.50293V6.60254C10.418 6.22566 10.9371 6.00293 11.5 6.00293C12.881 6.00293 14 7.34596 14 9.00293C14 10.6599 12.881 12.0029 11.5 12.0029C10.9371 12.0029 10.418 11.7802 10 11.4033V11.5029C10 11.7619 9.80278 11.974 9.55078 12C9.53385 12.003 9.51693 12.0029 9.5 12.0029C9.224 12.0029 9 11.7789 9 11.5029V2.50293C9 2.486 9.00095 2.46907 9.00293 2.45215C9.02793 2.20015 9.241 2.00293 9.5 2.00293C9.51692 2.00293 9.53386 2.00388 9.55078 2.00586ZM11.4355 7.00391C11.0307 7.03208 10.5769 7.31545 10.29 7.82227C10.1232 8.12611 10.018 8.49479 10.002 8.89453C9.99995 8.92952 10 8.96597 10 9.00195C10 9.03795 10.001 9.07438 10.002 9.10938C10.018 9.50814 10.1222 9.87582 10.2891 10.1797C10.576 10.6875 11.0307 10.9728 11.4355 11C11.4565 11.002 11.478 11.002 11.5 11.002C11.522 11.002 11.5435 11.001 11.5645 11C11.9693 10.9728 12.424 10.6875 12.7109 10.1797C12.8778 9.87582 12.982 9.50814 12.998 9.10938C13 9.07438 13 9.03795 13 9.00195C13 8.96597 12.999 8.92952 12.998 8.89453C12.982 8.49479 12.8768 8.12611 12.71 7.82227C12.4231 7.31545 11.9693 7.03109 11.5645 7.00391C11.5435 7.00191 11.522 7.00195 11.5 7.00195C11.478 7.00195 11.4565 7.00291 11.4355 7.00391Z"/>
                </svg>
              </button>
            </div>
          </div>

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            overflow: 'hidden',
            marginBottom: `${footerHeight}px`
          }}>
            {renderExperimentSection(filteredRunning, 'Running', 'running', runningSizePercent, true)}
            {renderExperimentSection(filteredFinished, 'Finished', 'finished', 100 - runningSizePercent, false)}
          </div>
        </>
      )}

      {/* User Section (always present at bottom) */}
      <div style={userSectionContainerStyle}>
        {user ? (
          <div style={userRowStyle}>
            <img
              src={user.avatarUrl || 'https://www.gravatar.com/avatar/?d=mp&s=200'}
              alt={user.displayName || 'User avatar'}
              style={avatarStyle}
            />
            <div style={nameBlockStyle}>
              <div style={nameStyle}>{user.displayName || 'User'}</div>
              <div style={emailStyle}>{user.email || ''}</div>
            </div>
            <button
              onClick={handleLogoutClick}
              style={{
                marginLeft: 'auto',
                padding: '4px',
                backgroundColor: 'transparent',
                color: isDarkTheme ? '#cccccc' : '#333333',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: 0.7,
                transition: 'opacity 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.opacity = '1';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = '0.7';
              }}
              title="Logout"
            >
              <IconSignOut size={20} />
            </button>
          </div>
        ) : (
          <button
            style={loginButtonStyle}
            onClick={handleLoginClick}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = isDarkTheme ? '#2a2d2e' : '#e8e8e8';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = isDarkTheme ? '#1e1e1e' : '#ffffff';
            }}
          >
            Sign in with Google
            <IconGoogle size={16} />
          </button>
        )}
      </div>
    </div>
  );
};