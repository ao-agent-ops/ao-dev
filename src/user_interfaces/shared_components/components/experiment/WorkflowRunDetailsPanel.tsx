import React, { useState } from "react";
import { WorkflowRunDetailsPanelProps } from "../../types";
import { useIsVsCodeDarkTheme } from "../../utils/themeUtils";

interface Props extends WorkflowRunDetailsPanelProps {
  onBack?: () => void;
  sessionId?: string;
}

const resultOptions = ["Select a result", "Satisfactory", "Failed"];

export const WorkflowRunDetailsPanel: React.FC<Props> = ({
  runName = "",
  result = "",
  notes = "",
  log = "",
  onOpenInTab,
  onBack,
  sessionId = "",
}) => {
  const [localRunName, setLocalRunName] = useState(runName);
  const [localResult, setLocalResult] = useState(result);
  const [localNotes, setLocalNotes] = useState(notes);
  const isDarkTheme = useIsVsCodeDarkTheme();

  const handleRunNameChange = (value: string) => {
    console.log('[WorkflowRunDetailsPanel] Run name changed:', value, 'sessionId:', sessionId);
    setLocalRunName(value);
    if (window.vscode && sessionId) {
      console.log('[WorkflowRunDetailsPanel] Sending update_run_name message to VSCode');
      window.vscode.postMessage({
        type: "update_run_name",
        session_id: sessionId,
        run_name: value,
      });
    } else {
      console.warn('[WorkflowRunDetailsPanel] Cannot send message - window.vscode:', !!window.vscode, 'sessionId:', sessionId);
    }
  };

  const handleResultChange = (value: string) => {
    console.log('[WorkflowRunDetailsPanel] Result changed:', value, 'sessionId:', sessionId);
    setLocalResult(value);
    if (window.vscode && sessionId) {
      console.log('[WorkflowRunDetailsPanel] Sending update_result message to VSCode');
      window.vscode.postMessage({
        type: "update_result",
        session_id: sessionId,
        result: value,
      });
    } else {
      console.warn('[WorkflowRunDetailsPanel] Cannot send message - window.vscode:', !!window.vscode, 'sessionId:', sessionId);
    }
  };

  const handleNotesChange = (value: string) => {
    console.log('[WorkflowRunDetailsPanel] Notes changed (length:', value.length, ') sessionId:', sessionId);
    setLocalNotes(value);
    if (window.vscode && sessionId) {
      console.log('[WorkflowRunDetailsPanel] Sending update_notes message to VSCode');
      window.vscode.postMessage({
        type: "update_notes",
        session_id: sessionId,
        notes: value,
      });
    } else {
      console.warn('[WorkflowRunDetailsPanel] Cannot send message - window.vscode:', !!window.vscode, 'sessionId:', sessionId);
    }
  };
 
  const containerStyle: React.CSSProperties = {
    padding: "20px 20px 40px 20px",
    height: "100%",
    maxHeight: "100%",
    overflowY: "auto",
    boxSizing: "border-box",
    backgroundColor: isDarkTheme ? "#252525" : "#F0F0F0",
    color: isDarkTheme ? "#FFFFFF" : "#000000",
    };

    const fieldStyle: React.CSSProperties = {
      width: "100%",
      padding: "6px 8px",
      fontSize: "14px",
      background: "#2d2d2d",
      color: "#fff",
      border: "1px solid #555",
      borderRadius: "3px",
      boxSizing: "border-box",
      marginBottom: "16px",
    };

    const selectStyle: React.CSSProperties = {
      ...fieldStyle,
      padding: "6px 32px 6px 8px",
      appearance: "none",
      MozAppearance: "none",
      WebkitAppearance: "none",
      marginBottom: "16px",
    };

    const buttonStyle: React.CSSProperties = {
      ...fieldStyle,
      background: "#007acc",
      color: "#fff",
      cursor: "pointer",
      fontSize: "16px",
      border: "1px solid #555",
    };

    const textareaStyle: React.CSSProperties = {
      ...fieldStyle,
      resize: "none",
      minHeight: "80px",
      maxHeight: "150px",
      overflowY: "auto",
      color: "#fff",
      marginBottom: "5px",
    };
    
  return (
    <div style={containerStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          fontWeight: "bold",
          fontSize: 20,
          marginBottom: 20,
        }}
      >
        {onBack && (
          <button
            onClick={onBack}
            style={{
              background: "none",
              border: "none",
              color: "#fff",
              fontSize: 20,
              cursor: "pointer",
              marginRight: 8,
              lineHeight: 1,
              padding: 0,
            }}
            title="Back"
          >
            ⬅️
          </button>
        )}
        Workflow run
      </div>
      {/* Title */}
      <label style={{ fontSize: "20px" }}>Run name</label>
      <input
        type="text"
        value={localRunName}
        onChange={(e) => handleRunNameChange(e.target.value)}
        style={fieldStyle}
      />

      {/* Result */}
      <label style={{ fontSize: "20px" }}>Result</label>
      <div style={{ position: "relative", width: "100%" }}>
        <select
          value={localResult}
          onChange={(e) => handleResultChange(e.target.value)}
          style={selectStyle}
        >
          {resultOptions.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <span
          style={{
            position: "absolute",
            right: "12px",
            top: -6,
            height: "100%",
            display: "flex",
            alignItems: "center",
            pointerEvents: "none",
            color: "#aaa",
            fontSize: "16px",
            lineHeight: 1,
          }}
        >
          ▼
        </span>
      </div>

      {/* Notes */}
      <label style={{ fontSize: "20px" }}>Notes</label>
      <textarea
        value={localNotes}
        onChange={(e) => handleNotesChange(e.target.value)}
        style={textareaStyle}
      />

      {/* Log */}
      <label style={{ fontSize: "20px" }}>Log</label>
      <textarea value={log} readOnly style={textareaStyle} />


      {/* Button open in tab */}
      <button
        onClick={() => {
          if (window.vscode) {
            window.vscode.postMessage({
              type: "open_log_tab_side_by_side",
              payload: {
                runName: localRunName,
                result: localResult,
                log,
              },
            });
          }
        }}
        style={buttonStyle}
      >
        Open in tab
      </button>
    </div>
  );
};