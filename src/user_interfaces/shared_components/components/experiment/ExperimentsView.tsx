import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { useIsVsCodeDarkTheme } from '../../utils/themeUtils';
import { ProcessCard } from './ProcessCard';
import { GraphData, ProcessInfo } from '../../types';

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
  const [menuOpen, setMenuOpen] = useState(false);
  const userRowRef = useRef<HTMLDivElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Simple inline icons to avoid adding dependencies
  const IconLogout = ({ size = 16 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <path d="M16 13v-2H7V8l-5 4 5 4v-3z" fill="currentColor" />
      <path d="M20 3h-8v2h8v14h-8v2h8c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z" fill="currentColor" />
    </svg>
  );

  // Close menu when clicking outside or pressing Escape
  useEffect(() => {
    if (!menuOpen) return;

    const handleDocClick = (e: MouseEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (userRowRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setMenuOpen(false);
    };

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };

    document.addEventListener('mousedown', handleDocClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleDocClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [menuOpen]);

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

  const emptyStateStyle: React.CSSProperties = {
    textAlign: 'center',
    padding: '40px 20px',
    color: isDarkTheme ? '#CCCCCC' : '#666666',
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
    fontWeight: 600,
    color: '#ffffff',
    backgroundColor: '#007acc',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    transition: 'background-color 0.2s',
  };

  const loginButtonHoverStyle: React.CSSProperties = {
    ...loginButtonStyle,
    backgroundColor: '#005a9e',
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

  const menuStyle: React.CSSProperties = {
    position: 'absolute',
    right: 12,
    bottom: `${footerHeight + 8}px`,
    minWidth: 140,
    borderRadius: 6,
    overflow: 'hidden',
    boxShadow: '0 6px 16px rgba(0,0,0,0.12)',
    backgroundColor: isDarkTheme ? '#2b2b2b' : '#ffffff',
    border: `1px solid ${isDarkTheme ? '#3a3a3a' : '#e6e6e6'}`,
    zIndex: 20,
  };

  const menuItemStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
    fontSize: 14,
    cursor: 'pointer',
    color: isDarkTheme ? '#ffffff' : '#111111',
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
    setMenuOpen(false);
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

  if (runningProcesses.length === 0 && finishedProcesses.length === 0) {
    return (
      <div style={containerStyle}>
        {showHeader && (
          <div style={headerStyle}>
            <h3 style={headerTitleStyle}>Experiments</h3>
            {renderDropdown()}
          </div>
        )}
        <div style={titleStyle}>Develop Processes</div>
        <div style={emptyStateStyle}>
          <div style={{ fontSize: '16px', marginBottom: '8px' }}>No develop processes</div>
          <div style={{ fontSize: '12px' }}>
            Start a develop process to see it here
          </div>
        </div>

        {/* Footer */}
        <div style={footerStyle}>
          {user ? (
            <>
              <div
                ref={userRowRef}
                style={userRowStyle}
                onClick={() => setMenuOpen((s) => !s)}
                role="button"
                aria-haspopup="true"
                aria-expanded={menuOpen}
              >
                <img
                  src={user.avatarUrl || 'https://www.gravatar.com/avatar/?d=mp&s=200'}
                  alt={user.displayName || 'User avatar'}
                  style={avatarStyle}
                />
                <div style={nameBlockStyle}>
                  <div style={nameStyle}>{user.displayName || 'User'}</div>
                  <div style={emailStyle}>{user.email || ''}</div>
                </div>
              </div>

              {menuOpen && (
                <div ref={menuRef} style={menuStyle}>             
                  <div
                    style={{ ...menuItemStyle, borderTop: `1px solid ${isDarkTheme ? '#3a3a3a' : '#eee'}` }}
                    onClick={handleLogoutClick}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', marginRight: 8 }}>
                      <IconLogout />
                    </span>
                    Logout
                  </div>
                </div>
              )}
            </>
          ) : (
            <button
              style={loginButtonStyle}
              onClick={handleLoginClick}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#005a9e';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#007acc';
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="currentColor"/>
              </svg>
              Sign in with Google
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {showHeader && (
        <div style={headerStyle}>
          <h3 style={headerTitleStyle}>Experiments</h3>
          {renderDropdown()}
        </div>
      )}
      {renderExperimentSection(runningProcesses, 'Running', 'running')}
      {renderExperimentSection(similarProcesses, 'Similar', 'similar', runningProcesses.length > 0 ? 32 : 0)}
      {renderExperimentSection(finishedProcesses, 'Finished', 'finished', (runningProcesses.length > 0 || similarProcesses.length > 0) ? 32 : 0)}

      {/* Footer (always present) */}
      <div style={footerStyle}>
        {user ? (
          <>
            <div
              ref={userRowRef}
              style={userRowStyle}
              onClick={() => setMenuOpen((s) => !s)}
              role="button"
              aria-haspopup="true"
              aria-expanded={menuOpen}
            >
              <img
                src={user.avatarUrl || 'https://www.gravatar.com/avatar/?d=mp&s=200'}
                alt={user.displayName || 'User avatar'}
                style={avatarStyle}
              />
              <div style={nameBlockStyle}>
                <div style={nameStyle}>{user.displayName || 'User'}</div>
                <div style={emailStyle}>{user.email || ''}</div>
              </div>        
            </div>

            {menuOpen && (
              <div ref={menuRef} style={menuStyle}>           
                <div style={{ ...menuItemStyle, borderTop: `1px solid ${isDarkTheme ? '#3a3a3a' : '#eee'}` }} onClick={handleLogoutClick}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', marginRight: 8 }}>
                    <IconLogout />
                  </span>
                  Logout
                </div>
              </div>
            )}
          </>
        ) : (
          <button
            style={loginButtonStyle}
            onClick={handleLoginClick}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#005a9e';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#007acc';
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="currentColor"/>
            </svg>
            Sign in with Google
          </button>
        )}
      </div>
    </div>
  );
};