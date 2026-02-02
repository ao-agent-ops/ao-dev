import React, { useState, useEffect, useRef, useCallback } from 'react';

export interface Lesson {
  id: string;
  name: string;
  summary: string;
  content: string;
  path?: string;
  appliedTo?: { sessionId: string; nodeId?: string; runName: string }[];
  extractedFrom?: { sessionId: string; nodeId?: string };
  validationSeverity?: 'info' | 'warning' | 'error';
}

export interface LessonFormData {
  name: string;
  summary: string;
  content: string;
  path?: string;
}

export interface ValidationResult {
  feedback: string;
  severity: 'info' | 'warning' | 'error';
  conflicting_lesson_ids: string[];
  isRejected?: boolean;
}

interface LessonsViewProps {
  lessons: Lesson[];
  isDarkTheme: boolean;
  onLessonCreate?: (data: LessonFormData, force?: boolean) => void;
  onLessonUpdate?: (id: string, data: Partial<LessonFormData>, force?: boolean) => void;
  onLessonDelete?: (id: string) => void;
  onNavigateToRun?: (sessionId: string, nodeId?: string) => void;
  onFetchLessonContent?: (id: string) => void;
  validationResult?: ValidationResult | null;
  isValidating?: boolean;
  onClearValidation?: () => void;
  apiKeyError?: boolean;
}

// Loading spinner component
const Spinner: React.FC<{ isDark: boolean }> = ({ isDark }) => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 16 16"
    style={{
      animation: 'spin 1s linear infinite',
      marginLeft: '8px',
    }}
  >
    <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
    <circle
      cx="8"
      cy="8"
      r="6"
      fill="none"
      stroke={isDark ? '#888888' : '#666666'}
      strokeWidth="2"
      strokeDasharray="24"
      strokeDashoffset="8"
      strokeLinecap="round"
    />
  </svg>
);

// Get border color based on severity
const getSeverityColor = (severity: string | undefined, isDark: boolean): string => {
  switch (severity) {
    case 'info': return isDark ? '#3a7644' : '#43884e';
    case 'warning': return isDark ? '#c9a227' : '#f0ad4e';
    case 'error': return isDark ? '#b33b3b' : '#d9534f';
    default: return isDark ? '#3c3c3c' : '#d0d0d0';
  }
};

export const LessonsView: React.FC<LessonsViewProps> = ({
  lessons,
  isDarkTheme,
  onLessonCreate,
  onLessonUpdate,
  onLessonDelete,
  onNavigateToRun,
  onFetchLessonContent,
  validationResult,
  isValidating,
  onClearValidation,
  apiKeyError,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<LessonFormData>({ name: '', summary: '', content: '', path: '' });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<LessonFormData>({ name: '', summary: '', content: '', path: '' });
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [loadingContentIds, setLoadingContentIds] = useState<Set<string>>(new Set());
  const lessonRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // Clear loading state when lesson content is received
  useEffect(() => {
    setLoadingContentIds((prev) => {
      const next = new Set(prev);
      for (const lesson of lessons) {
        if (lesson.content && next.has(lesson.id)) {
          next.delete(lesson.id);
        }
      }
      return next.size !== prev.size ? next : prev;
    });
  }, [lessons]);

  // Check if a lesson matches the search query
  const lessonMatches = useCallback((lesson: Lesson, query: string): boolean => {
    if (!query) return false;
    const q = query.toLowerCase();
    if (lesson.name.toLowerCase().includes(q)) return true;
    if (lesson.summary.toLowerCase().includes(q)) return true;
    if (expandedIds.has(lesson.id) && lesson.content && lesson.content.toLowerCase().includes(q)) return true;
    return false;
  }, [expandedIds]);

  const matchingLessonIds = searchQuery
    ? lessons.filter((lesson) => lessonMatches(lesson, searchQuery)).map((l) => l.id)
    : [];

  useEffect(() => {
    setCurrentMatchIndex(0);
  }, [searchQuery, matchingLessonIds.length]);

  useEffect(() => {
    if (matchingLessonIds.length > 0 && currentMatchIndex < matchingLessonIds.length) {
      const matchId = matchingLessonIds[currentMatchIndex];
      const element = lessonRefs.current.get(matchId);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [currentMatchIndex, matchingLessonIds]);

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && matchingLessonIds.length > 0) {
      e.preventDefault();
      setCurrentMatchIndex((prev) => (prev + 1) % matchingLessonIds.length);
    }
  };

  const filteredLessons = lessons;

  const highlightText = (text: string, isCurrentMatch: boolean): React.ReactNode => {
    if (!searchQuery || !text) return text;
    const query = searchQuery.toLowerCase();
    const lowerText = text.toLowerCase();
    const index = lowerText.indexOf(query);
    if (index === -1) return text;
    const before = text.slice(0, index);
    const match = text.slice(index, index + searchQuery.length);
    const after = text.slice(index + searchQuery.length);
    return (
      <>
        {before}
        <mark
          style={{
            backgroundColor: isCurrentMatch
              ? (isDarkTheme ? '#4a9eff' : '#ffeb3b')
              : (isDarkTheme ? '#5a5a00' : '#fff59d'),
            color: isCurrentMatch ? '#000' : (isDarkTheme ? '#fff' : '#000'),
            padding: '1px 2px',
            borderRadius: '2px',
          }}
        >
          {match}
        </mark>
        {highlightText(after, isCurrentMatch)}
      </>
    );
  };

  const handleStartEdit = (lesson: Lesson) => {
    setEditingId(lesson.id);
    setEditForm({
      name: lesson.name,
      summary: lesson.summary,
      content: lesson.content,
      path: lesson.path || '',
    });
    onClearValidation?.();
  };

  const handleSaveEdit = (id: string, force: boolean = false) => {
    if (onLessonUpdate) {
      onLessonUpdate(id, editForm, force);
      // If force save, close immediately. Otherwise wait for validation response.
      if (force) {
        setEditingId(null);
        setEditForm({ name: '', summary: '', content: '', path: '' });
      }
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditForm({ name: '', summary: '', content: '', path: '' });
    onClearValidation?.();
  };

  const handleCreate = (force: boolean = false) => {
    if (onLessonCreate && createForm.name && createForm.content) {
      onLessonCreate(createForm, force);
      // If force save, close immediately. Otherwise wait for validation response.
      if (force) {
        setShowCreateModal(false);
        setCreateForm({ name: '', summary: '', content: '', path: '' });
      }
    }
  };

  // Close modal when validation succeeds (non-rejected response received)
  useEffect(() => {
    if (validationResult && !validationResult.isRejected && !isValidating) {
      // Validation passed - close modal after a short delay to show feedback
      const timer = setTimeout(() => {
        if (showCreateModal) {
          setShowCreateModal(false);
          setCreateForm({ name: '', summary: '', content: '', path: '' });
        }
        if (editingId) {
          setEditingId(null);
          setEditForm({ name: '', summary: '', content: '', path: '' });
        }
        onClearValidation?.();
      }, 1500); // 1.5s delay to let user see feedback
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validationResult, isValidating, showCreateModal, editingId]);

  const handleCancelCreate = () => {
    setShowCreateModal(false);
    setCreateForm({ name: '', summary: '', content: '', path: '' });
    onClearValidation?.();
  };

  const toggleExpanded = (id: string, lesson: Lesson) => {
    const isExpanding = !expandedIds.has(id);
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
    if (isExpanding && !lesson.content && onFetchLessonContent) {
      setLoadingContentIds((prev) => new Set(prev).add(id));
      onFetchLessonContent(id);
    }
  };

  const buttonStyle = (isDark: boolean, variant: 'primary' | 'secondary' | 'danger' | 'warning' = 'secondary') => ({
    padding: '4px 10px',
    fontSize: '11px',
    fontWeight: 500 as const,
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    backgroundColor:
      variant === 'primary'
        ? isDark ? '#0e639c' : '#007acc'
        : variant === 'danger'
          ? isDark ? '#5a1d1d' : '#ffebee'
          : variant === 'warning'
            ? isDark ? '#8a6914' : '#f0ad4e'
            : isDark ? '#3c3c3c' : '#e8e8e8',
    color:
      variant === 'primary'
        ? '#ffffff'
        : variant === 'danger'
          ? isDark ? '#f48771' : '#d32f2f'
          : variant === 'warning'
            ? '#ffffff'
            : isDark ? '#cccccc' : '#333333',
    transition: 'background-color 0.15s ease',
  });

  const inputStyle = (isDark: boolean) => ({
    width: '100%',
    padding: '8px 10px',
    fontSize: '13px',
    border: `1px solid ${isDark ? '#3c3c3c' : '#d0d0d0'}`,
    borderRadius: '4px',
    backgroundColor: isDark ? '#2d2d2d' : '#ffffff',
    color: isDark ? '#e5e5e5' : '#333333',
    outline: 'none',
    boxSizing: 'border-box' as const,
    fontFamily: 'inherit',
  });

  const labelStyle = (isDark: boolean) => ({
    display: 'block',
    fontSize: '12px',
    fontWeight: 500 as const,
    marginBottom: '4px',
    color: isDark ? '#cccccc' : '#555555',
  });

  // Handle Escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showCreateModal) {
          handleCancelCreate();
        } else if (editingId) {
          handleCancelEdit();
        }
      }
    };
    if (showCreateModal || editingId) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [showCreateModal, editingId]);

  // Modal component for create/edit with validation feedback panel
  const renderModal = (
    title: string,
    form: LessonFormData,
    setForm: React.Dispatch<React.SetStateAction<LessonFormData>>,
    onSave: (force?: boolean) => void,
    onCancel: () => void
  ) => (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        style={{
          backgroundColor: isDarkTheme ? '#252525' : '#ffffff',
          borderRadius: '8px',
          padding: '24px',
          width: '800px',
          maxWidth: '95vw',
          maxHeight: '85vh',
          overflow: 'auto',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
          position: 'relative',
        }}
      >
        {/* Close button (X) in top right */}
        <button
          onClick={onCancel}
          style={{
            position: 'absolute',
            top: '12px',
            right: '12px',
            background: 'transparent',
            border: 'none',
            fontSize: '20px',
            lineHeight: 1,
            color: isDarkTheme ? '#888888' : '#666666',
            cursor: 'pointer',
            padding: '4px 8px',
            borderRadius: '4px',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = isDarkTheme ? '#3c3c3c' : '#e8e8e8';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
          title="Close (Esc)"
        >
          ×
        </button>

        {/* Header with title and spinner */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', color: isDarkTheme ? '#e5e5e5' : '#333333' }}>
            {title}
          </h3>
          {isValidating && <Spinner isDark={isDarkTheme} />}
        </div>

        {/* Two-column layout */}
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
          {/* Left column: Form fields */}
          <div style={{ flex: '1 1 300px', minWidth: '280px' }}>
            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle(isDarkTheme)}>Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                style={inputStyle(isDarkTheme)}
                placeholder="Lesson title"
                maxLength={200}
                disabled={isValidating}
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle(isDarkTheme)}>Summary *</label>
              <textarea
                value={form.summary}
                onChange={(e) => setForm({ ...form, summary: e.target.value })}
                style={{ ...inputStyle(isDarkTheme), minHeight: '60px', resize: 'vertical' }}
                placeholder="Brief description"
                maxLength={1000}
                disabled={isValidating}
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle(isDarkTheme)}>Content *</label>
              <textarea
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                style={{ ...inputStyle(isDarkTheme), minHeight: '120px', resize: 'vertical' }}
                placeholder="Full lesson content (markdown supported)"
                disabled={isValidating}
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle(isDarkTheme)}>Path (optional)</label>
              <input
                type="text"
                value={form.path || ''}
                onChange={(e) => setForm({ ...form, path: e.target.value })}
                style={inputStyle(isDarkTheme)}
                placeholder="e.g., beaver/retriever/"
                disabled={isValidating}
              />
            </div>
          </div>

          {/* Right column: Validation feedback */}
          <div style={{ flex: '1 1 250px', minWidth: '220px' }}>
            <label style={labelStyle(isDarkTheme)}>AI Validation Feedback</label>
            <div
              style={{
                padding: '12px',
                minHeight: '200px',
                maxHeight: '350px',
                overflow: 'auto',
                backgroundColor: isDarkTheme ? '#1e1e1e' : '#f8f8f8',
                border: `2px solid ${getSeverityColor(validationResult?.severity, isDarkTheme)}`,
                borderRadius: '4px',
                fontSize: '12px',
                lineHeight: '1.5',
                color: isDarkTheme ? '#d4d4d4' : '#444444',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {isValidating ? (
                <span style={{ color: isDarkTheme ? '#888888' : '#666666', fontStyle: 'italic' }}>
                  Validating lesson with AI...
                </span>
              ) : validationResult?.feedback ? (
                validationResult.feedback
              ) : (
                <span style={{ color: isDarkTheme ? '#888888' : '#666666', fontStyle: 'italic' }}>
                  Click Save to validate the lesson. Feedback from the AI validator will appear here.
                </span>
              )}
            </div>

            {/* Severity indicator */}
            {validationResult && !isValidating && (
              <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: getSeverityColor(validationResult.severity, isDarkTheme),
                  }}
                />
                <span style={{ fontSize: '11px', color: isDarkTheme ? '#cccccc' : '#555555', textTransform: 'capitalize' }}>
                  {validationResult.isRejected ? 'Rejected' : validationResult.severity}
                </span>
                {validationResult.conflicting_lesson_ids.length > 0 && (
                  <span style={{ fontSize: '11px', color: isDarkTheme ? '#888888' : '#666666' }}>
                    ({validationResult.conflicting_lesson_ids.length} conflicts)
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Button row */}
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '20px' }}>
          <button
            onClick={onCancel}
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

          {/* Force Save button - only show when validation rejected */}
          {validationResult?.isRejected && (
            <button
              onClick={() => onSave(true)}
              style={buttonStyle(isDarkTheme, 'warning')}
              disabled={isValidating || !form.name || !form.summary || !form.content}
              onMouseEnter={(e) => {
                if (!isValidating && form.name && form.summary && form.content) {
                  e.currentTarget.style.backgroundColor = isDarkTheme ? '#a07a18' : '#ec971f';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = isDarkTheme ? '#8a6914' : '#f0ad4e';
              }}
            >
              Force Save
            </button>
          )}

          <button
            onClick={() => onSave(false)}
            style={{
              ...buttonStyle(isDarkTheme, 'primary'),
              opacity: isValidating || !form.name || !form.summary || !form.content ? 0.6 : 1,
            }}
            disabled={isValidating || !form.name || !form.summary || !form.content}
            onMouseEnter={(e) => {
              if (!isValidating && form.name && form.summary && form.content) {
                e.currentTarget.style.backgroundColor = isDarkTheme ? '#1177bb' : '#0062a3';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isDarkTheme ? '#0e639c' : '#007acc';
            }}
          >
            {isValidating ? 'Validating...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );

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
          {onLessonCreate && (
            <button
              onClick={() => {
                setShowCreateModal(true);
                onClearValidation?.();
              }}
              style={{
                ...buttonStyle(isDarkTheme, 'primary'),
                padding: '6px 12px',
                fontSize: '12px',
                backgroundColor: '#43884e',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#3a7644';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#43884e';
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
            placeholder="Search lessons... (Enter for next)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            style={{
              width: '100%',
              padding: '8px 70px 8px 32px',
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
          {searchQuery && (
            <span
              style={{
                position: 'absolute',
                right: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: '11px',
                color: matchingLessonIds.length > 0
                  ? (isDarkTheme ? '#888888' : '#666666')
                  : (isDarkTheme ? '#f48771' : '#d32f2f'),
                fontWeight: 500,
              }}
            >
              {matchingLessonIds.length > 0
                ? `${currentMatchIndex + 1}/${matchingLessonIds.length}`
                : 'No matches'}
            </span>
          )}
        </div>
      </div>

      {/* Lessons List */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px 16px 24px' }}>
        {apiKeyError ? (
          <div
            style={{
              textAlign: 'center',
              padding: '60px 20px',
              color: isDarkTheme ? '#cccccc' : '#444444',
            }}
          >
            <div style={{ fontSize: '14px', marginBottom: '12px' }}>
              Unable to connect to the Lessons server.
            </div>
            <div style={{ fontSize: '13px', color: isDarkTheme ? '#888888' : '#666666' }}>
              To obtain an API key, send an e-mail to{' '}
              <a
                href="mailto:hello@agops-project.com"
                style={{ color: isDarkTheme ? '#4a9eff' : '#007acc' }}
              >
                hello@agops-project.com
              </a>
            </div>
          </div>
        ) : filteredLessons.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: '40px 20px',
              color: isDarkTheme ? '#888888' : '#666666',
            }}
          >
            No lessons yet
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredLessons.map((lesson) => {
              const isCurrentMatch = !!(searchQuery && matchingLessonIds[currentMatchIndex] === lesson.id);
              return (
              <div
                key={lesson.id}
                ref={(el) => {
                  if (el) lessonRefs.current.set(lesson.id, el);
                  else lessonRefs.current.delete(lesson.id);
                }}
                style={{
                  backgroundColor: isDarkTheme ? '#2d2d2d' : '#fafafa',
                  border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
                  borderLeft: lesson.validationSeverity
                    ? `3px solid ${getSeverityColor(lesson.validationSeverity, isDarkTheme)}`
                    : `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
                  borderRadius: '6px',
                  padding: '14px 16px',
                }}
              >
                {/* Header: Name and Path */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <h4
                    style={{
                      margin: 0,
                      fontSize: '14px',
                      fontWeight: 600,
                      color: isDarkTheme ? '#e5e5e5' : '#333333',
                    }}
                  >
                    {highlightText(lesson.name, isCurrentMatch)}
                  </h4>
                  {lesson.path && (
                    <span
                      style={{
                        fontSize: '10px',
                        padding: '2px 6px',
                        borderRadius: '3px',
                        backgroundColor: isDarkTheme ? '#3c3c3c' : '#e0e0e0',
                        color: isDarkTheme ? '#999999' : '#666666',
                        marginLeft: '8px',
                        flexShrink: 0,
                      }}
                    >
                      {lesson.path}
                    </span>
                  )}
                </div>

                {/* Summary */}
                <p
                  style={{
                    margin: '0 0 10px 0',
                    fontSize: '12px',
                    lineHeight: '1.5',
                    color: isDarkTheme ? '#999999' : '#666666',
                  }}
                >
                  {highlightText(lesson.summary, isCurrentMatch)}
                </p>

                {/* Content (expandable) */}
                <div style={{ marginBottom: '12px' }}>
                  <button
                    onClick={() => toggleExpanded(lesson.id, lesson)}
                    style={{
                      ...buttonStyle(isDarkTheme),
                      fontSize: '10px',
                      padding: '2px 8px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span style={{ transform: expandedIds.has(lesson.id) ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
                      ▶
                    </span>
                    {expandedIds.has(lesson.id) ? 'Hide content' : 'Show content'}
                  </button>
                  {expandedIds.has(lesson.id) && (
                    <pre
                      style={{
                        margin: '8px 0 0 0',
                        padding: '10px',
                        fontSize: '12px',
                        lineHeight: '1.5',
                        backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
                        border: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
                        borderRadius: '4px',
                        color: isDarkTheme ? '#d4d4d4' : '#444444',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        fontFamily: 'inherit',
                        overflow: 'auto',
                        maxHeight: '300px',
                      }}
                    >
                      {loadingContentIds.has(lesson.id)
                        ? 'Loading...'
                        : (lesson.content ? highlightText(lesson.content, isCurrentMatch) : 'No content available')}
                    </pre>
                  )}
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  {onLessonUpdate && (
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
                  )}

                  {onLessonDelete && (
                    <button
                      onClick={() => onLessonDelete(lesson.id)}
                      style={buttonStyle(isDarkTheme, 'danger')}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = isDarkTheme ? '#6a2a2a' : '#ffcdd2';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = isDarkTheme ? '#5a1d1d' : '#ffebee';
                      }}
                    >
                      Delete
                    </button>
                  )}

                  {lesson.appliedTo && lesson.appliedTo.length > 0 && (
                    <>
                      <span style={{ fontSize: '11px', color: isDarkTheme ? '#888888' : '#888888', marginLeft: '8px' }}>
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
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal &&
        renderModal(
          'Create New Lesson',
          createForm,
          setCreateForm,
          handleCreate,
          handleCancelCreate
        )}

      {/* Edit Modal */}
      {editingId &&
        renderModal(
          'Edit Lesson',
          editForm,
          setEditForm,
          (force) => handleSaveEdit(editingId, force),
          handleCancelEdit
        )}
    </div>
  );
};
