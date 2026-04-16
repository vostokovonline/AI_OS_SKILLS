/**
 * Plan Memory Dashboard - Hierarchical Multi-Armed Bandit
 *
 * Displays:
 * - Current mode (explore/probe/exploit)
 * - Locked strategy
 * - Strategy scores (abstract & concrete)
 * - Evolution state
 * - Artifact cache stats
 */
import { useEffect, useState, useCallback } from 'react';
import { apiClient } from '../api/client';
import {
  Brain,
  Target,
  Zap,
  Activity,
  Database,
  RefreshCw,
  AlertOctagon,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  Layers,
  Award,
} from 'lucide-react';

interface PlanMemoryStatus {
  status: string;
  mode: string;
  locked_strategy: string | null;
  total_strategies: number;
  artifact_cache_size: number;
  evolution_count: number;
  total_selections: number;
  error?: string;
}

interface StrategyInfo {
  name: string;
  alpha: number;
  beta: number;
  success_rate: number;
  selections: number;
  level: 'abstract' | 'concrete';
}

function getModeColor(mode: string): string {
  switch (mode.toLowerCase()) {
    case 'explore': return 'text-blue-400';
    case 'probe': return 'text-yellow-400';
    case 'exploit': return 'text-green-400';
    default: return 'text-gray-400';
  }
}

function getModeBg(mode: string): string {
  switch (mode.toLowerCase()) {
    case 'explore': return 'bg-blue-900/30 border-blue-700';
    case 'probe': return 'bg-yellow-900/30 border-yellow-700';
    case 'exploit': return 'bg-green-900/30 border-green-700';
    default: return 'bg-gray-800/50 border-gray-700';
  }
}

export default function PlanMemory() {
  const [status, setStatus] = useState<PlanMemoryStatus | null>(null);
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, strategiesRes] = await Promise.allSettled([
        apiClient.get('/semantic/plan-memory/status'),
        apiClient.get('/semantic/plan-memory/strategies'),
      ]);

      if (statusRes.status === 'fulfilled') {
        const data = statusRes.value.data || statusRes.value;
        setStatus(data);
      }

      if (strategiesRes.status === 'fulfilled') {
        const data = strategiesRes.value.data || strategiesRes.value;
        setStrategies(data.strategies || []);
      }

      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch plan memory data:', err);
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

  const toggleStrategy = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <RefreshCw size={32} className="text-purple-400 animate-spin mx-auto mb-4" />
          <div className="text-gray-400">Loading Plan Memory...</div>
        </div>
      </div>
    );
  }

  if (error && !status) {
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

  if (!status) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-gray-400">No data available</div>
      </div>
    );
  }

  const abstractStrategies = strategies.filter((s) => s.level === 'abstract');
  const concreteStrategies = strategies.filter((s) => s.level === 'concrete');

  return (
    <div className="h-full overflow-auto bg-gray-900 p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Brain size={28} className="text-purple-400" />
            <h1 className="text-2xl font-bold text-white">Plan Memory</h1>
            <span className="px-2 py-0.5 bg-purple-900/50 border border-purple-700 rounded text-xs text-purple-300">Hierarchical MAB</span>
          </div>
          <p className="text-gray-400 text-sm">
            Last updated: {lastUpdate.toLocaleTimeString()} | Mode: <span className={getModeColor(status.mode)}>{status.mode}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleRefresh} disabled={refreshing} className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-lg text-sm text-gray-300 transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <div className={`px-3 py-1.5 rounded-lg border ${getModeBg(status.mode)}`}>
            <span className={`text-sm font-medium ${getModeColor(status.mode)}`}>{status.mode.toUpperCase()}</span>
          </div>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800/80 rounded-xl border border-purple-700/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target size={18} className="text-purple-400" />
            <div className="text-xs text-gray-400">Mode</div>
          </div>
          <div className={`text-xl font-bold ${getModeColor(status.mode)}`}>{status.mode}</div>
          <div className="text-xs text-gray-500 mt-1">
            {status.locked_strategy ? `Locked: ${status.locked_strategy}` : 'No lock'}
          </div>
        </div>

        <div className="bg-gray-800/80 rounded-xl border border-blue-700/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Layers size={18} className="text-blue-400" />
            <div className="text-xs text-gray-400">Strategies</div>
          </div>
          <div className="text-xl font-bold text-blue-300">{status.total_strategies}</div>
          <div className="text-xs text-gray-500 mt-1">
            {abstractStrategies.length} abstract, {concreteStrategies.length} concrete
          </div>
        </div>

        <div className="bg-gray-800/80 rounded-xl border border-green-700/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Database size={18} className="text-green-400" />
            <div className="text-xs text-gray-400">Artifact Cache</div>
          </div>
          <div className="text-xl font-bold text-green-300">{status.artifact_cache_size}</div>
          <div className="text-xs text-gray-500 mt-1">Cached artifacts</div>
        </div>

        <div className="bg-gray-800/80 rounded-xl border border-orange-700/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity size={18} className="text-orange-400" />
            <div className="text-xs text-gray-400">Selections</div>
          </div>
          <div className="text-xl font-bold text-orange-300">{status.total_selections}</div>
          <div className="text-xs text-gray-500 mt-1">{status.evolution_count} evolutions</div>
        </div>
      </div>

      {/* Abstract Strategies */}
      {abstractStrategies.length > 0 && (
        <div className="bg-gray-800/60 rounded-xl border border-purple-700/50 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Award size={20} className="text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Abstract Strategies</h2>
            <span className="px-2 py-0.5 bg-purple-900/50 border border-purple-600 rounded text-xs text-purple-300">{abstractStrategies.length}</span>
          </div>

          <div className="space-y-2">
            {abstractStrategies.map((s) => (
              <div key={s.name} className="bg-gray-900/50 rounded-lg overflow-hidden">
                <div
                  className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-900/70 transition-colors"
                  onClick={() => toggleStrategy(s.name)}
                >
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-gray-500">{expanded.has(s.name) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
                    <span className="text-sm font-medium text-gray-200">{s.name}</span>
                    <span className="text-xs text-purple-400 px-2 py-0.5 bg-purple-900/30 rounded">abstract</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-1">
                      <TrendingUp size={14} className={s.success_rate > 0.7 ? 'text-green-400' : s.success_rate > 0.4 ? 'text-yellow-400' : 'text-red-400'} />
                      <span className={s.success_rate > 0.7 ? 'text-green-400' : s.success_rate > 0.4 ? 'text-yellow-400' : 'text-red-400'}>
                        {(s.success_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                    <span className="text-gray-400">{s.selections} selections</span>
                  </div>
                </div>

                {expanded.has(s.name) && (
                  <div className="px-3 pb-3 grid grid-cols-4 gap-3 text-xs border-t border-gray-800 pt-3">
                    <div>
                      <div className="text-gray-500 mb-1">Alpha</div>
                      <div className="text-gray-200 font-mono">{s.alpha.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Beta</div>
                      <div className="text-gray-200 font-mono">{s.beta.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Success Rate</div>
                      <div className="text-gray-200 font-mono">{(s.success_rate * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Total Selections</div>
                      <div className="text-gray-200 font-mono">{s.selections}</div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Concrete Strategies */}
      {concreteStrategies.length > 0 && (
        <div className="bg-gray-800/60 rounded-xl border border-blue-700/50 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap size={20} className="text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Concrete Strategies</h2>
            <span className="px-2 py-0.5 bg-blue-900/50 border border-blue-600 rounded text-xs text-blue-300">{concreteStrategies.length}</span>
          </div>

          <div className="space-y-2">
            {concreteStrategies.map((s) => (
              <div key={s.name} className="bg-gray-900/50 rounded-lg overflow-hidden">
                <div
                  className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-900/70 transition-colors"
                  onClick={() => toggleStrategy(s.name)}
                >
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-gray-500">{expanded.has(s.name) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
                    <span className="text-sm font-medium text-gray-200">{s.name}</span>
                    <span className="text-xs text-blue-400 px-2 py-0.5 bg-blue-900/30 rounded">concrete</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-1">
                      <TrendingUp size={14} className={s.success_rate > 0.7 ? 'text-green-400' : s.success_rate > 0.4 ? 'text-yellow-400' : 'text-red-400'} />
                      <span className={s.success_rate > 0.7 ? 'text-green-400' : s.success_rate > 0.4 ? 'text-yellow-400' : 'text-red-400'}>
                        {(s.success_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                    <span className="text-gray-400">{s.selections} selections</span>
                  </div>
                </div>

                {expanded.has(s.name) && (
                  <div className="px-3 pb-3 grid grid-cols-4 gap-3 text-xs border-t border-gray-800 pt-3">
                    <div>
                      <div className="text-gray-500 mb-1">Alpha</div>
                      <div className="text-gray-200 font-mono">{s.alpha.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Beta</div>
                      <div className="text-gray-200 font-mono">{s.beta.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Success Rate</div>
                      <div className="text-gray-200 font-mono">{(s.success_rate * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-gray-500 mb-1">Total Selections</div>
                      <div className="text-gray-200 font-mono">{s.selections}</div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {strategies.length === 0 && (
        <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-8 text-center">
          <Brain size={48} className="text-gray-600 mx-auto mb-4" />
          <div className="text-gray-400">No strategies learned yet</div>
          <div className="text-gray-500 text-sm mt-2">System is in exploration mode</div>
        </div>
      )}
    </div>
  );
}
