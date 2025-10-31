'use client';

import { useEffect, useState } from 'react';

export default function AuthButton() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    const token = localStorage.getItem('auth_token');

    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/auth/status', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setIsAuthenticated(true);
        setUserEmail(data.email);
      } else {
        // Token is invalid
        localStorage.removeItem('auth_token');
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = () => {
    window.location.href = 'http://localhost:8000/auth/google/login';
  };

  const handleLogout = async () => {
    const token = localStorage.getItem('auth_token');

    if (token) {
      try {
        await fetch('http://localhost:8000/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      } catch (error) {
        console.error('Error logging out:', error);
      }
    }

    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
    setUserEmail(null);
  };

  if (loading) {
    return (
      <button className="px-4 py-2 bg-gray-200 text-black rounded" disabled>
        Loading...
      </button>
    );
  }

  if (isAuthenticated) {
    return (
      <div className="flex items-center gap-4">
        <span className="text-sm text-black">
          Logged in as: {userEmail}
        </span>
        <button
          onClick={handleLogout}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleLogin}
      className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
    >
      Login with Google
    </button>
  );
}
