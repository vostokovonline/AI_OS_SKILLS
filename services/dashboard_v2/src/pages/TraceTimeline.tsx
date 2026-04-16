/**
 * Trace Timeline - Execution Trace Visualization
 *
 * Displays:
 * - Goal execution traces with timeline
 * - Skill selections, artifacts produced, evaluations
 * - Search by goal_id
 * - Recent goals with trace availability
 */
import { useEffect, useState, useCallback } from 'react';
import { apiClient } from '../api/client';
import {
  Clock,
  Activity,
  FileText,
  Zap,
  CheckCircle,
  Search,
  RefreshCw,
  Play,
  AlertCircle,
  GitBranch,
  Award,
} from 'lucide-react';

interface TraceStep {
  type: string;
  timestamp: string;
  details: string;
  skill_name?: string;
  artifact_type?: string;
  outcome?: string;
  confidence?: number;
}

interface GoalTrace {
  goal_id: string;
  title: string;
  status: string;
  goal_type: string;
  is_atomic: boolean;
  progress: number;
  created_at: string;
  completed_at: string | null;
  execution_trace: {
    steps: TraceStep[];
    total_steps: number;
    artifacts: any[];
    artifacts_count: number;
  };
  evaluation: any;
}

interface GoalSummary {
  id: string;
  title: string;
  status: string;
  is_atomic: boolean;
  created_at: string;
  has_trace: boolean;
}

function formatTimestamp(ts: string): string {
  if (!ts) return '--';
  return new Date(ts).toLocaleTimeString();
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'done': case 'completed': return 'text-green-400';
    case 'active': case 'running': return 'text-blue-400';
    case 'pending': return 'text-yellow-400';
    case 'blocked': case 'failed': return 'text-red-400';
    default: return 'text-gray-400';
  }
}

function getEventIcon(type: string): React.ElementType {
  if (type.includes('SKILL')) return Zap;
  if (type.includes('ARTIFACT')) return FileText;
  if (type.includes('EVALUAT')) return Award;
  if (type.includes('START')) return Play;
  if (type.includes('TRANSITION')) return GitBranch;
  return Activity;
}

function getEventColor(type: string): string {
  if (type.includes('SKILL')) return 'text-cyan-400';
  if (type.includes('ARTIFACT')) return 'text-orange-400';
  if (type.includes('EVALUAT')) return 'text-purple-400';
  if (type.includes('START')) return 'text-green-400';
  if (type.includes('TRANSITION')) return 'text-blue-400';
  return 'text-gray-400';
}

export default function TraceTimeline() {
  const [searchGoalId, setSearchGoalId] = useState('');
  const [trace, setTrace] = useState<GoalTrace | null>(null);
  const [recentGoals, setRecentGoals] = useState<GoalSummary[]>([]);
  const [traceLoading, setTraceLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [refreshing, setRefreshing] = useState(false);

  const fetchRecentGoals = useCallback(async () => {
    try {
      const response = await apiClient.get('/goals/list');
      const goals = response.data?.goals || response.data || [];
      const summaries: GoalSummary[] = goals.slice(0, 20).map((g: any) => ({
        id: g.id,
        title: g.title,
        status: g.status,
        is_atomic: g.is_atomic,
        created_at: g.created_at,
        has_trace: !!(g.execution_trace && Object.keys(g.execution_trace || {}).length > 0),
      }));
      setRecentGoals(summaries);
    } catch (err) {
      console.error('Failed to fetch recent goals:', err);
    }
  }, []);

  const fetchTrace = useCallback(async (goalId: string) => {
    if (!goalId) return;
    setTraceLoading(true);
    try {
      const response = await apiClient.get(`/control/trace/${goalId}`);
      setTrace(response.data || response);
    } catch (err) {
      console.error('Failed to fetch trace:', err);
      setTrace(null);
    } finally {
      setTraceLoading(false);
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchGoalId.trim()) {
      fetchTrace(searchGoalId.trim());
    }
  };

  useEffect(() => {
    let mounted = true;
    const load = async () => { if (mounted) await fetchRecentGoals(); };
    load();
    const interval = setInterval(load, 15000);
    return () => { mounted = false; clearInterval(interval); };
  }, [fetchRecentGoals]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchRecentGoals();
    if (searchGoalId) await fetchTrace(searchGoalId);
    setLastUpdate(new Date());
    setRefreshing(false);
  };

  return (
    <div className="h-full overflow-auto bg-gray-900 p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Clock size={28} className="text-cyan-400" />
            <h1 className="text-2xl font-bold text-white">Trace Timeline</h1>
            <span className="px-2 py-0.5 bg-cyan-900/50 border border-cyan-700 rounded text-xs text-cyan-300">Execution Traces</span>
          </div>
          <p className="text-gray-400 text-sm">
            Last updated: {lastUpdate.toLocaleTimeString()} | Goal execution event viewer
          </p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing} className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-lg text-sm text-gray-300 transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search by goal ID..."
            value={searchGoalId}
            onChange={(e) => setSearchGoalId(e.target.value)}
            className="w-full bg-gray-800 text-white text-sm rounded-lg pl-10 pr-3 py-2.5 border border-gray-700 focus:border-cyan-500 focus:outline-none"
          />
        </div>
        <button type="submit" className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 rounded-lg text-white text-sm font-medium transition-colors">
          Search
        </button>
      </form>

      {/* Trace Timeline */}
      {traceLoading && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw size={24} className="text-cyan-400 animate-spin mr-3" />
          <span className="text-gray-400">Loading trace...</span>
        </div>
      )}

      {trace && (
        <div className="bg-gray-800/60 rounded-xl border border-cyan-700/50 p-5">
          {/* Trace Header */}
          <div className="flex items-start justify-between mb-4 pb-4 border-b border-gray-700">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-sm font-semibold ${getStatusColor(trace.status)}`}>{trace.title}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(trace.status)} bg-gray-900/50`}>{trace.status}</span>
                {trace.is_atomic && <Zap size={12} className="text-cyan-400" />}
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-400">
                <span>Type: {trace.goal_type}</span>
                <span>Progress: {(trace.progress * 100).toFixed(0)}%</span>
                <span>Steps: {trace.execution_trace?.total_steps || 0}</span>
                <span>Artifacts: {trace.execution_trace?.artifacts_count || 0}</span>
              </div>
            </div>
            <div className="text-right text-xs text-gray-500">
              <div>Created: {formatTimestamp(trace.created_at)}</div>
              {trace.completed_at && <div>Completed: {formatTimestamp(trace.completed_at)}</div>}
            </div>
          </div>

          {/* Timeline Events */}
          {trace.execution_trace?.steps && trace.execution_trace.steps.length > 0 ? (
            <div className="space-y-3">
              {trace.execution_trace.steps.map((step, idx) => {
                const Icon = getEventIcon(step.type);
                return (
                  <div key={idx} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div className={`p-2 rounded-lg bg-gray-900/50 ${getEventColor(step.type)}`}>
                        <Icon size={16} />
                      </div>
                      {idx < trace.execution_trace.steps.length - 1 && (
                        <div className="w-0.5 h-8 bg-gray-700 mt-1" />
                      )}
                    </div>
                    <div className="flex-1 bg-gray-900/30 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-sm font-medium ${getEventColor(step.type)}`}>{step.type}</span>
                        <span className="text-xs text-gray-500">{formatTimestamp(step.timestamp)}</span>
                      </div>
                      {step.details && <div className="text-xs text-gray-400">{step.details}</div>}
                      {step.skill_name && <div className="text-xs text-cyan-400 mt-1">Skill: {step.skill_name}</div>}
                      {step.artifact_type && <div className="text-xs text-orange-400 mt-1">Artifact: {step.artifact_type}</div>}
                      {step.outcome && <div className="text-xs text-gray-400 mt-1">Outcome: {step.outcome}</div>}
                      {step.confidence !== undefined && (
                        <div className="text-xs text-purple-400 mt-1">Confidence: {(step.confidence * 100).toFixed(0)}%</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <AlertCircle size={32} className="mx-auto mb-2 opacity-50" />
              <div>No trace events recorded</div>
            </div>
          )}
        </div>
      )}

      {/* Recent Goals */}
      <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-5">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={20} className="text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Recent Goals</h2>
          <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">{recentGoals.length}</span>
        </div>

        <div className="space-y-2 max-h-96 overflow-y-auto">
          {recentGoals.map((goal) => (
            <div
              key={goal.id}
              className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors hover:bg-gray-800/70 ${
                trace?.goal_id === goal.id ? 'bg-cyan-900/20 border border-cyan-700/50' : 'bg-gray-900/30'
              }`}
              onClick={() => { setSearchGoalId(goal.id); fetchTrace(goal.id); }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-200 truncate">{goal.title}</span>
                  {goal.is_atomic && <Zap size={12} className="text-cyan-400 flex-shrink-0" />}
                </div>
                <div className="text-xs text-gray-500 mt-1 font-mono">{goal.id.slice(0, 12)}...</div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className={`text-xs ${getStatusColor(goal.status)}`}>{goal.status}</span>
                {goal.has_trace ? (
                  <CheckCircle size={14} className="text-green-400" />
                ) : (
                  <AlertCircle size={14} className="text-gray-600" />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
