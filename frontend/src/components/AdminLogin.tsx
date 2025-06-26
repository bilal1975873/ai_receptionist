import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { isAuthenticated, handleLogin } from '../services/auth';
import type { AuthState } from '../types';
import dplLogo from '../../DPL_LOGO_tagline.png';

const AdminLogin: React.FC = () => {
  const navigate = useNavigate();
  const [authState, setAuthState] = useState<Omit<AuthState, 'user'>>({
    isAuthenticated: false,
    loading: true,
    error: null
  });

  useEffect(() => {
    const checkAuth = async () => {
      try {
        console.log('Checking authentication in AdminLogin...');
        const isAuth = await isAuthenticated();
        console.log('isAuthenticated result:', isAuth);
        
        if (isAuth) {
          console.log('User is authenticated, redirecting...');
          const savedRedirect = sessionStorage.getItem('auth_redirect');
          sessionStorage.removeItem('auth_redirect');
          
          // Force navigation to root or saved redirect
          const targetPath = savedRedirect || '/';
          console.log('Redirecting to:', targetPath);
          
          // Use history.replaceState to clean up the URL
          window.history.replaceState({}, '', targetPath);
          window.location.reload();
          return;
        }
        
        console.log('User is not authenticated');
        setAuthState(prev => ({
          ...prev,
          isAuthenticated: false,
          loading: false
        }));
      } catch (error) {
        console.error('Auth check failed:', error);
        setAuthState(prev => ({
          ...prev,
          loading: false,
          error: error instanceof Error ? error.message : 'Authentication check failed'
        }));
      }
    };

    // Check URL parameters for auth results
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const error = urlParams.get('error');
    const errorMsg = urlParams.get('message');

    if (error) {
      console.error('Auth error:', errorMsg);
      setAuthState(prev => ({
        ...prev,
        loading: false,
        error: errorMsg || 'Authentication failed. Please try again.'
      }));
    } else if (success === 'true') {
      // Auth was successful from the backend, now verify session
      console.log('Auth success from backend, checking session...');
      checkAuth();
    } else {
      // Initial page load
      checkAuth();
    }
  }, [navigate]);

  const onLoginClick = async () => {
    try {
      setAuthState(prev => ({ ...prev, loading: true, error: null }));
      await handleLogin();
    } catch (error) {
      setAuthState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Login failed'
      }));
    }
  };

  if (authState.loading) {
    return (
      <div className="fixed inset-0 bg-black overflow-hidden">
        {/* Animated Grid Background */}
        <div className="absolute inset-0 opacity-40">
          <div className="absolute inset-0" style={{
            backgroundImage: `radial-gradient(circle, rgba(239, 68, 68, 0.6) 1px, transparent 1px)`,
            backgroundSize: '50px 50px',
            animation: 'gridMove 20s linear infinite'
          }}></div>
        </div>
        
        {/* Floating Particles */}
        <div className="absolute inset-0">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="absolute w-1 h-1 bg-red-500 rounded-full opacity-60"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animation: `float ${3 + Math.random() * 4}s ease-in-out infinite`,
                animationDelay: `${Math.random() * 2}s`
              }}
            ></div>
          ))}
        </div>

        {/* Loading Spinner */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-red-600"></div>
            <div className="absolute inset-0 animate-ping rounded-full h-16 w-16 border-2 border-red-400 opacity-30"></div>
          </div>
        </div>

        <style>{`
          @keyframes gridMove {
            0% { transform: translate(0, 0); }
            100% { transform: translate(50px, 50px); }
          }
          @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(180deg); }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black overflow-hidden">
      {/* Animated Grid Background - More Prominent */}
      <div className="absolute inset-0 opacity-50">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle, rgba(239, 68, 68, 0.7) 2px, transparent 2px)`,
          backgroundSize: '60px 60px',
          animation: 'gridMove 25s linear infinite'
        }}></div>
      </div>

      {/* Diagonal Lines Animation */}
      <div className="absolute inset-0 opacity-15">
        <div className="absolute inset-0" style={{
          backgroundImage: `
            repeating-linear-gradient(
              45deg,
              transparent,
              transparent 50px,
              rgba(239, 68, 68, 0.4) 50px,
              rgba(239, 68, 68, 0.4) 52px
            )
          `,
          animation: 'diagonalMove 30s linear infinite'
        }}></div>
      </div>

      {/* Floating Particles */}
      <div className="absolute inset-0">
        {[...Array(30)].map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full opacity-40"
            style={{
              width: `${2 + Math.random() * 4}px`,
              height: `${2 + Math.random() * 4}px`,
              backgroundColor: Math.random() > 0.5 ? '#ef4444' : '#ffffff',
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animation: `float ${4 + Math.random() * 6}s ease-in-out infinite`,
              animationDelay: `${Math.random() * 3}s`
            }}
          ></div>
        ))}
      </div>

      {/* Main Content Container */}
      <div className="absolute inset-0 flex flex-col items-center justify-center p-4">
        {/* Logo Container */}
        <div className="mb-12 transform hover:scale-105 transition-transform duration-300">
          <img 
            src={dplLogo} 
            alt="DPL Logo" 
            className="w-56 mx-auto drop-shadow-2xl filter brightness-110" 
          />
        </div>

        {/* Login Card */}
        <div className="relative z-10 p-10 rounded-3xl shadow-2xl w-full max-w-md backdrop-blur-md border border-red-900/40"
             style={{
               background: `
                 linear-gradient(
                   135deg,
                   rgba(0, 0, 0, 0.9) 0%,
                   rgba(20, 20, 20, 0.95) 50%,
                   rgba(40, 0, 0, 0.9) 100%
                 )
               `,
               boxShadow: `
                 0 25px 50px -12px rgba(239, 68, 68, 0.25),
                 0 0 0 1px rgba(239, 68, 68, 0.1),
                 inset 0 1px 0 rgba(255, 255, 255, 0.1)
               `
             }}>
          
          {/* Card Glow Effect */}
          <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-red-600/20 via-transparent to-white/10 pointer-events-none"></div>
          
          <div className="relative z-10">
            <h1 className="text-4xl font-bold text-center mb-8 bg-gradient-to-r from-white via-red-100 to-red-200 bg-clip-text text-transparent tracking-wide">
              Admin Login
            </h1>
            
            {authState.error && (
              <div className="mb-6 p-4 bg-red-900/40 text-red-300 rounded-xl text-center border border-red-700/50 backdrop-blur-sm animate-pulse shadow-lg">
                <div className="flex items-center justify-center space-x-2">
                  <div className="w-2 h-2 bg-red-400 rounded-full animate-ping"></div>
                  <span>{authState.error}</span>
                </div>
              </div>
            )}
            
            <p className="text-gray-300 mb-8 text-center text-lg leading-relaxed">
              Please log in with your Microsoft account to continue.
            </p>
            
            <button
              onClick={onLoginClick}
              disabled={authState.loading}
              className={`
                relative w-full py-4 px-6 rounded-xl font-bold text-lg transition-all duration-300 shadow-xl group overflow-hidden
                ${authState.loading
                  ? 'bg-red-900/40 text-gray-400 cursor-not-allowed'
                  : 'bg-gradient-to-r from-red-600 via-red-700 to-red-800 text-white hover:from-red-500 hover:via-red-600 hover:to-red-700 hover:scale-105 hover:shadow-2xl focus:ring-4 focus:ring-red-500/50 active:scale-95'}
              `}
              style={{
                boxShadow: authState.loading ? 'none' : '0 10px 25px rgba(239, 68, 68, 0.4), 0 0 0 1px rgba(239, 68, 68, 0.3)'
              }}
            >
              {/* Button Glow Effect */}
              {!authState.loading && (
                <div className="absolute inset-0 bg-gradient-to-r from-white/20 via-transparent to-white/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
              )}
              
              <span className="relative z-10 flex items-center justify-center space-x-2">
                {authState.loading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-gray-400"></div>
                    <span>Signing in...</span>
                  </>
                ) : (
                  <>
                    <span>Sign in with Microsoft</span>
                  </>
                )}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Custom Animations */}
      <style>{`
        @keyframes gridMove {
          0% { transform: translate(0, 0); }
          100% { transform: translate(60px, 60px); }
        }
        
        @keyframes diagonalMove {
          0% { transform: translateX(-100px); }
          100% { transform: translateX(100px); }
        }
        
        @keyframes float {
          0%, 100% { 
            transform: translateY(0px) rotate(0deg) scale(1); 
            opacity: 0.4;
          }
          25% { 
            transform: translateY(-15px) rotate(90deg) scale(1.1); 
            opacity: 0.6;
          }
          50% { 
            transform: translateY(-25px) rotate(180deg) scale(0.9); 
            opacity: 0.8;
          }
          75% { 
            transform: translateY(-15px) rotate(270deg) scale(1.1); 
            opacity: 0.6;
          }
        }
      `}</style>
    </div>
  );
};

export default AdminLogin;