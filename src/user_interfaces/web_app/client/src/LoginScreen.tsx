
import React, { useState } from "react";
import "./App.css";
import "./LoginScreen.css";

const PASSWORD_HASH = import.meta.env.VITE_LOGIN_PASSWORD_HASH || ""; // login password hash from environment variable


function sha256(str: string): Promise<string> {
  // Simple browser SHA-256 using SubtleCrypto
  const encoder = new TextEncoder();
  return window.crypto.subtle.digest("SHA-256", encoder.encode(str)).then(buf => {
    return Array.from(new Uint8Array(buf)).map(x => x.toString(16).padStart(2, "0")).join("");
  });
}

interface LoginScreenProps {
  onSuccess: () => void;
}

export function LoginScreen({ onSuccess }: LoginScreenProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const hash = await sha256(password);
    if (hash === PASSWORD_HASH) {
      onSuccess();
    } else {
      setError("Incorrect password");
    }
    setLoading(false);
  };

  return (
    <div className="login-screen">
      <form className="login-form" onSubmit={handleSubmit}>
        <div className="login-logo">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#007acc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        </div>
        <h2 className="login-title">Welcome!</h2>
        <p className="login-desc">Please enter your password to continue</p>
        <input
          className="login-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={loading}
        />
        <button
          className="login-btn"
          type="submit"
          disabled={loading || !password}
        >
          {loading ? "Checking..." : "Login"}
        </button>
        {error && <div className="login-error">{error}</div>}
      </form>
    </div>
  );
}
