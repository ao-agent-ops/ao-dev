import React, { useState } from 'react';
import { useIsVsCodeDarkTheme } from '../utils/themeUtils';
import { ProcessCard } from './ProcessCard';

export interface ProcessInfo {
  pid: number;
  script_name: string;
  session_id: string;
  status: string;
  role?: string;
  timestamp?: string;
}

interface ExperimentsViewProps {
  runningProcesses: ProcessInfo[];
  finishedProcesses: ProcessInfo[];
  onCardClick?: (process: ProcessInfo) => void;
}

export const ExperimentsView: React.FC<ExperimentsViewProps> = ({ runningProcesses, finishedProcesses, onCardClick }) => {
  const isDarkTheme = useIsVsCodeDarkTheme();
  const [hoveredCards, setHoveredCards] = useState<Set<string>>(new Set());
  
  const containerStyle: React.CSSProperties = {
    padding: '20px 20px 40px 20px',
    height: '100%',
    maxHeight: '100%',
    overflowY: 'auto',
    boxSizing: 'border-box',
    backgroundColor: isDarkTheme ? '#252525' : '#F0F0F0',
    color: isDarkTheme ? '#FFFFFF' : '#000000',
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '18px',
    fontWeight: 'bold',
    marginBottom: '20px',
    color: isDarkTheme ? '#FFFFFF' : '#000000',
  };

  const emptyStateStyle: React.CSSProperties = {
    textAlign: 'center',
    padding: '40px 20px',
    color: isDarkTheme ? '#CCCCCC' : '#666666',
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
      {runningProcesses.length > 0 && (
        <>
          <div style={titleStyle}>Running</div>
          {runningProcesses.map((process) => {
            const cardId = `running-${process.pid}`;
            const isHovered = hoveredCards.has(cardId);
            return (
              <ProcessCard
                key={process.pid}
                process={process}
                isHovered={isHovered}
                isDarkTheme={isDarkTheme}
                onClick={() => onCardClick && onCardClick(process)}
                onMouseEnter={() => setHoveredCards(prev => new Set(prev).add(cardId))}
                onMouseLeave={() => setHoveredCards(prev => {
                  const newSet = new Set(prev);
                  newSet.delete(cardId);
                  return newSet;
                })}
              />
            );
          })}
        </>
      )}
      {finishedProcesses.length > 0 && (
        <>
          <div style={{ ...titleStyle, marginTop: runningProcesses.length > 0 ? 32 : 0 }}>Finished</div>
          {finishedProcesses.map((process) => {
            const cardId = `finished-${process.pid}`;
            const isHovered = hoveredCards.has(cardId);
            return (
              <ProcessCard
                key={process.pid}
                process={process}
                isHovered={isHovered}
                isDarkTheme={isDarkTheme}
                onClick={() => onCardClick && onCardClick(process)}
                onMouseEnter={() => setHoveredCards(prev => new Set(prev).add(cardId))}
                onMouseLeave={() => setHoveredCards(prev => {
                  const newSet = new Set(prev);
                  newSet.delete(cardId);
                  return newSet;
                })}
              />
            );
          })}
        </>
      )}
    </div>
  );
}; 