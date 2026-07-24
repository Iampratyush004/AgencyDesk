import React from 'react';
import { Outlet, Navigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function AppLayout() {
  const { isAuthenticated, userContext, logout } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <h2>AgencyDesk</h2>
        </div>

        <nav className="nav-menu">
          <Link to="/projects" className="nav-item">Projects</Link>
        </nav>

        <div className="user-info">
          <div className="role-badge">
            {userContext?.role?.replace('_', ' ')}
          </div>
          <button onClick={logout} className="logout-btn">
            Logout
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
