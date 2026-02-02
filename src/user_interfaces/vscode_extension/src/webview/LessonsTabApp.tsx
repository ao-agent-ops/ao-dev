import React, { useState, useEffect } from 'react';
import { LessonsView, Lesson, LessonFormData, ValidationResult } from '../../../shared_components/components/lessons/LessonsView';
import { useIsVsCodeDarkTheme } from '../../../shared_components/utils/themeUtils';

declare global {
  interface Window {
    vscode?: {
      postMessage: (message: any) => void;
    };
    isLessonsView?: boolean;
  }
}

export const LessonsTabApp: React.FC = () => {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [apiKeyError, setApiKeyError] = useState(false);
  const isDarkTheme = useIsVsCodeDarkTheme();

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      switch (message.type) {
        case 'lessons_list':
          console.log('[LessonsTabApp] Received lessons_list:', message.lessons);
          setLessons(message.lessons || []);
          setError(null); // Clear any previous error on successful list
          setApiKeyError(false); // Clear API key error on success
          break;
        case 'lesson_content':
          // Update the specific lesson with its full content
          console.log('[LessonsTabApp] Received lesson_content:', message.lesson);
          if (message.lesson) {
            setLessons((prev) =>
              prev.map((l) =>
                l.id === message.lesson.id ? { ...l, content: message.lesson.content } : l
              )
            );
          }
          break;
        case 'lesson_error':
          console.error('[LessonsTabApp] Received lesson_error:', message.error);
          setIsValidating(false);
          const errorMsg = message.error || 'An unknown error occurred';
          // Check if it's an API key error
          if (errorMsg.toLowerCase().includes('api key') || errorMsg.toLowerCase().includes('invalid') || errorMsg.toLowerCase().includes('unavailable')) {
            setApiKeyError(true);
          } else {
            setError(errorMsg);
            // Auto-clear error after 5 seconds
            setTimeout(() => setError(null), 5000);
          }
          break;
        case 'lesson_created':
        case 'lesson_updated':
          console.log(`[LessonsTabApp] Received ${message.type}:`, message);
          setIsValidating(false);
          if (message.validation) {
            // Show validation feedback (info or warning)
            setValidationResult({
              feedback: message.validation.feedback || '',
              severity: message.validation.severity || 'info',
              conflicting_lesson_ids: message.validation.conflicting_lesson_ids || [],
              isRejected: false,
            });
          } else {
            // No validation feedback, clear any previous result
            setValidationResult(null);
          }
          break;
        case 'lesson_rejected':
          console.log('[LessonsTabApp] Received lesson_rejected:', message);
          setIsValidating(false);
          setValidationResult({
            feedback: message.reason || 'Validation failed',
            severity: message.severity || 'error',
            conflicting_lesson_ids: message.conflicting_lesson_ids || [],
            isRejected: true,
          });
          break;
      }
    };

    window.addEventListener('message', handleMessage);

    // Send ready message to request lessons data
    if (window.vscode) {
      window.vscode.postMessage({ type: 'ready' });
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  return (
    <div
      style={{
        width: '100%',
        height: '100vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {error && (
        <div
          style={{
            padding: '10px 16px',
            backgroundColor: isDarkTheme ? '#5a1d1d' : '#ffebee',
            color: isDarkTheme ? '#f48771' : '#d32f2f',
            fontSize: '13px',
            borderBottom: `1px solid ${isDarkTheme ? '#6a2a2a' : '#ffcdd2'}`,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span style={{ fontWeight: 500 }}>Error:</span>
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            style={{
              marginLeft: 'auto',
              background: 'transparent',
              border: 'none',
              color: 'inherit',
              cursor: 'pointer',
              padding: '4px',
              fontSize: '16px',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}
      <LessonsView
        lessons={lessons}
        isDarkTheme={isDarkTheme}
        validationResult={validationResult}
        isValidating={isValidating}
        onClearValidation={() => setValidationResult(null)}
        apiKeyError={apiKeyError}
        onLessonCreate={(data: LessonFormData, force?: boolean) => {
          // Create lesson via postMessage to backend (proxied to ao-playbook)
          if (window.vscode) {
            setIsValidating(true);
            window.vscode.postMessage({
              type: 'add_lesson',
              name: data.name,
              summary: data.summary,
              content: data.content,
              path: data.path || '',
              force: force || false,
            });
          }
        }}
        onLessonUpdate={(id: string, data: Partial<LessonFormData>, force?: boolean) => {
          // Update lesson via postMessage to backend (proxied to ao-playbook)
          if (window.vscode) {
            setIsValidating(true);
            window.vscode.postMessage({
              type: 'update_lesson',
              lesson_id: id,
              ...data,
              force: force || false,
            });
          }
        }}
        onLessonDelete={(id: string) => {
          // Delete lesson via postMessage to backend (proxied to ao-playbook)
          if (window.vscode) {
            window.vscode.postMessage({
              type: 'delete_lesson',
              lesson_id: id,
            });
          }
        }}
        onNavigateToRun={(sessionId: string, nodeId?: string) => {
          // Navigate to the run - open graph tab (optionally focus on node)
          if (window.vscode) {
            window.vscode.postMessage({ type: 'navigateToRun', sessionId, nodeId });
          }
        }}
        onFetchLessonContent={(id: string) => {
          // Fetch individual lesson content via postMessage to backend
          if (window.vscode) {
            window.vscode.postMessage({ type: 'get_lesson', lesson_id: id });
          }
        }}
      />
    </div>
  );
};
