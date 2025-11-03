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
  // const isDarkTheme = useIsVsCodeDarkTheme();
  const [hoveredCards, setHoveredCards] = useState<Set<string>>(new Set());
  
  // Debug logging
  console.log('ExperimentsView render - similarProcesses:', similarProcesses);
  console.log('ExperimentsView render - runningProcesses:', runningProcesses);
  console.log('ExperimentsView render - finishedProcesses:', finishedProcesses);
  
  const containerStyle: React.CSSProperties = {
    padding: '20px 20px 40px 20px',
    height: '100%',
    maxHeight: '100%',
    overflowY: 'auto',
    boxSizing: 'border-box',
    backgroundColor: isDarkTheme ? '#252525' : '#F0F2F0',
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

  const renderExperimentSection = (
    processes: ProcessInfo[],
    sectionTitle: string,
    sectionPrefix: string,
    marginTop?: number
  ) => {
    if (processes.length === 0) return null;

    return (
      <>
        <div style={{ ...titleStyle, ...(marginTop && { marginTop }) }}>
          {sectionTitle}
        </div>
        {processes.map((process) => {
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
        })}
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
      {renderExperimentSection(similarProcesses, 'Similar', 'similar')}
      {renderExperimentSection(runningProcesses, 'Running', 'running')}
      {renderExperimentSection(finishedProcesses, 'Finished', 'finished', runningProcesses.length > 0 ? 32 : 0)}
    </div>
  );
}; 