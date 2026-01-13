import React, { 
  useState, 
  useEffect, 
  createContext, 
  useContext, 
  useCallback,
  Suspense 
} from 'react';
import { 
  BrowserRouter as Router, 
  Routes, 
  Route, 
  Link, 
  useLocation, 
  Navigate 
} from 'react-router-dom';
import { 
  Activity, 
  Server, 
  Database, 
  Settings, 
  Shield, 
  Menu, 
  X, 
  Bell, 
  Search,
  RefreshCw,
  Cpu,
  Wifi
} from 'lucide-react';

// --- Types & Interfaces ---

interface SystemMetrics {
  cpuUsage: number;
  memoryUsage: number;
  activeConnections: number;
  latency: number;
  status: 'healthy' | 'degraded' | 'critical';
  lastUpdated: string;
}

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  message: string;
  source: string;
}

interface AppContextType {
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  isConnected: boolean;
  systemMetrics: SystemMetrics | null;
  refreshMetrics: () => Promise<void>;
}

// --- Mock Data Generators (Simulating Backend) ---

const generateMockMetrics = (): SystemMetrics => ({
  cpuUsage: Math.floor(Math.random() * 100),
  memoryUsage: Math.floor(Math.random() * 100),
  activeConnections: Math.floor(Math.random() * 5000) + 1000,
  latency: Math.floor(Math.random() * 200),
  status: Math.random() > 0.8 ? 'degraded' : 'healthy',
  lastUpdated: new Date().toISOString(),
});

const generateMockLogs = (count: number): LogEntry[] => {
  return Array.from({ length: count }).map((_, i) => ({
    id: `log-${Date.now()}-${i}`,
    timestamp: new Date(Date.now() - i * 60000).toISOString(),
    level: Math.random() > 0.9 ? 'ERROR' : Math.random() > 0.7 ? 'WARN' : 'INFO',
    message: `System event detected: Process ID ${Math.floor(Math.random() * 9999)}`,
    source: ['AuthService', 'DataNode-01', 'LoadBalancer', 'PaymentGateway'][Math.floor(Math.random() * 4)],
  }));
};

// --- Context Definition ---

const AppContext = createContext<AppContextType | undefined>(undefined);

const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useAppContext must be used within an AppProvider');
  return context;
};

// --- Components ---

const LoadingSpinner = () => (
  <div className="flex items-center justify-center h-full w-full p-12">
    <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
  </div>
);

const StatusBadge = ({ status }: { status: string }) => {
  const colors = {
    healthy: 'bg-green-500/10 text-green-500 border-green-500/20',
    degraded: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
    critical: 'bg-red-500/10 text-red-500 border-red-500/20',
  };
  
  const style = colors[status as keyof typeof colors] || colors.healthy;

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${style} uppercase tracking-wider`}>
      {status}
    </span>
  );
};

const MetricCard = ({ title, value, icon: Icon, trend }: { title: string, value: string, icon: any, trend?: string }) => (
  <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 hover:border-slate-600 transition-colors">
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-slate-400 text-sm font-medium">{title}</h3>
      <div className="p-2 bg-slate-700/50 rounded-lg">
        <Icon className="w-5 h-5 text-blue-400" />
      </div>
    </div>
    <div className="flex items-end justify-between">
      <span className="text-2xl font-bold text-white">{value}</span>
      {trend && (
        <span className={`text-xs font-medium ${trend.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>
          {trend}
        </span>
      )}
    </div>
  </div>
);

// --- Views ---

const DashboardView = () => {
  const { systemMetrics, refreshMetrics, isConnected } = useAppContext();
  const [logs, setLogs] = useState<LogEntry[]>([]);

  useEffect(() => {
    // Simulate fetching logs
    setLogs(generateMockLogs(5));
  }, []);

  if (!systemMetrics) return <LoadingSpinner />;

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">System Overview</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time infrastructure monitoring</p>
        </div>
        <button 
          onClick={refreshMetrics}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors text-sm font-medium"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh Data
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard 
          title="CPU Usage" 
          value={`${systemMetrics.cpuUsage}%`} 
          icon={Cpu}
          trend={systemMetrics.cpuUsage > 80 ? '+12%' : '-5%'}
        />
        <MetricCard 
          title="Memory" 
          value={`${systemMetrics.memoryUsage}%`} 
          icon={Database}
          trend="+2%"
        />
        <MetricCard 
          title="Active Connections" 
          value={systemMetrics.activeConnections.toLocaleString()} 
          icon={Wifi}
          trend="+124"
        />
        <MetricCard 
          title="System Health" 
          value={systemMetrics.status.toUpperCase()} 
          icon={Activity}
        />
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Area Placeholder */}
        <div className="lg:col-span-2 bg-slate-800 border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-white">Traffic Analysis</h3>
            <select className="bg-slate-700 border-none text-white text-sm rounded px-3 py-1 focus:ring-2 focus:ring-blue-500">
              <option>Last Hour</option>
              <option>Last 24 Hours</option>
              <option>Last 7 Days</option>
            </select>
          </div>
          <div className="h-64 flex items-center justify-center bg-slate-900/50 rounded border border-slate-700 border-dashed">
            <span className="text-slate-500 text-sm">Interactive Chart Component Visualization</span>
          </div>
        </div>

        {/* Recent Logs */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Events</h3>
          <div className="space-y-4">
            {logs.map((log) => (
              <div key={log.id} className="flex gap-3 items-start p-3 rounded bg-slate-700/30 border border-slate-700/50">
                <div className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                  log.level === 'ERROR' ? 'bg-red-500' : log.level === 'WARN' ? 'bg-yellow-500' : 'bg-blue-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-200 font-medium truncate">{log.source}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{log.message}</p>
                </div>
                <span className="text-xs text-slate-500 whitespace-nowrap">
                  {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
          <button className="w-full mt-4 py-2 text-sm text-blue-400 hover:text-blue-300 border border-dashed border-slate-600 rounded hover:bg-slate-700/50 transition-colors">
            View All Logs
          </button>
        </div>
      </div>
    </div>
  );
};

const InfrastructureView = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-white">Infrastructure Map</h1>
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-12 text-center">
      <Server className="w-16 h-16 text-slate-600 mx-auto mb-4" />
      <h3 className="text-xl font-medium text-white">Node Topology</h3>
      <p className="text-slate-400 mt-2">Visual representation of active server nodes and load balancers.</p>
    </div>
  </div>
);

const SettingsView = () => (
  <div className="max-w-2xl space-y-8">
    <div>
      <h1 className="text-2xl font-bold text-white">Settings</h1>
      <p className="text-slate-400 mt-1">Manage your dashboard preferences and API keys.</p>
    </div>

    <div className="bg-slate-800 border border-slate-700 rounded-lg divide-y divide-slate-700">
      <div className="p-6">
        <h3 className="text-lg font-medium text-white mb-4">API Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Endpoint URL</label>
            <input 
              type="text" 
              defaultValue="https://api.codecraft.internal/v1/metrics"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">API Key</label>
            <input 
              type="password" 
              defaultValue="sk_live_xxxxxxxxxxxx"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>
        </div>
      </div>
      
      <div className="p-6 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-white">Auto-Refresh</h3>
          <p className="text-sm text-slate-400">Automatically poll for new data every 30 seconds.</p>
        </div>
        <button className="w-12 h-6 bg-blue-600 rounded-full relative transition-colors">
          <span className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm" />
        </button>
      </div>
    </div>
  </div>
);

// --- Layout Components ---

const SidebarItem = ({ icon: Icon, label, to, active }: { icon: any, label: string, to: string, active: boolean }) => (
  <Link 
    to={to}
    className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 group ${
      active 
        ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' 
        : 'text-slate-400 hover:text-white hover:bg-slate-800'
    }`}
  >
    <Icon className={`w-5 h-5 ${active ? 'text-white' : 'text-slate-400 group-hover:text-white'}`} />
    <span className="font-medium text-sm">{label}</span>
  </Link>
);

const Sidebar = ({ isOpen, setIsOpen }: { isOpen: boolean, setIsOpen: (v: boolean) => void }) => {
  const location = useLocation();
  
  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <aside className={`
        fixed top-0 left-0 z-50 h-screen w-64 bg-slate-900 border-r border-slate-800
        transform transition-transform duration-300 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:translate-x-0 lg:static
      `}>
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <Shield className="w-8 h-8 text-blue-500 mr-3" />
          <span className="text-xl font-bold text-white tracking-tight">CodeCraft</span>
        </div>

        <div className="p-4 space-y-1">
          <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Platform
          </div>
          <SidebarItem 
            icon={Activity} 
            label="Dashboard" 
            to="/" 
            active={location.pathname === '/'} 
          />
          <SidebarItem 
            icon={Server} 
            label="Infrastructure" 
            to="/infrastructure" 
            active={location.pathname === '/infrastructure'} 
          />
          <SidebarItem 
            icon={Database} 
            label="Data Nodes" 
            to="/nodes" 
            active={location.pathname === '/nodes'} 
          />
          
          <div className="mt-8 px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Configuration
          </div>
          <SidebarItem 
            icon={Settings} 
            label="Settings" 
            to="/settings" 
            active={location.pathname === '/settings'} 
          />
        </div>

        <div className="absolute bottom-0 left-0 w-full p-4 border-t border-slate-800 bg-slate-900">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold text-white">
              JS
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">Jane Smith</p>
              <p className="text-xs text-slate-500 truncate">DevOps Engineer</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

const Topbar = ({ onMenuClick }: { onMenuClick: () => void }) => {
  const { isConnected } = useAppContext();

  return (
    <header className="h-16 bg-slate-900/50 backdrop-blur-md border-b border-slate-800 sticky top-0 z-30 px-4 lg:px-8 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <button 
          onClick={onMenuClick}
          className="p-2 text-slate-400 hover:text-white lg:hidden"
        >
          <Menu className="w-6 h-6" />
        </button>
        
        <div className="hidden md:flex items-center relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3" />
          <input 
            type="text" 
            placeholder="Search resources..." 
            className="bg-slate-800 border border-slate-700 text-sm rounded-full pl-10 pr-4 py-1.5 text-slate-300 focus:outline-none focus:border-blue-500 w-64 transition-all"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-full border border-slate-700">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-xs font-medium text-slate-300">
            {isConnected ? 'System Online' : 'Disconnected'}
          </span>
        </div>
        
        <button className="relative p-2 text-slate-400 hover:text-white transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-500 rounded-full border-2 border-slate-900" />
        </button>
      </div>
    </header>
  );
};

const AppLayout = ({ children }: { children: React.ReactNode }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 font-sans overflow-hidden">
      <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
      
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        
        <main className="flex-1 overflow-y-auto p-4 lg:p-8 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

// --- Main App Component ---

const App = () => {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [isConnected, setIsConnected] = useState(false);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);

  // Simulate API Connection and Polling
  const refreshMetrics = useCallback(async () => {
    try {
      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 600));
      const data = generateMockMetrics();
      setSystemMetrics(data);
      setIsConnected(true);
    } catch (error) {
      console.error("Failed to fetch metrics", error);
      setIsConnected(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    refreshMetrics();

    // Polling interval
    const interval = setInterval(refreshMetrics, 5000);
    return () => clearInterval(interval);
  }, [refreshMetrics]);

  const contextValue: AppContextType = {
    theme,
    toggleTheme: () => setTheme(prev => prev === 'dark' ? 'light' : 'dark'),
    isConnected,
    systemMetrics,
    refreshMetrics
  };

  return (
    <AppContext.Provider value={contextValue}>
      <Router>
        <AppLayout>
          <Suspense fallback={<LoadingSpinner />}>
            <Routes>
              <Route path="/" element={<DashboardView />} />
              <Route path="/infrastructure" element={<InfrastructureView />} />
              <Route path="/settings" element={<SettingsView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AppLayout>
      </Router>
    </AppContext.Provider>
  );
};

export default App;
