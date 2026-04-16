/**
 * AI-OS Control Center v2.0 - Real-time System Observability
 *
 * Displays:
 * - System health (goals, LLM usage, thinking depth)
 * - Goal economy (pending, running, completed, success rate, STUCK goals)
 * - Execution metrics (skills, artifacts, throughput)
 * - Cognition metrics (fast vs deep reasoning)
 * - v7.2 TS Router & Policy Learning status
 * - Strategic goals including "Оставить след в истории человечества"
 * - System alerts and stuck goal detection
 */
import { useEffect, useState, useCallback } from 'react';
import { apiClient } from '../api/client';
import {
  AlertTriangle,
  Activity,
  Brain,
  Cpu,
  Target,
  TrendingUp,
  CheckCircle,
  XCircle,
  Zap,
  BarChart3,
  Layers,
  GitBranch,
  Shield,
  Award,
  AlertOctagon,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

// ========================
// TYPE DEFINITIONS
// ========================

interface ControlCenterData {
  system: {
    llm_calls: number;
    llm_tokens: number;
    failure_rate: number;
  };
  goals: {
    running: number;
    completed: number;
    success_rate: number;
    throughput_per_min: number;
  };
  execution: {
    skills_invoked: number;
    artifacts_produced: number;
    throughput: number;
  };
  cognition: {
    fast_percentage: number;
    deep_percentage: number;
    avg_tokens: number;
  };
  top_skills: SkillMetric[];
}

interface SkillMetric {
  skill: string;
  usage: number;
  success_rate: number;
  failures?: number;
}

interface GoalDetail {
  id: string;
  title: string;
  description: string;
  status: string;
  goal_type: string;
  progress: number;
  is_atomic: boolean;
  depth_level: number;
  parent_id: string | null;
  created_at: string;
  completed_at: string | null;
  execution_trace: any;
  children_count?: number;
  done_children_count?: number;
}

interface GoalStats {
  total: number;
  pending: number;
  active: number;
  done: number;
  blocked: number;
  failed: number;
  frozen: number;
  cancelled: number;
}

interface StuckGoal {
  id: string;
  title: string;
  status: string;
  progress: number;
  age_days: number;
  depth_level: number;
  is_atomic: boolean;
  children_count: number;
  has_execution_trace: boolean;
}

interface RouterStatus {
  version: string;
  ts_strategy: string;
  policy_bias_active: boolean;
  confidence_threshold: number;
  decay_factor: number;
  context_signatures: number;
  exploration_rate: number;
}

interface StrategicGoal {
  id: string;
  title: string;
  description: string;
  status: string;
  progress: number;
  goal_type: string;
  created_at: string;
  is_core: boolean;
}

// ========================
// UTILITY FUNCTIONS
// ========================

function formatAge(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  if (diffDays < 1) {
    const diffHours = diffMs / (1000 * 60 * 60);
    return `${diffHours.toFixed(1)}h`;
  }
  return `${diffDays.toFixed(1)}d`;
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'done':
    case 'completed':
      return 'text-green-400';
    case 'active':
    case 'running':
      return 'text-blue-400';
    case 'pending':
      return 'text-yellow-400';
    case 'blocked':
    case 'failed':
      return 'text-red-400';
    case 'frozen':
      return 'text-gray-400';
    default:
      return 'text-gray-300';
  }
}

function getStatusBg(status: string): string {
  switch (status) {
    case 'done':
    case 'completed':
      return 'bg-green-900/30 border-green-700';
    case 'active':
    case 'running':
      return 'bg-blue-900/30 border-blue-700';
    case 'pending':
      return 'bg-yellow-900/30 border-yellow-700';
    case 'blocked':
    case 'failed':
      return 'bg-red-900/30 border-red-700';
    case 'frozen':
      return 'bg-gray-800/50 border-gray-600';
    default:
      return 'bg-gray-800/50 border-gray-700';
  }
}

function getProgressColor(progress: number): string {
  if (progress >= 0.8) return 'bg-green-500';
  if (progress >= 0.5) return 'bg-blue-500';
  if (progress >= 0.2) return 'bg-yellow-500';
  return 'bg-red-500';
}

// ========================
// METRIC CARD COMPONENT
// ========================

interface MetricCardProps {
  title: string;
  icon: React.ElementType;
  color: 'blue' | 'green' | 'purple' | 'orange' | 'red' | 'cyan' | 'yellow';
  metrics: Array<{ label: string; value: string; trend?: 'up' | 'down' | 'stable' }>;
  footer?: React.ReactNode;
}

function MetricCard({ title, icon: Icon, color, metrics, footer }: MetricCardProps) {
  const [expanded, setExpanded] = useState(false);

  const colorMap = {
    blue: { border: 'border-blue-500', icon: 'text-blue-400', bg: 'bg-blue-900/20' },
    green: { border: 'border-green-500', icon: 'text-green-400', bg: 'bg-green-900/20' },
    purple: { border: 'border-purple-500', icon: 'text-purple-400', bg: 'bg-purple-900/20' },
    orange: { border: 'border-orange-500', icon: 'text-orange-400', bg: 'bg-orange-900/20' },
    red: { border: 'border-red-500', icon: 'text-red-400', bg: 'bg-red-900/20' },
    cyan: { border: 'border-cyan-500', icon: 'text-cyan-400', bg: 'bg-cyan-900/20' },
    yellow: { border: 'border-yellow-500', icon: 'text-yellow-400', bg: 'bg-yellow-900/20' },
  };

  const colors = colorMap[color];

  return (
    <div className={`bg-gray-800/80 rounded-xl border ${colors.border} overflow-hidden transition-all hover:shadow-lg hover:shadow-${color}-500/10`}>
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Icon size={18} className={colors.icon} />
            <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wide">{title}</h3>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>

        <div className="space-y-2">
          {metrics.slice(0, expanded ? undefined : 3).map((metric, idx) => (
            <div key={idx} className="flex justify-between items-center py-1.5 border-b border-gray-700/50 last:border-0">
              <span className="text-xs text-gray-400">{metric.label}</span>
              <div className="flex items-center gap-1">
                <span className="text-sm font-semibold text-gray-100">{metric.value}</span>
                {metric.trend && (
                  <TrendingUp size={12} className={metric.trend === 'up' ? 'text-green-400' : metric.trend === 'down' ? 'text-red-400' : 'text-gray-500'} />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {footer && (
        <div className={`px-4 py-2 ${colors.bg} border-t ${colors.border}`}>
          {footer}
        </div>
      )}
    </div>
  );
}

// ========================
// MAIN COMPONENT
// ========================

export default function ControlCenter() {
  const [metrics, setMetrics] = useState<ControlCenterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Extended data
  const [goalStats, setGoalStats] = useState<GoalStats | null>(null);
  const [stuckGoals, setStuckGoals] = useState<StuckGoal[]>([]);
  const [strategicGoals, setStrategicGoals] = useState<StrategicGoal[]>([]);
  const [routerStatus, setRouterStatus] = useState<RouterStatus | null>(null);
  const [policyStatus, setPolicyStatus] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      // Core metrics
      const [overviewRes, goalsListRes, routerRes, policyRes] = await Promise.allSettled([
        apiClient.get('/control/overview'),
        apiClient.get('/goals/list'),
        apiClient.get('/semantic/router/status'),
        apiClient.get('/semantic/policy/status'),
      ]);

      if (overviewRes.status === 'fulfilled') {
        setMetrics(overviewRes.value.data || overviewRes.value);
      }

      if (goalsListRes.status === 'fulfilled') {
        const goalsData = goalsListRes.value.data || goalsListRes.value;
        const goals: GoalDetail[] = Array.isArray(goalsData) ? goalsData : goalsData.goals || [];

        // Calculate goal stats
        const stats: GoalStats = {
          total: goals.length,
          pending: goals.filter((g: GoalDetail) => g.status === 'pending').length,
          active: goals.filter((g: GoalDetail) => g.status === 'active').length,
          done: goals.filter((g: GoalDetail) => g.status === 'done').length,
          blocked: goals.filter((g: GoalDetail) => g.status === 'blocked').length,
          failed: goals.filter((g: GoalDetail) => g.status === 'failed').length,
          frozen: goals.filter((g: GoalDetail) => g.status === 'frozen').length,
          cancelled: goals.filter((g: GoalDetail) => g.status === 'cancelled').length,
        };
        setGoalStats(stats);

        // Detect stuck goals (pending/active > 1 day with no progress)
        const now = new Date();
        const stuck = goals
          .filter((g: GoalDetail) => {
            const ageMs = now.getTime() - new Date(g.created_at).getTime();
            const ageDays = ageMs / (1000 * 60 * 60 * 24);
            return (
              (g.status === 'pending' || g.status === 'active') &&
              g.progress === 0 &&
              ageDays > 0.5 &&
              !g.is_atomic
            );
          })
          .map((g: GoalDetail) => {
            const ageMs = now.getTime() - new Date(g.created_at).getTime();
            const ageDays = ageMs / (1000 * 60 * 60 * 24);
            return {
              id: g.id,
              title: g.title,
              status: g.status,
              progress: g.progress,
              age_days: ageDays,
              depth_level: g.depth_level,
              is_atomic: g.is_atomic,
              children_count: g.children_count || 0,
              has_execution_trace: !!(g.execution_trace && Object.keys(g.execution_trace).length > 0),
            };
          })
          .sort((a: StuckGoal, b: StuckGoal) => b.age_days - a.age_days)
          .slice(0, 20);
        setStuckGoals(stuck);

        // Strategic goals (core mission goals)
        const strategic = goals
          .filter((g: GoalDetail) =>
            g.title.toLowerCase().includes('оставить след') ||
            g.title.toLowerCase().includes('leave a mark') ||
            g.goal_type === 'directional' ||
            g.depth_level === 0
          )
          .map((g: GoalDetail) => ({
            id: g.id,
            title: g.title,
            description: g.description,
            status: g.status,
            progress: g.progress,
            goal_type: g.goal_type,
            created_at: g.created_at,
            is_core: g.depth_level === 0 || g.title.toLowerCase().includes('оставить след'),
          }))
          .sort((a: StrategicGoal, b: StrategicGoal) => (b.is_core ? 1 : 0) - (a.is_core ? 1 : 0));
        setStrategicGoals(strategic);
      }

      if (routerRes.status === 'fulfilled') {
        const routerData = routerRes.value.data || routerRes.value;
        setRouterStatus({
          version: routerData.version || 'v7.2',
          ts_strategy: routerData.current_strategy || 'thompson_sampling',
          policy_bias_active: routerData.policy_bias_enabled ?? true,
          confidence_threshold: routerData.confidence_threshold ?? 0.3,
          decay_factor: routerData.decay_factor ?? 0.995,
          context_signatures: routerData.context_signatures ?? 0,
          exploration_rate: routerData.exploration_rate ?? 0.1,
        });
      }

      if (policyRes.status === 'fulfilled') {
        setPolicyStatus(policyRes.value.data || policyRes.value);
      }

      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch control center data:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      if (mounted) {
        await fetchData();
      }
    };

    load();
    const interval = setInterval(load, 10000); // Poll every 10s

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <RefreshCw size={32} className="text-blue-400 animate-spin mx-auto mb-4" />
          <div className="text-gray-400">Loading Control Center...</div>
        </div>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <AlertOctagon size={48} className="text-red-400 mx-auto mb-4" />
          <div className="text-red-400 font-semibold mb-2">Connection Error</div>
          <div className="text-gray-400 text-sm mb-4">{error}</div>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-gray-400">No metrics available</div>
      </div>
    );
  }

  // Calculate derived metrics
  const totalGoals = goalStats?.total || 0;
  const stuckGoalsCount = stuckGoals.length;
  const pendingGoals = goalStats?.pending || 0;
  const activeGoals = goalStats?.active || 0;
  const doneGoals = goalStats?.done || 0;

  const stuckPercentage = totalGoals > 0 ? (stuckGoalsCount / totalGoals * 100) : 0;
  const completionRate = metrics.goals.success_rate * 100;

  return (
    <div className="h-full overflow-auto bg-gray-900 p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Activity size={28} className="text-blue-400" />
            <h1 className="text-2xl font-bold text-white">AI-OS Control Center</h1>
            <span className="px-2 py-0.5 bg-blue-900/50 border border-blue-700 rounded text-xs text-blue-300">v2.0</span>
          </div>
          <p className="text-gray-400 text-sm">
            Last updated: {lastUpdate.toLocaleTimeString()} | Total Goals: {totalGoals}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-lg text-sm text-gray-300 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-green-900/30 border border-green-700 rounded-lg">
            <div className="h-2.5 w-2.5 bg-green-400 rounded-full animate-pulse" />
            <span className="text-sm text-green-300 font-medium">Live</span>
          </div>
        </div>
      </div>

      {/* ALERTS */}
      {stuckGoalsCount > 0 && (
        <div className="bg-red-900/20 border border-red-700 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-red-300 font-semibold">Stuck Goals Detected</span>
                <span className="px-2 py-0.5 bg-red-800 rounded text-xs text-red-200">{stuckGoalsCount} goals</span>
              </div>
              <p className="text-red-400/80 text-sm">
                {stuckGoalsCount} goals are stuck (pending/active with 0 progress). 
                Root cause: Non-atomic goals not auto-decomposing. Parent progress not aggregating.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Core Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* System Health */}
        <MetricCard
          title="System Health"
          icon={Cpu}
          color="blue"
          metrics={[
            { label: 'LLM Calls', value: metrics.system.llm_calls.toLocaleString(), trend: 'up' },
            { label: 'LLM Tokens', value: metrics.system.llm_tokens.toLocaleString() },
            { label: 'Failure Rate', value: `${(metrics.system.failure_rate * 100).toFixed(1)}%`, trend: metrics.system.failure_rate < 0.1 ? 'stable' : 'down' },
            { label: 'Throughput', value: `${metrics.goals.throughput_per_min.toFixed(2)}/min` },
          ]}
        />

        {/* Goal Economy */}
        <MetricCard
          title="Goal Economy"
          icon={Target}
          color={stuckGoalsCount > 5 ? 'red' : 'green'}
          metrics={[
            { label: 'Pending', value: pendingGoals.toString(), trend: pendingGoals > 10 ? 'down' : 'stable' },
            { label: 'Active', value: activeGoals.toString() },
            { label: 'Completed', value: doneGoals.toString(), trend: 'up' },
            { label: 'Success Rate', value: `${completionRate.toFixed(1)}%` },
            { label: 'Stuck Goals', value: `${stuckGoalsCount} (${stuckPercentage.toFixed(1)}%)`, trend: stuckGoalsCount > 0 ? 'down' : 'stable' },
          ]}
          footer={
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400">Blocked: {goalStats?.blocked || 0}</span>
              <span className="text-gray-400">Failed: {goalStats?.failed || 0}</span>
            </div>
          }
        />

        {/* Execution */}
        <MetricCard
          title="Execution"
          icon={Zap}
          color="purple"
          metrics={[
            { label: 'Skills Invoked', value: metrics.execution.skills_invoked.toLocaleString(), trend: 'up' },
            { label: 'Artifacts', value: metrics.execution.artifacts_produced.toLocaleString() },
            { label: 'Throughput', value: `${metrics.execution.throughput.toFixed(1)}/min` },
          ]}
        />

        {/* Cognition */}
        <MetricCard
          title="Thinking Depth"
          icon={Brain}
          color="orange"
          metrics={[
            { label: 'Fast Mode', value: `${metrics.cognition.fast_percentage.toFixed(0)}%` },
            { label: 'Deep Reasoning', value: `${metrics.cognition.deep_percentage.toFixed(0)}%` },
            { label: 'Avg Tokens', value: metrics.cognition.avg_tokens.toFixed(0) },
          ]}
          footer={
            <div className="flex h-2 rounded-full overflow-hidden bg-gray-700">
              <div
                className="bg-green-500 transition-all"
                style={{ width: `${metrics.cognition.fast_percentage}%` }}
              />
              <div
                className="bg-blue-500 transition-all"
                style={{ width: `${metrics.cognition.deep_percentage}%` }}
              />
            </div>
          }
        />
      </div>

      {/* v7.2 Router & Policy Status */}
      {routerStatus && (
        <div className="bg-gray-800/60 rounded-xl border border-purple-700/50 p-5">
          <div className="flex items-center gap-2 mb-4">
            <GitBranch size={20} className="text-purple-400" />
            <h2 className="text-lg font-semibold text-white">v7.2 Adaptive Router Status</h2>
            <span className="px-2 py-0.5 bg-purple-900/50 border border-purple-600 rounded text-xs text-purple-300">{routerStatus.version}</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-900/50 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Strategy</div>
              <div className="text-sm font-semibold text-purple-300">Thompson Sampling</div>
              <div className="text-xs text-gray-500 mt-1">3 arms: cheap/smart/loop</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Policy Bias</div>
              <div className={`text-sm font-semibold ${routerStatus.policy_bias_active ? 'text-green-400' : 'text-red-400'}`}>
                {routerStatus.policy_bias_active ? 'ACTIVE' : 'INACTIVE'}
              </div>
              <div className="text-xs text-gray-500 mt-1">Weight: 0.3</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Confidence</div>
              <div className="text-sm font-semibold text-cyan-300">{(routerStatus.confidence_threshold * 100).toFixed(0)}%</div>
              <div className="text-xs text-gray-500 mt-1">Cold start threshold</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Context Sigs</div>
              <div className="text-sm font-semibold text-yellow-300">{routerStatus.context_signatures}</div>
              <div className="text-xs text-gray-500 mt-1">Discrete encoding</div>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-4">
            <div className="bg-gray-900/50 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Decay Factor</div>
              <div className="text-sm font-semibold text-orange-300">{routerStatus.decay_factor}</div>
              <div className="text-xs text-gray-500 mt-1">Prevents overconfidence</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Exploration Rate</div>
              <div className="text-sm font-semibold text-blue-300">{(routerStatus.exploration_rate * 100).toFixed(1)}%</div>
              <div className="text-xs text-gray-500 mt-1">TS variance</div>
            </div>
            {policyStatus && (
              <div className="bg-gray-900/50 rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">Policy Q-Entries</div>
                <div className="text-sm font-semibold text-green-300">{policyStatus.q_table_size || policyStatus.total_entries || 0}</div>
                <div className="text-xs text-gray-500 mt-1">Learned patterns</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Strategic Goals - "Оставить след в истории человечества" */}
      {strategicGoals.length > 0 && (
        <div className="bg-gray-800/60 rounded-xl border border-yellow-700/50 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Award size={20} className="text-yellow-400" />
            <h2 className="text-lg font-semibold text-white">Strategic Mission Goals</h2>
          </div>

          <div className="space-y-3">
            {strategicGoals.map((goal) => (
              <div
                key={goal.id}
                className={`rounded-lg p-4 border ${getStatusBg(goal.status)} ${goal.is_core ? 'ring-2 ring-yellow-500/30' : ''}`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {goal.is_core && <Award size={16} className="text-yellow-400" />}
                    <span className={`font-medium ${getStatusColor(goal.status)}`}>{goal.title}</span>
                    {goal.is_core && (
                      <span className="px-1.5 py-0.5 bg-yellow-900/50 border border-yellow-600 rounded text-[10px] text-yellow-300 uppercase">Core</span>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(goal.status)} bg-gray-900/50`}>
                    {goal.status}
                  </span>
                </div>

                {goal.description && (
                  <p className="text-gray-400 text-sm mb-3 line-clamp-2">{goal.description}</p>
                )}

                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>Type: {goal.goal_type}</span>
                  <span>Progress:</span>
                  <div className="flex-1 max-w-[200px]">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${getProgressColor(goal.progress)} transition-all`}
                          style={{ width: `${goal.progress * 100}%` }}
                        />
                      </div>
                      <span className="text-gray-300 w-10 text-right">{(goal.progress * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <span>Age: {formatAge(goal.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Skills */}
      {metrics.top_skills.length > 0 && (
        <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Layers size={20} className="text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Top Skills</h2>
          </div>

          <div className="space-y-2">
            {metrics.top_skills.map((skill, index) => (
              <div
                key={skill.skill}
                className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-900/40 hover:bg-gray-900/60 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-gray-500 text-sm w-6 font-mono">#{index + 1}</span>
                  <span className="text-sm font-medium text-gray-200">{skill.skill}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-400">Usage: {skill.usage}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${skill.success_rate > 0.8 ? 'bg-green-500' : skill.success_rate > 0.6 ? 'bg-yellow-500' : 'bg-red-500'}`}
                        style={{ width: `${skill.success_rate * 100}%` }}
                      />
                    </div>
                    <span className={`font-medium w-12 text-right ${
                      skill.success_rate > 0.8 ? 'text-green-400' :
                      skill.success_rate > 0.6 ? 'text-yellow-400' :
                      'text-red-400'
                    }`}>
                      {Math.round(skill.success_rate * 100)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stuck Goals Detail */}
      {stuckGoals.length > 0 && (
        <div className="bg-gray-800/60 rounded-xl border border-red-700/50 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle size={20} className="text-red-400" />
              <h2 className="text-lg font-semibold text-white">Stuck Goals ({stuckGoals.length})</h2>
            </div>
            <span className="text-xs text-gray-400">
              Non-atomic goals without auto-decomposition
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-2 px-3 text-gray-400 font-medium">Title</th>
                  <th className="text-left py-2 px-3 text-gray-400 font-medium">Status</th>
                  <th className="text-left py-2 px-3 text-gray-400 font-medium">Progress</th>
                  <th className="text-left py-2 px-3 text-gray-400 font-medium">Age</th>
                  <th className="text-left py-2 px-3 text-gray-400 font-medium">Depth</th>
                  <th className="text-left py-2 px-3 text-gray-400 font-medium">Children</th>
                  <th className="text-left py-2 px-3 text-gray-400 font-medium">Trace</th>
                </tr>
              </thead>
              <tbody>
                {stuckGoals.slice(0, 10).map((goal) => (
                  <tr key={goal.id} className="border-b border-gray-800 hover:bg-gray-900/30 transition-colors">
                    <td className="py-2 px-3 text-gray-200 max-w-[250px] truncate" title={goal.title}>
                      {goal.title}
                    </td>
                    <td className="py-2 px-3">
                      <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(goal.status)} bg-gray-900/50`}>
                        {goal.status}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                          <div className={`h-full ${getProgressColor(goal.progress)}`} style={{ width: `${goal.progress * 100}%` }} />
                        </div>
                        <span className="text-gray-400 text-xs">0%</span>
                      </div>
                    </td>
                    <td className="py-2 px-3 text-gray-400">{goal.age_days.toFixed(1)}d</td>
                    <td className="py-2 px-3 text-gray-400">L{goal.depth_level}</td>
                    <td className="py-2 px-3 text-gray-400">{goal.children_count}</td>
                    <td className="py-2 px-3">
                      {goal.has_execution_trace ? (
                        <CheckCircle size={14} className="text-green-400" />
                      ) : (
                        <XCircle size={14} className="text-red-400" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {stuckGoals.length > 10 && (
            <div className="text-center text-xs text-gray-500 mt-3">
              Showing 10 of {stuckGoals.length} stuck goals
            </div>
          )}
        </div>
      )}

      {/* Thinking Mode Distribution Bar */}
      <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-5">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 size={20} className="text-orange-400" />
          <h2 className="text-lg font-semibold text-white">Thinking Mode Distribution</h2>
        </div>
        <div className="flex h-10 rounded-lg overflow-hidden bg-gray-700">
          <div
            className="bg-gradient-to-r from-green-600 to-green-500 flex items-center justify-center text-white text-sm font-medium transition-all"
            style={{ width: `${Math.max(metrics.cognition.fast_percentage, 5)}%` }}
          >
            {metrics.cognition.fast_percentage >= 15 && `Fast ${metrics.cognition.fast_percentage.toFixed(0)}%`}
          </div>
          <div
            className="bg-gradient-to-r from-blue-600 to-blue-500 flex items-center justify-center text-white text-sm font-medium transition-all"
            style={{ width: `${Math.max(metrics.cognition.deep_percentage, 5)}%` }}
          >
            {metrics.cognition.deep_percentage >= 15 && `Deep ${metrics.cognition.deep_percentage.toFixed(0)}%`}
          </div>
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span>Fast: System 1 — quick decisions, pattern matching</span>
          <span>Deep: System 2 — multi-step reasoning, planning</span>
        </div>
      </div>

      {/* Goal Economy Pie */}
      {goalStats && goalStats.total > 0 && (
        <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Shield size={20} className="text-green-400" />
            <h2 className="text-lg font-semibold text-white">Goal Status Distribution</h2>
          </div>

          <div className="flex h-8 rounded-lg overflow-hidden bg-gray-700">
            {goalStats.done > 0 && (
              <div className="bg-green-500 flex items-center justify-center text-white text-xs font-medium" style={{ width: `${(goalStats.done / goalStats.total) * 100}%` }}>
                Done {goalStats.done}
              </div>
            )}
            {goalStats.active > 0 && (
              <div className="bg-blue-500 flex items-center justify-center text-white text-xs font-medium" style={{ width: `${(goalStats.active / goalStats.total) * 100}%` }}>
                Active {goalStats.active}
              </div>
            )}
            {goalStats.pending > 0 && (
              <div className="bg-yellow-500 flex items-center justify-center text-white text-xs font-medium" style={{ width: `${(goalStats.pending / goalStats.total) * 100}%` }}>
                Pending {goalStats.pending}
              </div>
            )}
            {goalStats.blocked > 0 && (
              <div className="bg-orange-500 flex items-center justify-center text-white text-xs font-medium" style={{ width: `${(goalStats.blocked / goalStats.total) * 100}%` }}>
                Blocked {goalStats.blocked}
              </div>
            )}
            {goalStats.failed > 0 && (
              <div className="bg-red-500 flex items-center justify-center text-white text-xs font-medium" style={{ width: `${(goalStats.failed / goalStats.total) * 100}%` }}>
                Failed {goalStats.failed}
              </div>
            )}
            {goalStats.frozen > 0 && (
              <div className="bg-gray-500 flex items-center justify-center text-white text-xs font-medium" style={{ width: `${(goalStats.frozen / goalStats.total) * 100}%` }}>
                Frozen {goalStats.frozen}
              </div>
            )}
          </div>

          <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mt-4">
            {[
              { label: 'Done', count: goalStats.done, color: 'text-green-400' },
              { label: 'Active', count: goalStats.active, color: 'text-blue-400' },
              { label: 'Pending', count: goalStats.pending, color: 'text-yellow-400' },
              { label: 'Blocked', count: goalStats.blocked, color: 'text-orange-400' },
              { label: 'Failed', count: goalStats.failed, color: 'text-red-400' },
              { label: 'Frozen', count: goalStats.frozen, color: 'text-gray-400' },
            ].map((item) => (
              <div key={item.label} className="text-center">
                <div className={`text-2xl font-bold ${item.color}`}>{item.count}</div>
                <div className="text-xs text-gray-500">{item.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
