import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { jwtDecode } from 'jwt-decode';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [userContext, setUserContext] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const logout = useCallback(() => {
    setToken(null);
    setUserContext(null);
    localStorage.removeItem('token');
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [logout]);

  useEffect(() => {
    if (token) {
      try {
        const decoded = jwtDecode(token);
        setUserContext({
          userId: decoded.sub,
          agencyId: decoded.agency_id,
          role: decoded.role,
          clientId: decoded.client_id,
        });
        localStorage.setItem('token', token);
      } catch (e) {
        logout();
      }
    } else {
      setUserContext(null);
    }
    setIsInitializing(false);
  }, [token, logout]);

  const login = (newToken) => {
    setToken(newToken);
  };

  const value = {
    token,
    isAuthenticated: !!token,
    userContext,
    isInitializing,
    login,
    logout,
  };

  if (isInitializing) {
    return null; // Or a loading spinner
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  return useContext(AuthContext);
};
