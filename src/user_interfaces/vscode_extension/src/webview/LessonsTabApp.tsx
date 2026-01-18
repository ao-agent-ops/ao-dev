import React, { useState, useEffect } from 'react';
import { LessonsView, Lesson } from '../../../shared_components/components/lessons/LessonsView';
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
  const isDarkTheme = useIsVsCodeDarkTheme();

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      switch (message.type) {
        case 'lessons_list':
          console.log('[LessonsTabApp] Received lessons_list:', message.lessons);
          setLessons(message.lessons || []);
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
      }}
    >
      <LessonsView
        lessons={lessons}
        isDarkTheme={isDarkTheme}
        onAddLesson={() => {
          // Add a new lesson via postMessage to backend
          const newLessonId = `lesson-${Date.now()}`;
          if (window.vscode) {
            window.vscode.postMessage({
              type: 'add_lesson',
              lesson_id: newLessonId,
              lesson_text: 'New lesson - click to edit',
            });
          }
        }}
        onLessonUpdate={(id, content) => {
          // Update lesson via postMessage to backend
          if (window.vscode) {
            window.vscode.postMessage({
              type: 'update_lesson',
              lesson_id: id,
              lesson_text: content,
            });
          }
        }}
        onLessonDelete={(id) => {
          // Delete lesson via postMessage to backend
          if (window.vscode) {
            window.vscode.postMessage({
              type: 'delete_lesson',
              lesson_id: id,
            });
          }
        }}
        onNavigateToRun={(sessionId, nodeId) => {
          // Navigate to the run - open graph tab (optionally focus on node)
          if (window.vscode) {
            window.vscode.postMessage({ type: 'navigateToRun', sessionId, nodeId });
          }
        }}
      />
    </div>
  );
};
