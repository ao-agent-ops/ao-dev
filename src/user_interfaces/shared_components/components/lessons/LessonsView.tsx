import React, { useState } from 'react';

export interface Lesson {
  id: string;
  content: string;
  extractedFrom?: { sessionId: string; nodeId?: string; runName: string };
  appliedTo?: { sessionId: string; nodeId?: string; runName: string }[];
}

interface LessonsViewProps {
  lessons: Lesson[];
  isDarkTheme: boolean;
  onLessonUpdate?: (id: string, content: string) => void;
  onLessonDelete?: (id: string) => void;
  onNavigateToRun?: (sessionId: string, nodeId?: string) => void;
  onAddLesson?: () => void;
}

export const LessonsView: React.FC<LessonsViewProps> = ({
  lessons,
  isDarkTheme,
  onLessonUpdate,
  onLessonDelete,
  onNavigateToRun,
  onAddLesson,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');

  const filteredLessons = lessons.filter((lesson) =>
    lesson.content.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleStartEdit = (lesson: Lesson) => {
    setEditingId(lesson.id);
    setEditContent(lesson.content);
  };

  const handleSaveEdit = (id: string) => {
    if (onLessonUpdate) {
      onLessonUpdate(id, editContent);
    }
    setEditingId(null);
    setEditContent('');
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditContent('');
  };

  const buttonStyle = (isDark: boolean, variant: 'primary' | 'secondary' = 'secondary') => ({
    padding: '4px 10px',
    fontSize: '11px',
    fontWeight: 500 as const,
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    backgroundColor: variant === 'primary'
      ? (isDark ? '#0e639c' : '#007acc')
      : (isDark ? '#3c3c3c' : '#e8e8e8'),
    color: variant === 'primary'
      ? '#ffffff'
      : (isDark ? '#cccccc' : '#333333'),
    transition: 'background-color 0.15s ease',
  });

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        backgroundColor: isDarkTheme ? '#252525' : '#F0F0F0',
        color: isDarkTheme ? '#e5e5e5' : '#333333',
        fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header with Search */}
      <div
        style={{
          padding: '18px 24px 16px 24px',
          borderBottom: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
          backgroundColor: isDarkTheme ? '#252525' : '#F0F0F0',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h2
            style={{
              margin: 0,
              fontSize: '18px',
              fontWeight: 600,
              color: isDarkTheme ? '#e5e5e5' : '#333333',
            }}
          >
            Lessons
          </h2>
          {onAddLesson && (
            <button
              onClick={onAddLesson}
              style={{
                ...buttonStyle(isDarkTheme, 'primary'),
                padding: '6px 12px',
                fontSize: '12px',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = isDarkTheme ? '#1176ba' : '#0062a3';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = isDarkTheme ? '#0f6caa' : '#007acc';
              }}
            >
              + Add Lesson
            </button>
          )}
        </div>

        {/* Search Bar */}
        <div style={{ position: 'relative' }}>
          <svg
            style={{
              position: 'absolute',
              left: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '14px',
              height: '14px',
              fill: isDarkTheme ? '#888888' : '#666666',
            }}
            viewBox="0 0 16 16"
          >
            <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search lessons..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px 8px 32px',
              fontSize: '13px',
              border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#d0d0d0'}`,
              borderRadius: '4px',
              backgroundColor: isDarkTheme ? '#2d2d2d' : '#ffffff',
              color: isDarkTheme ? '#e5e5e5' : '#333333',
              outline: 'none',
              boxSizing: 'border-box',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = isDarkTheme ? '#0e639c' : '#007acc';
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = isDarkTheme ? '#3c3c3c' : '#d0d0d0';
            }}
          />
        </div>
      </div>

      {/* Lessons List */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px 16px 24px' }}>
        {filteredLessons.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: '40px 20px',
              color: isDarkTheme ? '#888888' : '#666666',
            }}
          >
            {searchQuery ? 'No lessons match your search' : 'No lessons yet'}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredLessons.map((lesson) => (
              <div
                key={lesson.id}
                style={{
                  backgroundColor: isDarkTheme ? '#252525' : '#fafafa',
                  border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
                  borderRadius: '6px',
                  padding: '14px 16px',
                }}
              >
                {/* Content - Editable */}
                {editingId === lesson.id ? (
                  <div style={{ marginBottom: '12px' }}>
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      style={{
                        width: '100%',
                        minHeight: '80px',
                        padding: '10px',
                        fontSize: '13px',
                        lineHeight: '1.5',
                        border: `1px solid ${isDarkTheme ? '#0e639c' : '#007acc'}`,
                        borderRadius: '4px',
                        backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
                        color: isDarkTheme ? '#e5e5e5' : '#333333',
                        resize: 'vertical',
                        outline: 'none',
                        boxSizing: 'border-box',
                        fontFamily: 'inherit',
                      }}
                      autoFocus
                    />
                    <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                      <button
                        onClick={() => handleSaveEdit(lesson.id)}
                        style={buttonStyle(isDarkTheme, 'primary')}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#1177bb' : '#0062a3';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#0e639c' : '#007acc';
                        }}
                      >
                        Save
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        style={buttonStyle(isDarkTheme)}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#4a4a4a' : '#d0d0d0';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#3c3c3c' : '#e8e8e8';
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <p
                    style={{
                      margin: '0 0 12px 0',
                      fontSize: '13px',
                      lineHeight: '1.6',
                      color: isDarkTheme ? '#d4d4d4' : '#444444',
                      cursor: 'text',
                    }}
                    onClick={() => handleStartEdit(lesson)}
                    title="Click to edit"
                  >
                    {lesson.content}
                  </p>
                )}

                {/* Action Buttons */}
                {editingId !== lesson.id && (
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    {/* Edit Button */}
                    <button
                      onClick={() => handleStartEdit(lesson)}
                      style={buttonStyle(isDarkTheme)}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = isDarkTheme ? '#4a4a4a' : '#d0d0d0';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = isDarkTheme ? '#3c3c3c' : '#e8e8e8';
                      }}
                    >
                      Edit
                    </button>

                    {/* Delete Button */}
                    {onLessonDelete && (
                      <button
                        onClick={() => onLessonDelete(lesson.id)}
                        style={{
                          ...buttonStyle(isDarkTheme),
                          color: isDarkTheme ? '#f48771' : '#d32f2f',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#4a4a4a' : '#d0d0d0';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#3c3c3c' : '#e8e8e8';
                        }}
                      >
                        Delete
                      </button>
                    )}

                    {/* Extracted From Button */}
                    {lesson.extractedFrom && (
                      <button
                        onClick={() => onNavigateToRun?.(lesson.extractedFrom!.sessionId, lesson.extractedFrom!.nodeId)}
                        style={{
                          ...buttonStyle(isDarkTheme),
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#4a4a4a' : '#d0d0d0';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = isDarkTheme ? '#3c3c3c' : '#e8e8e8';
                        }}
                        title={`Go to: ${lesson.extractedFrom.runName}`}
                      >
                        <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                          <path d="M4.5 3A1.5 1.5 0 0 0 3 4.5v7A1.5 1.5 0 0 0 4.5 13h7a1.5 1.5 0 0 0 1.5-1.5v-3a.5.5 0 0 1 1 0v3A2.5 2.5 0 0 1 11.5 14h-7A2.5 2.5 0 0 1 2 11.5v-7A2.5 2.5 0 0 1 4.5 2h3a.5.5 0 0 1 0 1h-3z"/>
                          <path d="M10 2a.5.5 0 0 1 .5-.5h4a.5.5 0 0 1 .5.5v4a.5.5 0 0 1-1 0V2.707l-5.146 5.147a.5.5 0 0 1-.708-.708L13.293 2H10.5A.5.5 0 0 1 10 1.5z"/>
                        </svg>
                        Extracted from: {lesson.extractedFrom.runName}
                      </button>
                    )}

                    {/* Applied To Buttons */}
                    {lesson.appliedTo && lesson.appliedTo.length > 0 && (
                      <>
                        <span style={{ fontSize: '11px', color: isDarkTheme ? '#888888' : '#888888' }}>
                          Applied to:
                        </span>
                        {lesson.appliedTo.map((target, idx) => (
                          <button
                            key={idx}
                            onClick={() => onNavigateToRun?.(target.sessionId, target.nodeId)}
                            style={{
                              ...buttonStyle(isDarkTheme),
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = isDarkTheme ? '#4a4a4a' : '#d0d0d0';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = isDarkTheme ? '#3c3c3c' : '#e8e8e8';
                            }}
                            title={`Go to: ${target.runName}`}
                          >
                            <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                              <path d="M4.5 3A1.5 1.5 0 0 0 3 4.5v7A1.5 1.5 0 0 0 4.5 13h7a1.5 1.5 0 0 0 1.5-1.5v-3a.5.5 0 0 1 1 0v3A2.5 2.5 0 0 1 11.5 14h-7A2.5 2.5 0 0 1 2 11.5v-7A2.5 2.5 0 0 1 4.5 2h3a.5.5 0 0 1 0 1h-3z"/>
                              <path d="M10 2a.5.5 0 0 1 .5-.5h4a.5.5 0 0 1 .5.5v4a.5.5 0 0 1-1 0V2.707l-5.146 5.147a.5.5 0 0 1-.708-.708L13.293 2H10.5A.5.5 0 0 1 10 1.5z"/>
                            </svg>
                            {target.runName}
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
