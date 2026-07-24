import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { apiFetch } from '../api/client';

export default function Login() {
  const { isAuthenticated, login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const [agencies, setAgencies] = useState(null);

  if (isAuthenticated) {
    return <Navigate to="/projects" replace />;
  }

  const handleLogin = async (e, agencyId = null) => {
    if (e) e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const payload = {
        email,
        password,
        agency_id: agencyId
      };

      const response = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (response.status === 'authenticated') {
        login(response.access_token);
      } else if (response.status === 'agency_selection_required') {
        setAgencies(response.agencies);
      }
    } catch (err) {
      setError(err.data?.detail || 'Login failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h2>AgencyDesk</h2>
        <p className="subtitle">Sign in to your account</p>

        {error && <div className="error-alert">{error}</div>}

        {!agencies ? (
          <form onSubmit={handleLogin} className="login-form">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>

            <button type="submit" disabled={isLoading} className="submit-btn">
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        ) : (
          <div className="agency-selection">
            <h3>Select your agency</h3>
            <p className="help-text">Your account is associated with multiple agencies.</p>
            <div className="agency-list">
              {agencies.map(agency => (
                <button
                  key={agency.id}
                  className="agency-btn"
                  onClick={() => handleLogin(null, agency.id)}
                  disabled={isLoading}
                >
                  <span className="agency-name">{agency.name}</span>
                  <span className="agency-role">{agency.role.replace('_', ' ')}</span>
                </button>
              ))}
            </div>
            <button
              className="back-btn"
              onClick={() => setAgencies(null)}
              disabled={isLoading}
            >
              &larr; Back to Login
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
