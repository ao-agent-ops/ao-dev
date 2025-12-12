import React, { useState, useLayoutEffect } from 'react';
import { ProcessCard } from './ProcessCard';
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
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['running', 'similar', 'finished']));
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

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
    if (typeof window !== 'undefined' && window.vscode) {
      window.vscode.postMessage({ type: 'requestExperimentRefresh' });
    }
  }, []); // Empty dependency array - only runs once on mount

  // Footer layout constants
  const footerHeight = 60; // px

  // Debug logging
  console.log('ExperimentsView render - runningProcesses:', runningProcesses);
  console.log('ExperimentsView render - finishedProcesses:', finishedProcesses);
  console.log('ExperimentsView render - user:', user);
  const containerStyle: React.CSSProperties = {
    position: 'relative',
    padding: '20px 20px',
    paddingBottom: `${footerHeight + 20}px`, // reserve space for footer
    height: '100%',
    maxHeight: '100%',
    overflowY: 'auto',
    boxSizing: 'border-box',
    backgroundColor: isDarkTheme ? '#252525' : '#F0F2F0',
    color: 'var(--vscode-foreground)',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: '600',
    marginBottom: '20px',
    color: isDarkTheme ? '#FFFFFF' : '#000000',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const footerStyle: React.CSSProperties = {
    position: 'fixed',
    left: 0,
    right: 0,
    bottom: 0,
    height: `${footerHeight}px`,
    padding: '8px 12px',
    boxSizing: 'border-box',
    borderTop: `1px solid ${isDarkTheme ? '#3a3a3a' : '#e0e0e0'}`,
    backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    zIndex: 10,
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
    padding: '12px 16px',
    fontSize: 14,
    fontWeight: 'normal',
    color: '#ffffff',
    backgroundColor: '#000000',
    border: '1px solid #007acc',
    borderRadius: 6,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    transition: 'background-color 0.2s, border-color 0.2s',
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

    const query = searchQuery.toLowerCase();
    return processes.filter(process => {
      const runName = (process.run_name || '').toLowerCase();
      const sessionId = (process.session_id || '').toLowerCase();
      const notes = (process.notes || '').toLowerCase();

      return runName.includes(query) ||
             sessionId.includes(query) ||
             notes.includes(query);
    });
  };

  // Apply filtering to all process lists
  const filteredRunning = filterProcesses(runningProcesses);
  const filteredSimilar = filterProcesses(similarProcesses);
  const filteredFinished = filterProcesses(finishedProcesses);

  const renderExperimentSection = (
    processes: ProcessInfo[],
    sectionTitle: string,
    sectionPrefix: string,
    marginTop?: number
  ) => {
    const isExpanded = expandedSections.has(sectionPrefix);

    return (
      <>
        <div 
          style={{ 
            ...titleStyle, 
            ...(marginTop && { marginTop }),
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            userSelect: 'none'
          }}
          onClick={() => toggleSection(sectionPrefix)}
        >
          <i 
            className={`codicon ${isExpanded ? 'codicon-chevron-down' : 'codicon-chevron-right'}`}
            style={{ 
              fontSize: '12px',
              transition: 'transform 0.2s ease',
              transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)'
            }}
          />
          {sectionTitle} ({processes.length})
        </div>
        <div
          style={{
            maxHeight: isExpanded ? (processes.length > 0 ? `${processes.length * 100}px` : '28px') : '0px',
            overflow: 'hidden',
            transition: 'max-height 0.3s ease-in-out, opacity 0.2s ease',
            opacity: isExpanded ? 1 : 0
          }}
        >
          {processes.length > 0 ? (
            processes.map((process) => {
              const cardId = `${sectionPrefix}-${process.session_id}`;
              const isHovered = hoveredCards.has(cardId);
              const nodeColors = process.color_preview || [];
              return (
                <ProcessCard
                  key={process.session_id}
                  process={process}
                  isHovered={isHovered}
                  isDarkTheme={isDarkTheme}
                  nodeColors={nodeColors}
                  onClick={() => onCardClick && onCardClick(process)}
                  onMouseEnter={() => handleCardHover(cardId, true)}
                  onMouseLeave={() => handleCardHover(cardId, false)}
                />
              );
            })
          ) : (
            <div
              style={{
                padding: '4px 16px 8px 16px',
                color: isDarkTheme ? '#CCCCCC' : '#666666',
                fontSize: '12px',
                fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
                fontStyle: 'italic'
              }}
            >
              No {sectionTitle.toLowerCase()} processes
            </div>
          )}
        </div>
      </>
    );
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--vscode-editorWidget-border)',
    padding: '10px 20px',
    margin: '-20px -20px 20px -20px', // Extend to edges of container
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
    position: 'relative',
    marginBottom: '16px',
  };

  const searchIconStyle: React.CSSProperties = {
    position: 'absolute',
    left: '10px',
    top: '50%',
    transform: 'translateY(-50%)',
    color: isDarkTheme ? '#858585' : '#666666',
    pointerEvents: 'none',
    fontSize: '13px',
  };

  const searchBarInputStyle: React.CSSProperties = {
    width: '100%',
    padding: '5px 10px 5px 28px',
    fontSize: '13px',
    backgroundColor: isDarkTheme ? '#3c3c3c' : '#ffffff',
    color: isDarkTheme ? '#cccccc' : '#333333',
    border: `1px solid ${isDarkTheme ? '#555555' : '#cccccc'}`,
    borderRadius: '4px',
    outline: 'none',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
    boxSizing: 'border-box',
  };

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
            <i className="codicon codicon-search" style={searchIconStyle} />
            <input
              type="text"
              placeholder="Search experiments..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={searchBarInputStyle}
            />
          </div>

          {renderExperimentSection(filteredRunning, 'Running', 'running')}
          {renderExperimentSection(filteredSimilar, 'Similar', 'similar', filteredRunning.length > 0 ? 32 : 0)}
          {renderExperimentSection(filteredFinished, 'Finished', 'finished', (filteredRunning.length > 0 || filteredSimilar.length > 0) ? 32 : 0)}
        </>
      )}

      {/* Footer (always present) */}
      <div style={footerStyle}>
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
              (e.currentTarget as HTMLButtonElement).style.borderColor = '#0098ff';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = '#007acc';
            }}
          >
            Sign in with
            <IconGoogle />
          </button>
        )}
      </div>
    </div>
  );
};