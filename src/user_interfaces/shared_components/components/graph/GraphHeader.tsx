import React from 'react';
import { Lesson } from '../lessons/LessonsView';

interface GraphHeaderProps {
  runName: string;
  isDarkTheme: boolean;
  sessionId?: string;
  lessons?: Lesson[];
  onNavigateToLessons?: () => void;
}

export const GraphHeader: React.FC<GraphHeaderProps> = ({
  runName,
  isDarkTheme,
  sessionId,
  lessons = [],
  onNavigateToLessons,
}) => {
  // Count lessons extracted from this graph
  const lessonsExtractedFrom = sessionId
    ? lessons.filter((lesson) => lesson.extractedFrom?.sessionId === sessionId).length
    : 0;

  // Count lessons applied to this graph
  const lessonsAppliedTo = sessionId
    ? lessons.filter((lesson) => lesson.appliedTo?.some((app) => app.sessionId === sessionId)).length
    : 0;

  return (
    <div
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 150,
        height: 0,
        overflow: 'visible',
      }}
    >
      {/* Content wrapper with background */}
      <div
        style={{
          position: 'absolute',
          top: '12px',
          left: '16px',
          backgroundColor: isDarkTheme ? '#252525' : '#F0F0F0',
          padding: '12px 16px',
          borderRadius: '8px',
        }}
      >
        {/* Run Name */}
        <div
          style={{
            fontSize: '18px',
            fontWeight: 600,
            color: isDarkTheme ? '#e5e5e5' : '#333333',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {runName || 'Untitled'}
        </div>

        {/* Horizontal Line */}
        {sessionId && (
          <div
            style={{
              width: '280px',
              height: '1.5px',
              backgroundColor: isDarkTheme ? '#3c3c3c' : '#d0d0d0',
              margin: '8px 0',
            }}
          />
        )}

        {/* Lesson Stats */}
        {sessionId && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              cursor: onNavigateToLessons ? 'pointer' : 'default',
              fontSize: '15px',
              color: isDarkTheme ? '#aeaeae' : '#666666',
              fontWeight: 400,
              transition: 'color 0.2s',
            }}
            onClick={onNavigateToLessons}
            onMouseEnter={(e) => {
              if (onNavigateToLessons) {
                e.currentTarget.style.color = isDarkTheme ? '#cecece' : '#333333';
              }
            }}
            onMouseLeave={(e) => {
              if (onNavigateToLessons) {
                e.currentTarget.style.color = isDarkTheme ? '#aeaeae' : '#666666';
              }
            }}
            title="View lessons"
          >
            <span>{lessonsExtractedFrom} lesson{lessonsExtractedFrom !== 1 ? 's' : ''} extracted</span>
            <span style={{ color: isDarkTheme ? '#555555' : '#c0c0c0' }}>|</span>
            <span>{lessonsAppliedTo} lesson{lessonsAppliedTo !== 1 ? 's' : ''} applied</span>
          </div>
        )}
      </div>
    </div>
  );
};
