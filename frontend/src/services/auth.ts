import type { ApiResponse, AuthState } from '../types';

// Default to localhost if VITE_API_URL is not set
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Validate API URL format
const isValidUrl = (url: string) => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

if (!isValidUrl(API_URL)) {
  console.error('Invalid VITE_API_URL:', API_URL);
}

export const isAuthenticated = async (): Promise<boolean> => {
  try {
    console.log('Checking authentication status...');
    
    // Add a small delay to ensure cookie is set
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const response = await fetch(`${API_URL}/auth/check`, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Accept': 'application/json',
        'Cache-Control': 'no-cache',
      },
    });
    
    if (!response.ok) {
      console.log('Auth check failed with status:', response.status);
      const responseText = await response.text();
      console.log('Auth check response:', responseText);
      return false;
    }
    
    const data = await response.json();
    console.log('Auth check response:', data);
    
    // Only check authenticated flag
    if (data.authenticated) {
      return true;
    }
    
    return false;
  } catch (error) {
    console.error('Auth check failed:', error);
    return false;
  }
};

export const checkAuthAndRedirect = async (): Promise<boolean> => {
  const isAuth = await isAuthenticated();
  if (!isAuth) {
    // Save current URL before redirecting
    sessionStorage.setItem('auth_redirect', window.location.pathname);
    window.location.href = '/login';
    return false;
  }
  return true;
};

export const handleLogin = async (): Promise<void> => {
  if (!isValidUrl(API_URL)) {
    throw new Error('Invalid API URL configuration');
  }
  try {
    // Save current URL to session storage to redirect back after auth
    sessionStorage.setItem('auth_redirect', window.location.pathname);
    
    // Open the login URL in the current window
    window.location.href = `${API_URL}/auth/login`;
  } catch (error) {
    console.error('Login redirect failed:', error);
    throw error;
  }
};

export const handleLogout = async (): Promise<ApiResponse<void>> => {
  if (!isValidUrl(API_URL)) {
    throw new Error('Invalid API URL configuration');
  }

  try {
    const response = await fetch(`${API_URL}/auth/logout`, {
      credentials: 'include',
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error('Logout failed');
    }

    window.location.href = '/login';
    return { success: true };
  } catch (error) {
    console.error('Logout failed:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'An error occurred during logout'
    };
  }
};

export const getAuthState = async (): Promise<ApiResponse<AuthState>> => {
  if (!isValidUrl(API_URL)) {
    throw new Error('Invalid API URL configuration');
  }

  try {
    const response = await fetch(`${API_URL}/auth/me`, {
      credentials: 'include',
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get auth state');
    }

    const data = await response.json();
    return {
      success: true,
      data: {
        isAuthenticated: true,
        user: data,
        loading: false,
        error: null
      }
    };
  } catch (error) {
    return {
      success: false,
      data: {
        isAuthenticated: false,
        user: null,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to get auth state'
      }
    };
  }
};
