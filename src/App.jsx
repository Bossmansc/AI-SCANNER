import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'react-hot-toast';

// Context Providers
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { WebSocketProvider } from './contexts/WebSocketContext';

// Layouts
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';

// Components
import LoadingScreen from './components/ui/LoadingScreen';
import ErrorBoundary from './components/common/ErrorBoundary';

// Lazy Loaded Pages - Performance Optimization
const Dashboard = lazy(() => import('./pages/dashboard/Dashboard'));
const Analytics = lazy(() => import('./pages/analytics/Analytics'));
const UserManagement = lazy(() => import('./pages/users/UserManagement'));
const SystemHealth = lazy(() => import('./pages/system/SystemHealth'));
const Settings = lazy(() => import('./pages/settings/Settings'));
const UserProfile = lazy(() => import('./pages/profile/UserProfile'));

// Auth Pages
const Login = lazy(() => import('./pages/auth/Login'));
const Register = lazy(() => import('./pages/auth/Register'));
const ForgotPassword = lazy(() => import('./pages/auth/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/auth/ResetPassword'));

// Error Pages
const NotFound = lazy(() => import('./pages/errors/NotFound'));
const Unauthorized = lazy(() => import('./pages/errors/Unauthorized'));
const ServerError = lazy(() => import('./pages/errors/ServerError'));

// Initialize React Query Client with default stale times for high-concurrency caching
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      cacheTime: 1000 * 60 * 30, // 30 minutes
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

/**
 * ScrollToTop
 * Utility component to ensure view resets on route change
 */
const ScrollToTop = () => {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
};

/**
 * ProtectedRoute
 * Higher-order component to guard routes requiring authentication
 */
const ProtectedRoute = ({ children, requiredRole = null }) => {
  const { isAuthenticated, user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen fullScreen />;
  }

  if (!isAuthenticated) {
    // Redirect to login while saving the attempted location
    return <Navigate to="/auth/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user?.role !== requiredRole && user?.role !== 'admin') {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

/**
 * PublicRoute
 * Guards routes that should only be accessible when NOT authenticated (e.g. Login)
 */
const PublicRoute = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen fullScreen />;
  }

  if (isAuthenticated) {
    // Redirect to dashboard or the page they came from
    const from = location.state?.from?.pathname || '/dashboard';
    return <Navigate to={from} replace />;
  }

  return children;
};

/**
 * App Component
 * Root application structure containing providers, routing logic, and global layout configuration.
 */
const App = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ThemeProvider>
            <WebSocketProvider>
              <Router>
                <ScrollToTop />
                <Toaster 
                  position="top-right"
                  toastOptions={{
                    duration: 4000,
                    style: {
                      background: '#333',
                      color: '#fff',
                    },
                    success: {
                      duration: 3000,
                      theme: {
                        primary: '#4aed88',
                        secondary: 'black',
                      },
                    },
                  }}
                />
                
                <Suspense fallback={<LoadingScreen fullScreen />}>
                  <Routes>
                    {/* Authentication Routes */}
                    <Route path="/auth" element={<AuthLayout />}>
                      <Route path="login" element={
                        <PublicRoute>
                          <Login />
                        </PublicRoute>
                      } />
                      <Route path="register" element={
                        <PublicRoute>
                          <Register />
                        </PublicRoute>
                      } />
                      <Route path="forgot-password" element={
                        <PublicRoute>
                          <ForgotPassword />
                        </PublicRoute>
                      } />
                      <Route path="reset-password" element={
                        <PublicRoute>
                          <ResetPassword />
                        </PublicRoute>
                      } />
                      <Route index element={<Navigate to="/auth/login" replace />} />
                    </Route>

                    {/* Protected Application Routes */}
                    <Route path="/" element={<MainLayout />}>
                      <Route index element={<Navigate to="/dashboard" replace />} />
                      
                      <Route path="dashboard" element={
                        <ProtectedRoute>
                          <Dashboard />
                        </ProtectedRoute>
                      } />

                      <Route path="analytics" element={
                        <ProtectedRoute requiredRole="analyst">
                          <Analytics />
                        </ProtectedRoute>
                      } />

                      <Route path="users" element={
                        <ProtectedRoute requiredRole="admin">
                          <UserManagement />
                        </ProtectedRoute>
                      } />

                      <Route path="system" element={
                        <ProtectedRoute requiredRole="admin">
                          <SystemHealth />
                        </ProtectedRoute>
                      } />

                      <Route path="settings" element={
                        <ProtectedRoute>
                          <Settings />
                        </ProtectedRoute>
                      } />

                      <Route path="profile" element={
                        <ProtectedRoute>
                          <UserProfile />
                        </ProtectedRoute>
                      } />
                    </Route>

                    {/* Error Routes */}
                    <Route path="/unauthorized" element={<Unauthorized />} />
                    <Route path="/500" element={<ServerError />} />
                    <Route path="*" element={<NotFound />} />
                  </Routes>
                </Suspense>
              </Router>
            </WebSocketProvider>
          </ThemeProvider>
        </AuthProvider>
        <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
      </QueryClientProvider>
    </ErrorBoundary>
  );
};

export default App;
