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
}

export const ExperimentsView: React.FC<ExperimentsViewProps> = ({ similarProcesses, runningProcesses, finishedProcesses, onCardClick, isDarkTheme = false }) => {
  const [hoveredCards, setHoveredCards] = useState<Set<string>>(new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['running', 'similar', 'finished']));
  
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

  if (runningProcesses.length === 0 && finishedProcesses.length === 0) {
    return (
      <div style={containerStyle}>
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
      {renderExperimentSection(runningProcesses, 'Running', 'running')}
      {renderExperimentSection(similarProcesses, 'Similar', 'similar', 16)}
      {renderExperimentSection(finishedProcesses, 'Finished', 'finished', 16)}
    </div>
  );
}; 