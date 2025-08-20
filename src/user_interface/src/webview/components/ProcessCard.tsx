import React from 'react';
import styles from './ProcessCard.module.css';
import { ProcessInfo } from '../types';
import { getDateOnly } from '../utils/timeSpan';


export interface ProcessCardProps {
  process: ProcessInfo;
  isHovered: boolean;
  onClick?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  isDarkTheme: boolean;
  nodeColors: string[];
}

export const ProcessCard: React.FC<ProcessCardProps> = React.memo(
  ({
    process,
    isHovered,
    onClick,
    onMouseEnter,
    onMouseLeave,
    isDarkTheme,
    nodeColors,
  }) => {
    // Debug logging
    console.log(`ProcessCard render for ${process.session_id}:`, { nodeColors, color_preview: process.color_preview });
    
    const handleClick = async () => {
      // Call original onClick (experiment clicks now handled by server)
      onClick?.();
    };
    
    return (
      <div
        className={[
          styles.card,
          isDarkTheme ? styles.dark : styles.light,
          isHovered ? styles.hovered : "",
        ].join(" ")}
        onClick={handleClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        tabIndex={0}
      >
        <div
          className={styles.headerRow}
          style={{ display: "flex", alignItems: "center", width: "100%", justifyContent: "space-between", gap: 8 }}
        >
          <div className={styles.title} style={{ textAlign: "left", flex: 1, minWidth: 0, wordBreak: 'break-word', whiteSpace: 'normal' }}>
            {process.title ? process.title : "Untitled"}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0, gap: 8, minWidth: 0, justifyContent: 'flex-end' }}>           
            <div
              className={styles.date}
              style={{ fontSize: 13, color: "#aaa", whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 60 }}
            >
              {process.timestamp}
              {/* Uncomment the line below if you want to use getDateOnly*/}
              {/* Returns only the date part (YYYY-MM-DD) from a timestamp like '2024-06-21 12:00:00' */}
              {/* {getDateOnly(process.timestamp)} */}
            </div>
          </div>
        </div>
        <div className={styles.nodeBar}>
          {Array.from({ length: Math.min(nodeColors.length, 10) }).map(
            (_, i) => (
              <span
                key={i}
                className={styles.nodeRect}
                style={{
                  background: nodeColors[i] || "#00c542",
                }}
              />
            )
          )}
        </div>
      </div>
    );
  }
);
