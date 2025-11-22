import React, { useState } from 'react';
import { useIsVsCodeDarkTheme } from '../../utils/themeUtils';
import { ProcessCard } from './ProcessCard';
import { GraphData, ProcessInfo } from '../../types';

interface ExperimentsViewProps {
  similarProcesses: ProcessInfo[];
  runningProcesses: ProcessInfo[];
  finishedProcesses: ProcessInfo[];
  onCardClick?: (process: ProcessInfo) => void;
  isDarkTheme?: boolean;
  showHeader?: boolean;
  onModeChange?: (mode: 'Local' | 'Remote') => void;
  currentMode?: 'Local' | 'Remote';
}

export const ExperimentsView: React.FC<ExperimentsViewProps> = ({ similarProcesses, runningProcesses, finishedProcesses, onCardClick, isDarkTheme = false, showHeader = false, onModeChange, currentMode = 'Local' }) => {
  // const isDarkTheme = useIsVsCodeDarkTheme();
  const [hoveredCards, setHoveredCards] = useState<Set<string>>(new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['running', 'similar', 'finished']));
  const [dropdownOpen, setDropdownOpen] = useState(false);
  
  const containerStyle: React.CSSProperties = {
    padding: '20px 20px 40px 20px',
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
      {renderExperimentSection(similarProcesses, 'Similar', 'similar', 16)}
      {renderExperimentSection(finishedProcesses, 'Finished', 'finished', 16)}
    </div>
  );
}; 