import React from 'react';
import { Lesson } from '../lessons/LessonsView';

interface GraphHeaderProps {
  runName: string;
  sessionId: string;
  lessons: Lesson[];
  isDarkTheme: boolean;
  onNavigateToLessons?: () => void;
}

export const GraphHeader: React.FC<GraphHeaderProps> = ({
  runName,
  sessionId,
  lessons,
  isDarkTheme,
  onNavigateToLessons,
}) => {
  // Count lessons extracted from this graph
  const lessonsExtractedFrom = lessons.filter(
    (lesson) => lesson.extractedFrom?.sessionId === sessionId
  ).length;

  // Count lessons applied to this graph
  const lessonsAppliedTo = lessons.filter(
    (lesson) => lesson.appliedTo?.some((app) => app.sessionId === sessionId)
  ).length;

  const hasLessonStats = lessonsExtractedFrom > 0 || lessonsAppliedTo > 0;

  const statStyle = {
    fontSize: '12px',
    color: isDarkTheme ? '#888888' : '#666666',
    fontWeight: 400 as const,
  };

  const statValueStyle = {
    color: isDarkTheme ? '#0e639c' : '#007acc',
    fontWeight: 500 as const,
    cursor: onNavigateToLessons ? 'pointer' : 'default',
  };

  return (
    <div
      style={{
        padding: '12px 20px',
        borderBottom: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
        backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
        color: isDarkTheme ? '#e5e5e5' : '#333333',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
      }}
    >
      {/* Run Name */}
      <div
        style={{
          fontSize: '16px',
          fontWeight: 600,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {runName || 'Untitled'}
      </div>

      {/* Lesson Stats */}
      {hasLessonStats && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            flexShrink: 0,
          }}
        >
          {lessonsExtractedFrom > 0 && (
            <span style={statStyle}>
              <span
                style={statValueStyle}
                onClick={onNavigateToLessons}
                title="View lessons extracted from this run"
              >
                {lessonsExtractedFrom} lesson{lessonsExtractedFrom !== 1 ? 's' : ''}
              </span>
              {' '}extracted
            </span>
          )}
          {lessonsAppliedTo > 0 && (
            <span style={statStyle}>
              <span
                style={statValueStyle}
                onClick={onNavigateToLessons}
                title="View lessons applied to this run"
              >
                {lessonsAppliedTo} lesson{lessonsAppliedTo !== 1 ? 's' : ''}
              </span>
              {' '}applied
            </span>
          )}
        </div>
      )}
    </div>
  );
};
