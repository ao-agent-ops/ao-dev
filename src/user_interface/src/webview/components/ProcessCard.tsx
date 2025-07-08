import React from 'react';
import styles from './ProcessCard.module.css';
import { ProcessInfo } from './ExperimentsView';

/**
 * Card for displaying a process in the experiments view.
 * @param process The process info object
 * @param isHovered Whether the card is hovered
 * @param onClick Click handler
 * @param onMouseEnter Mouse enter handler
 * @param onMouseLeave Mouse leave handler
 * @param isDarkTheme Whether VSCode is in dark mode
 */
export interface ProcessCardProps {
  process: ProcessInfo;
  isHovered: boolean;
  onClick?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  isDarkTheme: boolean;
}

export const ProcessCard: React.FC<ProcessCardProps> = React.memo(({ process, isHovered, onClick, onMouseEnter, onMouseLeave, isDarkTheme }) => {
  return (
    <div
      className={[
        styles.card,
        isDarkTheme ? styles.dark : styles.light,
        isHovered ? styles.hovered : ''
      ].join(' ')}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      tabIndex={0}
    >
      <div className={styles.title}>
        {process.timestamp ? `${process.timestamp} (${process.session_id.substring(0, 8)}...)` : process.script_name}
      </div>
    </div>
  );
}); 