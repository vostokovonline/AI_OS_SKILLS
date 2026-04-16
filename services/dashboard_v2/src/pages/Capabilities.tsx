/**
 * Capabilities Dashboard - UCB1 Skill Selection
 *
 * Displays:
 * - Capability-to-skill mappings
 * - UCB1 scores and exploration bonuses
 * - Selection statistics
 */
import { useEffect, useState, useCallback } from 'react';
import { apiClient } from '../api/client';
import {
  Zap,
  Target,
  TrendingUp,
  RefreshCw,
  AlertOctagon,
  Award,
  BarChart3,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface CapabilityInfo {
  best_skill: string;
  success_rate: number;
  selection_count: number;
  exploration_bonus?: number;
  ucb_score?: number;
  speed?: number;
  confidence?: number;
}

interface CapabilityStats {
  status: string;
  capabilities: Record<string, CapabilityInfo>;
  total_selections: number;
  exploration_bonus_active: boolean;
  ucb_exploration_constant: number;
  error?: string;
}

export default function Capabilities() {
  const [stats, setStats] = useState<CapabilityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [expandedCaps, setExpandedCaps] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    try {
      const response = await apiClient.get('/semantic/capability/selector/stats');
      const data = response.data || response;
      setStats(data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch capability stats:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const load = async () => { if (mounted) await fetchData(); };
    load();
    const interval = setInterval(load, 10000);
    return () => { mounted = false; clearInterval(interval); };
  }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
  };

  const toggleCapability = (name: string) => {
    setExpandedCaps((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <RefreshCw size={32} className="text-cyan-400 animate-spin mx-auto mb-4" />
          <div className="text-gray-400">Loading Capabilities...</div>
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <AlertOctagon size={48} className="text-red-400 mx-auto mb-4" />
          <div className="text-red-400 font-semibold mb-2">Connection Error</div>
          <div className="text-gray-400 text-sm mb-4">{error}</div>
          <button onClick={handleRefresh} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm transition-colors">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-gray-400">No data available</div>
      </div>
    );
  }

  const capabilities = Object.entries(stats.capabilities || {});
  const sortedCapabilities = capabilities.sort(([, a], [, b]) => (b.selection_count || 0) - (a.selection_count || 0));

  return (
    <div className="h-full overflow-auto bg-gray-900 p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Zap size={28} className="text-cyan-400" />
            <h1 className="text-2xl font-bold text-white">Capabilities</h1>
            <span className="px-2 py-0.5 bg-cyan-900/50 border border-cyan-700 rounded text-xs text-cyan-300">UCB1 Selector</span>
          </div>
          <p className="text-gray-400 text-sm">
            Last updated: {lastUpdate.toLocaleTimeString()} | {capabilities.length} capabilities
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleRefresh} disabled={refreshing} className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-lg text-sm text-gray-300 transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <div className={`px-3 py-1.5 rounded-lg border ${stats.exploration_bonus_active ? 'bg-green-900/30 border-green-700' : 'bg-gray-800/50 border-gray-700'}`}>
            <span className={`text-sm font-medium ${stats.exploration_bonus_active ? 'text-green-300' : 'text-gray-400'}`}>
              Exploration {stats.exploration_bonus_active ? 'ON' : 'OFF'}
            </span>
          </div>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bg-gray-800/80 rounded-xl border border-cyan-700/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target size={18} className="text-cyan-400" />
            <div className="text-xs text-gray-400">Total Selections</div>
          </div>
          <div className="text-xl font-bold text-cyan-300">{stats.total_selections}</div>
          <div className="text-xs text-gray-500 mt-1">All-time decisions</div>
        </div>

        <div className="bg-gray-800/80 rounded-xl border border-purple-700/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Award size={18} className="text-purple-400" />
            <div className="text-xs text-gray-400">Capabilities</div>
          </div>
          <div className="text-xl font-bold text-purple-300">{capabilities.length}</div>
          <div className="text-xs text-gray-500 mt-1">Mapped to skills</div>
        </div>

        <div className="bg-gray-800/80 rounded-xl border border-orange-700/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp size={18} className="text-orange-400" />
            <div className="text-xs text-gray-400">Exploration Constant</div>
          </div>
          <div className="text-xl font-bold text-orange-300">{stats.ucb_exploration_constant.toFixed(2)}</div>
          <div className="text-xs text-gray-500 mt-1">UCB1 parameter c</div>
        </div>
      </div>

      {/* Capabilities Table */}
      {sortedCapabilities.length > 0 ? (
        <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Capability-to-Skill Mappings</h2>
          </div>

          <div className="space-y-2">
            {sortedCapabilities.map(([name, cap]) => (
              <div key={name} className="bg-gray-900/50 rounded-lg overflow-hidden">
                <div
                  className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-900/70 transition-colors"
                  onClick={() => toggleCapability(name)}
                >
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-gray-500">{expandedCaps.has(name) ? <ChevronDown size={16} /> : <ChevronUp size={16} />}</span>
                    <span className="text-sm font-medium text-gray-200">{name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Best Skill</div>
                      <div className="text-xs text-cyan-400 font-medium">{cap.best_skill || 'N/A'}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Success</div>
                      <div className={`text-xs font-medium ${cap.success_rate > 0.7 ? 'text-green-400' : cap.success_rate > 0.4 ? 'text-yellow-400' : 'text-red-400'}`}>
                        {(cap.success_rate * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Count</div>
                      <div className="text-xs text-gray-300">{cap.selection_count}</div>
                    </div>
                  </div>
                </div>

                {expandedCaps.has(name) && (
                  <div className="px-3 pb-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs border-t border-gray-800 pt-3">
                    <div>
                      <div className="text-gray-500 mb-1">Best Skill</div>
                      <div className="text-gray-200 font-mono">{cap.best_skill || 'N/A'}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Success Rate</div>
                      <div className="text-gray-200 font-mono">{(cap.success_rate * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Selection Count</div>
                      <div className="text-gray-200 font-mono">{cap.selection_count}</div>
                    </div>
                    {cap.ucb_score !== undefined && (
                      <div>
                        <div className="text-gray-500 mb-1">UCB Score</div>
                        <div className="text-gray-200 font-mono">{cap.ucb_score.toFixed(3)}</div>
                      </div>
                    )}
                    {cap.exploration_bonus !== undefined && (
                      <div>
                        <div className="text-gray-500 mb-1">Exploration Bonus</div>
                        <div className="text-gray-200 font-mono">{cap.exploration_bonus.toFixed(3)}</div>
                      </div>
                    )}
                    {cap.speed !== undefined && (
                      <div>
                        <div className="text-gray-500 mb-1">Speed</div>
                        <div className="text-gray-200 font-mono">{cap.speed.toFixed(2)}</div>
                      </div>
                    )}
                    {cap.confidence !== undefined && (
                      <div>
                        <div className="text-gray-500 mb-1">Confidence</div>
                        <div className="text-gray-200 font-mono">{(cap.confidence * 100).toFixed(0)}%</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-8 text-center">
          <Zap size={48} className="text-gray-600 mx-auto mb-4" />
          <div className="text-gray-400">No capabilities registered yet</div>
          <div className="text-gray-500 text-sm mt-2">Skills need to be loaded for capability mapping</div>
        </div>
      )}
    </div>
  );
}
