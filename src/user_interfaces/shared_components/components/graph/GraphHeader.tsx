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
        padding: '12px 60px 12px 16px',  // Extra right padding for fixed sidebar
        marginLeft: '12px',
        marginTop: '8px',
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
              cursor: onNavigateToLessons ? 'pointer' : 'default',
              fontSize: '15px',
              color: isDarkTheme ? '#4da6ff' : '#007acc',
              fontWeight: 400,
              transition: 'color 0.2s',
            }}
            onClick={onNavigateToLessons}
            onMouseEnter={(e) => {
              if (onNavigateToLessons) {
                e.currentTarget.style.color = isDarkTheme ? '#6bb8ff' : '#005a9e';
              }
            }}
            onMouseLeave={(e) => {
              if (onNavigateToLessons) {
                e.currentTarget.style.color = isDarkTheme ? '#4da6ff' : '#007acc';
              }
            }}
            title="View lessons"
          >
            {lessonsExtractedFrom} lesson{lessonsExtractedFrom !== 1 ? 's' : ''} extracted, {lessonsAppliedTo} lesson{lessonsAppliedTo !== 1 ? 's' : ''} applied
          </div>
        )}
    </div>
  );
};
