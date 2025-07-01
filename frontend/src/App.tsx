import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ChatContainer } from './components/ChatContainer';
import { visitorService } from './services/api';
import AdminLogin from './components/AdminLogin';
import { isAuthenticated } from './services/auth';
import type { ChatState } from './types';
import dplLogo from '../DPL_LOGO_tagline.png';

const INITIAL_STATE: ChatState = {
  messages: [
    {
      type: 'bot',
      content: '🙄 Oh look, another human at the gates of innovation.  \nI’m your AI receptionist, not a therapist, so let’s keep this short.\n\nYou are:\n🧍 Guest – here to sip coffee and nod?  \n📦 Vendor – bless us with cardboard and chaos?  \n📅 Meeting – how official of you.',
      timestamp: new Date(),
    },
  ],
  currentStep: 'visitor_type',
  visitorInfo: {},
  isLoading: false,
};

// Protected Route component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const [isAuth, setIsAuth] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        console.log('ProtectedRoute: Checking authentication...');
        const auth = await isAuthenticated();
        console.log('ProtectedRoute: Authentication result:', auth);
        
        if (!auth) {
          console.log('ProtectedRoute: Not authenticated, redirecting to login...');
          // Save the current path for redirect after login
          sessionStorage.setItem('auth_redirect', window.location.pathname);
        }
        
        setIsAuth(auth);
      } catch (error) {
        console.error('ProtectedRoute: Auth check failed:', error);
        setIsAuth(false);
      }
    };
    
    checkAuth();
  }, []);

  if (isAuth === null) {
    console.log('ProtectedRoute: Loading state...');
    return (
      <div className="fixed inset-0 bg-black overflow-hidden">
        {/* Animated Dot Grid Background */}
        <div className="absolute inset-0 opacity-40">
          <div className="absolute inset-0" style={{
            backgroundImage: 'radial-gradient(circle at 25px 25px, rgba(239, 68, 68, 0.6) 1px, transparent 0.5px)',
            backgroundSize: '50px 50px',
            animation: 'gridMove 20s linear infinite'
          }}></div>
        </div>
        
        {/* Floating Particles */}
        <div className="absolute inset-0">
          {[...Array(15)].map((_, i) => {
            const left = Math.random() * 100 + '%';
            const top = Math.random() * 100 + '%';
            const anim = `float ${3 + Math.random() * 4}s ease-in-out infinite`;
            const animDelay = `${Math.random() * 2}s`;
            return (
              <div
                key={i}
                className="absolute w-1 h-1 bg-red-500 rounded-full opacity-60"
                style={{
                  left,
                  top,
                  animation: anim,
                  animationDelay: animDelay
                }}
              ></div>
            );
          })}
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

  console.log('ProtectedRoute: Render decision -', isAuth ? 'showing content' : 'redirecting to login');
  return isAuth ? <>{children}</> : <Navigate to="/login" replace />;
};

function App() {
  const [state, setState] = useState<ChatState>(INITIAL_STATE);

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      const auth = await isAuthenticated();
      if (!auth) {
        setState(prev => ({ ...prev, messages: [] }));
      }
    };
    checkAuth();
  }, []);

  const resetChat = () => {
    setState(INITIAL_STATE);
  };

  const handleSend = async (message: string) => {
    // If in completed state, reset the chat for new visitor
    if (state.currentStep === 'complete' && !state.isLoading) {
      resetChat();
      return;
    }

    // Prepare a new visitorInfo object
    const updatedVisitorInfo = { ...state.visitorInfo };

    // If the current step is host selection and the user selected an employee by number
    if (
      state.currentStep === 'host' &&
      state.visitorInfo.employee_selection_mode &&
      !isNaN(Number(message)) &&
      state.visitorInfo.employee_matches &&
      state.visitorInfo.employee_matches.length > 0
    ) {
      const idx = Number(message) - 1;
      const selected = state.visitorInfo.employee_matches[idx];
      if (selected) {
        updatedVisitorInfo.host_confirmed = selected.displayName;
        updatedVisitorInfo.host_email = selected.email;
        // --- Always preserve visitor_email when updating host fields ---
        updatedVisitorInfo.visitor_email = state.visitorInfo.visitor_email || updatedVisitorInfo.visitor_email || state.visitorInfo.email || updatedVisitorInfo.email || '';
      }
    }

    // Ensure visitor_email is always present
    if (!updatedVisitorInfo.visitor_email) {
      updatedVisitorInfo.visitor_email = updatedVisitorInfo.email || state.visitorInfo.visitor_email || state.visitorInfo.email || '';
    }
    console.log('[DEBUG][FRONTEND] visitorInfo before API call:', updatedVisitorInfo);

    // Add user message
    setState(prev => ({
      ...prev,
      messages: [...prev.messages, { type: 'user', content: message, timestamp: new Date() }],
      isLoading: true,
    }));

    try {
      console.log('[DEBUG] updatedVisitorInfo before API call:', updatedVisitorInfo);
      const { response, nextStep, visitorInfo } = await visitorService.processMessage(
        message,
        state.currentStep,
        updatedVisitorInfo
      );

      // Check if registration is completed
      if (visitorInfo?.registration_completed) {
        setState(prev => ({
          ...prev,
          messages: [
            ...prev.messages,
            { type: 'bot', content: response, timestamp: new Date() },
          ],
          currentStep: nextStep,
          visitorInfo: {
            ...prev.visitorInfo,  // preserve existing visitorInfo fields
            ...visitorInfo,       // merge with new visitorInfo from backend
            // explicitly keep host-related fields if they exist in prev state
            host_confirmed: visitorInfo.host_confirmed || prev.visitorInfo.host_confirmed,
            host_email: visitorInfo.host_email || prev.visitorInfo.host_email,
            employee_selection_mode: visitorInfo.employee_selection_mode || prev.visitorInfo.employee_selection_mode,
            employee_matches: visitorInfo.employee_matches || prev.visitorInfo.employee_matches,
          },
          isLoading: false,
        }));
      } else {
        // Only clear employee selection state if explicitly prompted for new host name
        if (typeof response === 'string' && 
            response.trim().toLowerCase().includes("please enter the name of the person you're scheduled to meet with") &&
            !response.includes("Type 'confirm' to proceed")) {
          visitorInfo.employee_selection_mode = false;
          visitorInfo.employee_matches = [];
          console.log('[DEBUG] Cleared employee selection state in frontend after prompt for new host name');
        }

        // Update state with AI response
        setState(prev => ({
          ...prev,
          messages: [
            ...prev.messages,
            { type: 'bot', content: response, timestamp: new Date() },
          ],
          currentStep: nextStep,
          visitorInfo: {
            ...prev.visitorInfo,  // preserve existing visitorInfo fields
            ...visitorInfo,       // merge with new visitorInfo from backend
            // explicitly keep host-related fields if they exist in prev state
            host_confirmed: visitorInfo.host_confirmed || prev.visitorInfo.host_confirmed,
            host_email: visitorInfo.host_email || prev.visitorInfo.host_email,
            employee_selection_mode: visitorInfo.employee_selection_mode || prev.visitorInfo.employee_selection_mode,
            employee_matches: visitorInfo.employee_matches || prev.visitorInfo.employee_matches,
          },
          isLoading: false,
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        messages: [
          ...prev.messages,
          { 
            type: 'bot', 
            content: 'I apologize, but I encountered an error processing your request. Please try again or contact support.',
            timestamp: new Date()
          },
        ],
        isLoading: false,
      }));
      console.error('Error processing message:', error);
    }
  };

  const ChatInterface = () => (
    <div className="fixed inset-0 w-screen h-screen bg-black overflow-hidden">
      {/* Animated Dot Grid Background */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute inset-0" style={{
          backgroundImage: 'radial-gradient(circle at 30px 30px, rgba(239, 68, 68, 0.5) 1.5px, transparent 1.5px)',
          backgroundSize: '60px 60px',
          animation: 'gridMove 25s linear infinite'
        }}></div>
      </div>

      {/* Diagonal Lines Animation */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute inset-0" style={{
          backgroundImage: `repeating-linear-gradient(45deg, transparent, transparent 80px, rgba(239, 68, 68, 0.3) 80px, rgba(239, 68, 68, 0.3) 82px)`,
          animation: 'diagonalMove 40s linear infinite'
        }}></div>
      </div>

      {/* Floating Particles */}
      <div className="absolute inset-0">
        {[...Array(25)].map((_, i) => {
          const width = 1 + Math.random() * 3 + 'px';
          const height = 1 + Math.random() * 3 + 'px';
          const backgroundColor = Math.random() > 0.7 ? '#ef4444' : '#ffffff';
          const left = Math.random() * 100 + '%';
          const top = Math.random() * 100 + '%';
          const animation = `float ${5 + Math.random() * 8}s ease-in-out infinite`;
          const animationDelay = `${Math.random() * 4}s`;
          return (
            <div
              key={i}
              className="absolute rounded-full opacity-30"
              style={{
                width,
                height,
                backgroundColor,
                left,
                top,
                animation,
                animationDelay
              }}
            ></div>
          );
        })}
      </div>

      {/* Enhanced Gradient Overlays */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-red-900/8 to-black/40"></div>
      <div className="fixed top-0 right-0 w-1/2 h-screen bg-gradient-to-l from-red-900/15 via-red-900/5 to-transparent pointer-events-none"></div>
      <div className="fixed top-0 left-0 w-1/2 h-screen bg-gradient-to-r from-red-900/15 via-red-900/5 to-transparent pointer-events-none"></div>

      {/* Corner Accent Elements */}
      <div className="fixed top-0 right-0 w-40 h-40 bg-gradient-to-bl from-red-500/15 via-red-600/8 to-transparent rounded-bl-full"></div>
      <div className="fixed top-0 left-0 w-40 h-40 bg-gradient-to-br from-red-500/15 via-red-600/8 to-transparent rounded-br-full"></div>
      <div className="fixed bottom-0 right-0 w-32 h-32 bg-gradient-to-tl from-red-500/10 via-red-600/5 to-transparent rounded-tl-full"></div>
      <div className="fixed bottom-0 left-0 w-32 h-32 bg-gradient-to-tr from-red-500/10 via-red-600/5 to-transparent rounded-tr-full"></div>

      <div className="relative z-10 container mx-auto px-4 min-h-screen flex flex-col">
        {/* Enhanced Logo Container */}
        <div className="flex justify-center mb-8 pt-8">
          <div className="relative transform hover:scale-105 transition-transform duration-300">
            <img 
              src={dplLogo} 
              alt="DPL Logo" 
              className="h-16 md:h-20 drop-shadow-2xl filter brightness-110" 
            />
            {/* Logo glow effect */}
            <div className="absolute inset-0 rounded-lg bg-gradient-to-r from-red-600/20 via-transparent to-white/10 opacity-0 hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
          </div>
        </div>

        <div className="flex-1 flex flex-col">
          <ChatContainer
            messages={state.messages}
            isLoading={state.isLoading}
            onSend={handleSend}
            onStartOver={resetChat}
          />
        </div>

        {/* Enhanced Bottom Accent */}
        <div className="h-2 w-full bg-gradient-to-r from-red-900/30 via-red-600/50 to-red-900/30 fixed bottom-0 left-0 shadow-lg">
          <div className="h-full w-full bg-gradient-to-r from-transparent via-red-400/20 to-transparent animate-pulse"></div>
        </div>
      </div>

      {/* Custom Animations */}
      <style>{`
        @keyframes gridMove {
          0% { transform: translate(0, 0); }
          100% { transform: translate(60px, 60px); }
        }
        
        @keyframes diagonalMove {
          0% { transform: translateX(-160px); }
          100% { transform: translateX(160px); }
        }
        
        @keyframes float {
          0%, 100% { 
            transform: translateY(0px) rotate(0deg) scale(1); 
            opacity: 0.3;
          }
          25% { 
            transform: translateY(-10px) rotate(90deg) scale(1.2); 
            opacity: 0.5;
          }
          50% { 
            transform: translateY(-20px) rotate(180deg) scale(0.8); 
            opacity: 0.7;
          }
          75% { 
            transform: translateY(-10px) rotate(270deg) scale(1.2); 
            opacity: 0.5;
          }
        }
      `}</style>
    </div>
  );

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<AdminLogin />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ChatInterface />
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;