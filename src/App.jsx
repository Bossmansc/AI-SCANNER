import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'react-hot-toast';

// Layout Components
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';

// Page Components - Lazy Loading for Code Splitting
const HomePage = React.lazy(() => import('./pages/HomePage'));
const DashboardPage = React.lazy(() => import('./pages/DashboardPage'));
const ProfilePage = React.lazy(() => import('./pages/ProfilePage'));
const SettingsPage = React.lazy(() => import('./pages/SettingsPage'));
const AnalyticsPage = React.lazy(() => import('./pages/AnalyticsPage'));
const LoginPage = React.lazy(() => import('./pages/auth/LoginPage'));
const RegisterPage = React.lazy(() => import('./pages/auth/RegisterPage'));
const ForgotPasswordPage = React.lazy(() => import('./pages/auth/ForgotPasswordPage'));
const ResetPasswordPage = React.lazy(() => import('./pages/auth/ResetPasswordPage'));
const NotFoundPage = React.lazy(() => import('./pages/errors/NotFoundPage'));
const ServerErrorPage = React.lazy(() => import('./pages/errors/ServerErrorPage'));
const UnauthorizedPage = React.lazy(() => import('./pages/errors/UnauthorizedPage'));

// Feature Modules
const ProjectsModule = React.lazy(() => import('./modules/projects/ProjectsModule'));
const TasksModule = React.lazy(() => import('./modules/tasks/TasksModule'));
const TeamModule = React.lazy(() => import('./modules/team/TeamModule'));
const DocumentsModule = React.lazy(() => import('./modules/documents/DocumentsModule'));
const CalendarModule = React.lazy(() => import('./modules/calendar/CalendarModule'));

// Context Providers
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { NotificationProvider } from './contexts/NotificationContext';

// Hooks
import { useAuth } from './hooks/useAuth';

// Components
import LoadingSpinner from './components/ui/LoadingSpinner';
import ErrorBoundary from './components/errors/ErrorBoundary';

// Create Query Client with configuration
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Protected Route Component
const ProtectedRoute = ({ children, requiredRoles = [] }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRoles.length > 0) {
    const hasRequiredRole = requiredRoles.some(role => 
      user.roles?.includes(role)
    );
    
    if (!hasRequiredRole) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return children;
};

// Public Route Component (redirects authenticated users away)
const PublicRoute = ({ children }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

// App Component
function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <NotificationProvider>
            <AuthProvider>
              <Router>
                <div className="App">
                  <React.Suspense 
                    fallback={
                      <div className="flex items-center justify-center min-h-screen">
                        <LoadingSpinner size="lg" />
                      </div>
                    }
                  >
                    <Routes>
                      {/* Public Routes */}
                      <Route path="/" element={<HomePage />} />
                      
                      {/* Auth Routes - Only accessible when NOT logged in */}
                      <Route element={<PublicRoute><AuthLayout /></PublicRoute>}>
                        <Route path="/login" element={<LoginPage />} />
                        <Route path="/register" element={<RegisterPage />} />
                        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                        <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
                      </Route>

                      {/* Protected Routes - Require authentication */}
                      <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
                        {/* Dashboard */}
                        <Route path="/dashboard" element={<DashboardPage />} />
                        
                        {/* Profile & Settings */}
                        <Route path="/profile" element={<ProfilePage />} />
                        <Route path="/settings" element={<SettingsPage />} />
                        <Route path="/settings/:tab" element={<SettingsPage />} />
                        
                        {/* Analytics */}
                        <Route path="/analytics" element={<AnalyticsPage />} />
                        
                        {/* Feature Modules */}
                        <Route path="/projects/*" element={<ProjectsModule />} />
                        <Route path="/tasks/*" element={<TasksModule />} />
                        <Route path="/team/*" element={<TeamModule />} />
                        <Route path="/documents/*" element={<DocumentsModule />} />
                        <Route path="/calendar/*" element={<CalendarModule />} />
                        
                        {/* Admin Routes - Require admin role */}
                        <Route 
                          path="/admin/*" 
                          element={
                            <ProtectedRoute requiredRoles={['admin', 'superadmin']}>
                              <React.Suspense fallback={<LoadingSpinner />}>
                                {React.createElement(React.lazy(() => import('./modules/admin/AdminModule')))}
                              </React.Suspense>
                            </ProtectedRoute>
                          } 
                        />
                      </Route>

                      {/* Error Pages */}
                      <Route path="/404" element={<NotFoundPage />} />
                      <Route path="/500" element={<ServerErrorPage />} />
                      <Route path="/unauthorized" element={<UnauthorizedPage />} />
                      
                      {/* Catch-all route for 404 */}
                      <Route path="*" element={<Navigate to="/404" replace />} />
                    </Routes>
                  </React.Suspense>
                  
                  {/* Global Toaster for notifications */}
                  <Toaster
                    position="top-right"
                    toastOptions={{
                      duration: 5000,
                      style: {
                        background: 'var(--bg-secondary)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--border-color)',
                      },
                      success: {
                        iconTheme: {
                          primary: 'var(--success)',
                          secondary: 'var(--bg-secondary)',
                        },
                      },
                      error: {
                        iconTheme: {
                          primary: 'var(--error)',
                          secondary: 'var(--bg-secondary)',
                        },
                      },
                    }}
                  />
                </div>
              </Router>
            </AuthProvider>
          </NotificationProvider>
        </ThemeProvider>
        
        {/* React Query DevTools - Only in development */}
        {process.env.NODE_ENV === 'development' && (
          <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
        )}
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

// Performance optimization: Memoize the App component
export default React.memo(App);
