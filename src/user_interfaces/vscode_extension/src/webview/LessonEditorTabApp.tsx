import React, { useState, useEffect, useCallback } from 'react';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';
import { LessonHeader } from '../../../shared_components/components/LessonHeader';
import { LessonSummary } from '../../../shared_components/types';

declare global {
  interface Window {
    vscode?: {
      postMessage: (message: any) => void;
    };
    lessonEditorContext?: {
      lessonId: string;
      lessonName: string;
      playbookUrl: string;
      playbookApiKey: string;
    };
  }
}

// Helper to build headers with optional API key
const buildHeaders = (apiKey?: string, contentType?: string): HeadersInit => {
  const headers: HeadersInit = {};
  if (contentType) headers['Content-Type'] = contentType;
  if (apiKey) headers['X-API-Key'] = apiKey;
  return headers;
};

interface LessonData {
  id: string;
  name: string;
  summary: string;
  content: string;
}

export const LessonEditorTabApp: React.FC = () => {
  const isDarkTheme = useIsVsCodeDarkTheme();
  const [context, setContext] = useState(window.lessonEditorContext || null);
  const [lesson, setLesson] = useState<LessonData | null>(null);
  const [lessons, setLessons] = useState<LessonSummary[]>([]);
  const [editedContent, setEditedContent] = useState('');
  const [editedName, setEditedName] = useState('');
  const [editedSummary, setEditedSummary] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [validationError, setValidationError] = useState<string | null>(null);
  const isNewLesson = context?.lessonId === 'new';

  // Fetch all lessons for dropdown
  const fetchAllLessons = useCallback(async () => {
    if (!context?.playbookUrl) return;
    try {
      const response = await fetch(`${context.playbookUrl}/api/v1/lessons`, {
        headers: buildHeaders(context.playbookApiKey),
      });
      if (response.ok) {
        const data = await response.json();
        setLessons(data);
      }
    } catch (err) {
      console.debug('Failed to fetch lessons list:', err);
    }
  }, [context?.playbookUrl, context?.playbookApiKey]);

  // Fetch single lesson data
  const fetchLesson = useCallback(async (lessonId: string) => {
    if (!context?.playbookUrl) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${context.playbookUrl}/api/v1/lessons/${lessonId}`, {
        headers: buildHeaders(context.playbookApiKey),
      });
      if (response.ok) {
        const data = await response.json();
        setLesson(data);
        setEditedContent(data.content || '');
        setEditedName(data.name || '');
        setEditedSummary(data.summary || '');
        setHasUnsavedChanges(false);
      } else {
        setError('Failed to load lesson');
      }
    } catch (err) {
      setError('Server not available');
    } finally {
      setLoading(false);
    }
  }, [context?.playbookUrl, context?.playbookApiKey]);

  // Load lesson on mount or when context changes
  useEffect(() => {
    if (context?.lessonId === 'new') {
      // New lesson - start with empty fields
      setLesson({ id: 'new', name: '', summary: '', content: '' });
      setEditedName('');
      setEditedSummary('');
      setEditedContent('');
      setHasUnsavedChanges(true); // Mark as unsaved since it's a new lesson
      setLoading(false);
    } else if (context?.lessonId) {
      fetchLesson(context.lessonId);
    }
  }, [context, fetchLesson]);

  // Fetch all lessons on mount
  useEffect(() => {
    fetchAllLessons();
  }, [fetchAllLessons]);

  // Listen for messages from extension
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;
      if (message.type === 'updateLessonData') {
        setContext(message.payload);
      }
    };

    window.addEventListener('message', handleMessage);

    if (window.vscode) {
      window.vscode.postMessage({ type: 'ready' });
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  // Detect changes
  useEffect(() => {
    if (!lesson) return;
    // For new lessons, always mark as unsaved (they need to be created)
    if (lesson.id === 'new') {
      setHasUnsavedChanges(true);
      return;
    }
    const contentChanged = editedContent !== (lesson.content || '');
    const nameChanged = editedName !== (lesson.name || '');
    const summaryChanged = editedSummary !== (lesson.summary || '');
    setHasUnsavedChanges(contentChanged || nameChanged || summaryChanged);
  }, [editedContent, editedName, editedSummary, lesson]);

  // Validate fields
  const validateFields = useCallback((): string | null => {
    if (!editedName.trim()) return 'Name is required';
    if (!editedSummary.trim()) return 'Summary is required';
    if (!editedContent.trim()) return 'Content is required';
    return null;
  }, [editedName, editedSummary, editedContent]);

  // Check if save is allowed
  const canSave = useCallback(() => {
    return hasUnsavedChanges && !validateFields();
  }, [hasUnsavedChanges, validateFields]);

  // Handle save
  const handleSave = useCallback(async () => {
    // Validate fields
    const validationErr = validateFields();
    if (validationErr) {
      setValidationError(validationErr);
      setTimeout(() => setValidationError(null), 3000);
      return;
    }

    setSaveStatus('saving');
    setValidationError(null);

    try {
      let response: Response;

      if (isNewLesson) {
        // Create new lesson via POST
        response = await fetch(`${context?.playbookUrl}/api/v1/lessons`, {
          method: 'POST',
          headers: buildHeaders(context?.playbookApiKey, 'application/json'),
          body: JSON.stringify({
            name: editedName.trim(),
            summary: editedSummary.trim(),
            content: editedContent.trim(),
          }),
        });
      } else {
        // Update existing lesson via PUT
        response = await fetch(`${context?.playbookUrl}/api/v1/lessons/${context?.lessonId}`, {
          method: 'PUT',
          headers: buildHeaders(context?.playbookApiKey, 'application/json'),
          body: JSON.stringify({
            name: editedName.trim(),
            summary: editedSummary.trim(),
            content: editedContent.trim(),
          }),
        });
      }

      if (response.ok) {
        const updatedLesson = await response.json();
        setLesson(updatedLesson);
        // Update context with new lesson ID if it was a new lesson
        if (isNewLesson && updatedLesson.id) {
          setContext({ lessonId: updatedLesson.id, lessonName: updatedLesson.name, playbookUrl: context?.playbookUrl || '', playbookApiKey: context?.playbookApiKey || '' });
        }
        setHasUnsavedChanges(false);
        setSaveStatus('saved');
        // Refresh lessons list for dropdown
        fetchAllLessons();
        // Notify sidebar to refresh
        if (window.vscode) {
          window.vscode.postMessage({ type: 'lessonUpdated' });
        }
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        const errorData = await response.json().catch(() => ({}));
        setValidationError(errorData.detail || 'Failed to save lesson');
        setSaveStatus('error');
        setTimeout(() => {
          setSaveStatus('idle');
          setValidationError(null);
        }, 3000);
      }
    } catch (err) {
      setValidationError('Server not available');
      setSaveStatus('error');
      setTimeout(() => {
        setSaveStatus('idle');
        setValidationError(null);
      }, 3000);
    }
  }, [context, editedContent, editedName, editedSummary, fetchAllLessons, isNewLesson, validateFields]);

  // Handle CMD+S / Ctrl+S keyboard shortcut for save
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 's') {
        event.preventDefault();
        handleSave();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleSave]);

  // Handle navigating to a different lesson
  const handleNavigateToLesson = useCallback((lessonSummary: LessonSummary) => {
    setContext(prev => ({ lessonId: lessonSummary.id, lessonName: lessonSummary.name, playbookUrl: prev?.playbookUrl || '', playbookApiKey: prev?.playbookApiKey || '' }));
    setShowPreview(false);
  }, []);

  // Simple markdown to HTML conversion for preview
  const renderMarkdown = (text: string): string => {
    return text
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^# (.*$)/gm, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
      .replace(/\n/g, '<br/>');
  };

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
    color: isDarkTheme ? '#cccccc' : '#333333',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const inputStyle: React.CSSProperties = {
    flex: 1,
    padding: '6px 10px',
    fontSize: '14px',
    backgroundColor: isDarkTheme ? '#3c3c3c' : '#ffffff',
    color: isDarkTheme ? '#cccccc' : '#333333',
    border: `1px solid ${isDarkTheme ? '#555555' : '#cccccc'}`,
    borderRadius: '4px',
    marginRight: '12px',
  };

  const buttonStyle: React.CSSProperties = {
    padding: '6px 16px',
    fontSize: '13px',
    backgroundColor: isDarkTheme ? '#0e639c' : '#007acc',
    color: '#ffffff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    marginLeft: '8px',
  };

  const editorStyle: React.CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };

  const textareaStyle: React.CSSProperties = {
    flex: 1,
    padding: '16px',
    fontSize: '14px',
    lineHeight: '1.6',
    backgroundColor: isDarkTheme ? '#1e1e1e' : '#ffffff',
    color: isDarkTheme ? '#cccccc' : '#333333',
    border: 'none',
    resize: 'none',
    fontFamily: 'monospace',
    outline: 'none',
  };

  const previewStyle: React.CSSProperties = {
    flex: 1,
    padding: '16px',
    overflow: 'auto',
    backgroundColor: isDarkTheme ? '#252525' : '#f5f5f5',
  };

  const fieldRowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    padding: '8px 16px',
    borderBottom: `1px solid ${isDarkTheme ? '#3c3c3c' : '#e0e0e0'}`,
  };

  const labelStyle: React.CSSProperties = {
    width: '80px',
    fontSize: '12px',
    fontWeight: 600,
    color: isDarkTheme ? '#888888' : '#666666',
  };

  if (loading) {
    return (
      <div style={{ ...containerStyle, alignItems: 'center', justifyContent: 'center' }}>
        Loading lesson...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ ...containerStyle, alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: '#e05252' }}>{error}</div>
        <button
          style={{ ...buttonStyle, marginTop: '16px' }}
          onClick={() => context?.lessonId && fetchLesson(context.lessonId)}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* Header with dropdown and action icons */}
      <LessonHeader
        lessonName={editedName || lesson?.name || (isNewLesson ? 'New Lesson' : 'Lesson')}
        lessonId={context?.lessonId || ''}
        isDarkTheme={isDarkTheme}
        lessons={lessons}
        hasUnsavedChanges={canSave()}
        showPreview={showPreview}
        saveStatus={saveStatus}
        onNavigateToLesson={handleNavigateToLesson}
        onTogglePreview={() => setShowPreview(!showPreview)}
        onSave={handleSave}
      />

      {/* Validation error banner */}
      {validationError && (
        <div style={{
          padding: '8px 16px',
          backgroundColor: isDarkTheme ? '#5a1d1d' : '#fde7e7',
          color: isDarkTheme ? '#f48771' : '#c53030',
          fontSize: '12px',
          borderBottom: `1px solid ${isDarkTheme ? '#742a2a' : '#feb2b2'}`,
        }}>
          {validationError}
        </div>
      )}

      {/* Name field */}
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Name</span>
        <input
          type="text"
          value={editedName}
          onChange={(e) => setEditedName(e.target.value)}
          style={inputStyle}
          placeholder="Lesson name"
        />
      </div>

      {/* Summary field */}
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Summary</span>
        <input
          type="text"
          value={editedSummary}
          onChange={(e) => setEditedSummary(e.target.value)}
          style={inputStyle}
          placeholder="Brief summary"
        />
      </div>

      {/* Editor/Preview */}
      <div style={editorStyle}>
        {showPreview ? (
          <div
            style={previewStyle}
            dangerouslySetInnerHTML={{ __html: renderMarkdown(editedContent) }}
          />
        ) : (
          <textarea
            style={textareaStyle}
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            placeholder="Write your lesson content in markdown..."
          />
        )}
      </div>
    </div>
  );
};
