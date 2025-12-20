import React, { useState } from 'react';

interface LoginScreenProps {
  onLogin: () => void;
  isDarkTheme?: boolean;
  onModeChange?: (mode: 'Local' | 'Remote') => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onLogin, isDarkTheme = false, onModeChange }) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [currentMode, setCurrentMode] = useState<'Local' | 'Remote'>('Remote');

  const IconGoogle = ({ size = 20 }: { size?: number }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width={size} height={size}>
      <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
      <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
      <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
      <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
    </svg>
  );

  const handleModeChange = (mode: 'Local' | 'Remote') => {
    setCurrentMode(mode);
    setDropdownOpen(false);

    if (onModeChange) {
      onModeChange(mode);
    }
  };

  const dropdownStyle: React.CSSProperties = {
    position: 'relative',
    marginBottom: '30px',
  };

  const dropdownButtonStyle: React.CSSProperties = {
    padding: '8px 12px',
    fontSize: '14px',
    backgroundColor: isDarkTheme ? '#3c3c3c' : '#f3f3f3',
    color: isDarkTheme ? '#cccccc' : '#333333',
    border: `1px solid ${isDarkTheme ? '#555555' : '#cccccc'}`,
    borderRadius: '4px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const dropdownMenuStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    marginTop: '4px',
    backgroundColor: isDarkTheme ? '#3c3c3c' : '#ffffff',
    border: `1px solid ${isDarkTheme ? '#555555' : '#cccccc'}`,
    borderRadius: '4px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
    zIndex: 1000,
    minWidth: '120px',
  };

  const dropdownItemStyle: React.CSSProperties = {
    padding: '8px 16px',
    fontSize: '14px',
    color: isDarkTheme ? '#cccccc' : '#333333',
    cursor: 'pointer',
    fontFamily: "var(--vscode-font-family, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)",
  };

  const loginButtonStyle: React.CSSProperties = {
    padding: '12px 24px',
    fontSize: 14,
    fontWeight: 'normal',
    color: isDarkTheme ? '#cccccc' : '#303030',
    backgroundColor: isDarkTheme ? '#3C3C3C' : '#fff',
    border: isDarkTheme ? '1px solid #6B6B6B' : '1px solid #CCCCCC',
    borderRadius: 6,
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    transition: 'background-color 0.2s, border-color 0.2s',
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      color: isDarkTheme ? '#fff' : '#000',
      padding: '20px',
      textAlign: 'center'
    }}>
      <div style={{ marginBottom: '20px' }}>
        <svg
          width="64"
          height="64"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="3" y="11" width="18" height="10" rx="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      </div>
      <h2 style={{ marginBottom: '10px' }}>Agops Agent Copilot</h2>
      <p style={{ marginBottom: '20px', opacity: 0.8 }}>
        {currentMode === 'Remote'
          ? 'Please sign in to access remote experiments'
          : 'Using local database'}
      </p>

      {/* Database Mode Selector */}
      <div style={dropdownStyle}>
        <button
          style={dropdownButtonStyle}
          onClick={() => setDropdownOpen(!dropdownOpen)}
        >
          <i className="codicon codicon-database" />
          {currentMode}
          <i className={`codicon ${dropdownOpen ? 'codicon-chevron-up' : 'codicon-chevron-down'}`} />
        </button>
        {dropdownOpen && (
          <div style={dropdownMenuStyle}>
            <div
              style={{
                ...dropdownItemStyle,
                backgroundColor: currentMode === 'Local' ? (isDarkTheme ? '#094771' : '#e3f2fd') : 'transparent',
              }}
              onClick={() => handleModeChange('Local')}
            >
              Local
            </div>
            <div
              style={{
                ...dropdownItemStyle,
                backgroundColor: currentMode === 'Remote' ? (isDarkTheme ? '#094771' : '#e3f2fd') : 'transparent',
              }}
              onClick={() => handleModeChange('Remote')}
            >
              Remote
            </div>
          </div>
        )}
      </div>

      {/* Only show login button in Remote mode */}
      {currentMode === 'Remote' && (
        <button
          onClick={onLogin}
          style={loginButtonStyle}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = isDarkTheme ? '#4a4a4a' : '#f5f5f5';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = isDarkTheme ? '#3C3C3C' : '#fff';
          }}
        >
          Sign in with
          <IconGoogle />
        </button>
      )}
    </div>
  );
};