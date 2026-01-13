import React, { useState, useMemo } from 'react';
import { 
  Search, 
  Server, 
  MoreVertical, 
  RefreshCw, 
  Power, 
  Activity, 
  AlertCircle, 
  CheckCircle2, 
  Clock,
  Globe,
  Cpu
} from 'lucide-react';

/**
 * ServerList Component
 * 
 * Displays a comprehensive data table of server instances with:
 * - Sorting (Name, Region, Status, Load, Uptime)
 * - Filtering (Search by name/IP)
 * - Status indicators
 * - Action menus
 */

const STATUS_COLORS = {
  online: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
  offline: 'bg-rose-500/10 text-rose-500 border-rose-500/20',
  maintenance: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
  booting: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
};

const STATUS_ICONS = {
  online: CheckCircle2,
  offline: AlertCircle,
  maintenance: Clock,
  booting: RefreshCw,
};

const ServerList = ({ servers = [], onServerAction }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'name', direction: 'asc' });
  const [selectedServerId, setSelectedServerId] = useState(null);

  // Handle sorting logic
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  // Process data: Filter -> Sort
  const processedServers = useMemo(() => {
    let data = [...servers];

    // 1. Filter
    if (searchQuery) {
      const lowerQuery = searchQuery.toLowerCase();
      data = data.filter(server => 
        server.name.toLowerCase().includes(lowerQuery) ||
        server.ip.includes(lowerQuery) ||
        server.region.toLowerCase().includes(lowerQuery)
      );
    }

    // 2. Sort
    data.sort((a, b) => {
      if (a[sortConfig.key] < b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (a[sortConfig.key] > b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    return data;
  }, [servers, searchQuery, sortConfig]);

  const getStatusBadge = (status) => {
    const normalizedStatus = status.toLowerCase();
    const colorClass = STATUS_COLORS[normalizedStatus] || 'bg-slate-500/10 text-slate-500 border-slate-500/20';
    const Icon = STATUS_ICONS[normalizedStatus] || Activity;

    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${colorClass}`}>
        <Icon size={12} className={normalizedStatus === 'booting' ? 'animate-spin' : ''} />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const renderSortIcon = (columnKey) => {
    if (sortConfig.key !== columnKey) return null;
    return (
      <span className="ml-1 text-slate-400">
        {sortConfig.direction === 'asc' ? '↑' : '↓'}
      </span>
    );
  };

  return (
    <div className="w-full bg-slate-900 border border-slate-800 rounded-xl shadow-xl overflow-hidden flex flex-col h-full">
      {/* Header Toolbar */}
      <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/50">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-indigo-500/10 rounded-lg">
            <Server className="text-indigo-400" size={20} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Server Instances</h2>
            <p className="text-xs text-slate-400">Manage your infrastructure nodes</p>
          </div>
        </div>

        <div className="relative group">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-slate-500 group-focus-within:text-indigo-400 transition-colors" />
          </div>
          <input
            type="text"
            className="block w-full sm:w-64 pl-10 pr-3 py-2 border border-slate-700 rounded-lg leading-5 bg-slate-950 text-slate-300 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm transition-all"
            placeholder="Search by name, IP, or region..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Data Table */}
      <div className="overflow-x-auto flex-grow">
        <table className="min-w-full divide-y divide-slate-800">
          <thead className="bg-slate-950/50">
            <tr>
              <th 
                scope="col" 
                className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider cursor-pointer hover:text-slate-200 transition-colors"
                onClick={() => handleSort('name')}
              >
                Instance Name {renderSortIcon('name')}
              </th>
              <th 
                scope="col" 
                className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider cursor-pointer hover:text-slate-200 transition-colors"
                onClick={() => handleSort('region')}
              >
                Region {renderSortIcon('region')}
              </th>
              <th 
                scope="col" 
                className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider cursor-pointer hover:text-slate-200 transition-colors"
                onClick={() => handleSort('status')}
              >
                Status {renderSortIcon('status')}
              </th>
              <th 
                scope="col" 
                className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider cursor-pointer hover:text-slate-200 transition-colors"
                onClick={() => handleSort('load')}
              >
                Load {renderSortIcon('load')}
              </th>
              <th 
                scope="col" 
                className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider cursor-pointer hover:text-slate-200 transition-colors"
                onClick={() => handleSort('uptime')}
              >
                Uptime {renderSortIcon('uptime')}
              </th>
              <th scope="col" className="relative px-6 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="bg-slate-900 divide-y divide-slate-800">
            {processedServers.length > 0 ? (
              processedServers.map((server) => (
                <tr 
                  key={server.id} 
                  className="hover:bg-slate-800/50 transition-colors group"
                >
                  {/* Name & IP Column */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-10 w-10 rounded-lg bg-slate-800 flex items-center justify-center border border-slate-700">
                        <Server className="h-5 w-5 text-slate-400" />
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-slate-200">{server.name}</div>
                        <div className="text-xs text-slate-500 font-mono">{server.ip}</div>
                      </div>
                    </div>
                  </td>

                  {/* Region Column */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center text-sm text-slate-400">
                      <Globe className="mr-1.5 h-3.5 w-3.5 text-slate-500" />
                      {server.region}
                    </div>
                  </td>

                  {/* Status Column */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getStatusBadge(server.status)}
                  </td>

                  {/* Load Column */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Cpu className="mr-2 h-4 w-4 text-slate-500" />
                      <div className="w-24 bg-slate-800 rounded-full h-1.5 mr-2 overflow-hidden">
                        <div 
                          className={`h-1.5 rounded-full ${
                            server.load > 90 ? 'bg-rose-500' : 
                            server.load > 70 ? 'bg-amber-500' : 'bg-emerald-500'
                          }`} 
                          style={{ width: `${server.load}%` }}
                        ></div>
                      </div>
                      <span className="text-sm text-slate-300">{server.load}%</span>
                    </div>
                  </td>

                  {/* Uptime Column */}
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-400">
                    {server.uptime}
                  </td>

                  {/* Actions Column */}
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button 
                        onClick={() => onServerAction(server.id, 'restart')}
                        className="p-1.5 text-slate-400 hover:text-amber-400 hover:bg-amber-400/10 rounded-md transition-colors"
                        title="Restart Server"
                      >
                        <RefreshCw size={16} />
                      </button>
                      <button 
                        onClick={() => onServerAction(server.id, 'stop')}
                        className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-400/10 rounded-md transition-colors"
                        title="Stop Server"
                      >
                        <Power size={16} />
                      </button>
                      <button 
                        onClick={() => setSelectedServerId(selectedServerId === server.id ? null : server.id)}
                        className="p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-indigo-400/10 rounded-md transition-colors"
                      >
                        <MoreVertical size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="6" className="px-6 py-12 text-center">
                  <div className="flex flex-col items-center justify-center text-slate-500">
                    <Server className="h-12 w-12 mb-3 opacity-20" />
                    <p className="text-lg font-medium">No servers found</p>
                    <p className="text-sm">Try adjusting your search filters</p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {/* Footer / Pagination Placeholder */}
      <div className="bg-slate-950/50 px-6 py-3 border-t border-slate-800 flex items-center justify-between">
        <div className="text-xs text-slate-500">
          Showing <span className="font-medium text-slate-300">{processedServers.length}</span> of <span className="font-medium text-slate-300">{servers.length}</span> instances
        </div>
        <div className="flex gap-2">
          <button className="px-3 py-1 text-xs font-medium text-slate-400 bg-slate-900 border border-slate-700 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
            Previous
          </button>
          <button className="px-3 py-1 text-xs font-medium text-slate-400 bg-slate-900 border border-slate-700 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default ServerList;
