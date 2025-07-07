import React from 'react';
import { useIsVsCodeDarkTheme } from '../utils/themeUtils';

interface ProcessInfo {
  pid: number;
  script_name: string;
  session_id: string;
  status: string;
  role?: string;
}

interface ExperimentsViewProps {
  runningProcesses: ProcessInfo[];
  finishedProcesses: ProcessInfo[];
  onCardClick?: (process: ProcessInfo) => void;
}

export const ExperimentsView: React.FC<ExperimentsViewProps> = ({ runningProcesses, finishedProcesses, onCardClick }) => {
  const isDarkTheme = useIsVsCodeDarkTheme();
  
  const containerStyle: React.CSSProperties = {
    padding: '20px',
    height: '100%',
    overflowY: 'auto',
    backgroundColor: isDarkTheme ? '#252525' : '#F0F0F0',
    color: isDarkTheme ? '#FFFFFF' : '#000000',
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '18px',
    fontWeight: 'bold',
    marginBottom: '20px',
    color: isDarkTheme ? '#FFFFFF' : '#000000',
  };

  const processCardStyle: React.CSSProperties = {
    backgroundColor: isDarkTheme ? '#3C3C3C' : '#FFFFFF',
    border: `1px solid ${isDarkTheme ? '#6B6B6B' : '#CCCCCC'}`,
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '12px',
    boxShadow: isDarkTheme ? '0 2px 4px rgba(0,0,0,0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
    cursor: 'pointer',
  };

  const processTitleStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: 'bold',
    marginBottom: '8px',
    color: isDarkTheme ? '#FFFFFF' : '#000000',
  };

  const processDetailStyle: React.CSSProperties = {
    fontSize: '12px',
    color: isDarkTheme ? '#CCCCCC' : '#666666',
    marginBottom: '4px',
  };

  const statusStyle: React.CSSProperties = {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: '12px',
    fontSize: '10px',
    fontWeight: 'bold',
    textTransform: 'uppercase',
  };

  const getStatusStyle = (status: string): React.CSSProperties => {
    const baseStyle = { ...statusStyle };
    if (status === 'running') {
      return {
        ...baseStyle,
        backgroundColor: '#27C93F',
        color: '#FFFFFF',
      };
    } else {
      return {
        ...baseStyle,
        backgroundColor: '#FF6B6B',
        color: '#FFFFFF',
      };
    }
  };

  const emptyStateStyle: React.CSSProperties = {
    textAlign: 'center',
    padding: '40px 20px',
    color: isDarkTheme ? '#CCCCCC' : '#666666',
  };

  if (runningProcesses.length === 0 && finishedProcesses.length === 0) {
    return (
      <div style={containerStyle}>
        <div style={titleStyle}>Develop Processes</div>
        <div style={emptyStateStyle}>
          <div style={{ fontSize: '16px', marginBottom: '8px' }}>No develop processes</div>
          <div style={{ fontSize: '12px' }}>
            Start a develop process to see it here
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {runningProcesses.length > 0 && (
        <>
          <div style={titleStyle}>Running ({runningProcesses.length})</div>
          {runningProcesses.map((process) => (
            <div key={process.pid} style={processCardStyle} onClick={() => onCardClick && onCardClick(process)}>
              <div style={processTitleStyle}>
                {process.script_name}
                <span style={getStatusStyle(process.status)}>
                  {process.status}
                </span>
              </div>
              <div style={processDetailStyle}>
                <strong>PID:</strong> {process.pid}
              </div>
              <div style={processDetailStyle}>
                <strong>Session:</strong> {process.session_id.substring(0, 8)}...
              </div>
            </div>
          ))}
        </>
      )}
      {finishedProcesses.length > 0 && (
        <>
          <div style={{ ...titleStyle, marginTop: runningProcesses.length > 0 ? 32 : 0 }}>Finished ({finishedProcesses.length})</div>
          {finishedProcesses.map((process) => (
            <div key={process.pid} style={processCardStyle} onClick={() => onCardClick && onCardClick(process)}>
              <div style={processTitleStyle}>
                {process.script_name}
                <span style={getStatusStyle(process.status)}>
                  {process.status}
                </span>
              </div>
              <div style={processDetailStyle}>
                <strong>PID:</strong> {process.pid}
              </div>
              <div style={processDetailStyle}>
                <strong>Session:</strong> {process.session_id.substring(0, 8)}...
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}; 