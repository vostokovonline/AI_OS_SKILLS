/**
 * AI-OS Goals Page - Goal Hierarchy & Execution Tracking
 *
 * Features:
 * - Goal tree visualization (hierarchical L0-L3)
 * - Stuck goals detection and analysis
 * - Strategic goals tracking ("Оставить след в истории человечества")
 * - Goal execution trace viewer
 * - Bulk actions (decompose, execute, freeze)
 * - Goal status distribution
 */
import { useEffect, useState, useCallback } from 'react';
import { apiClient } from '../api/client';
import {
  Target,
  GitBranch,
  AlertTriangle,
  Play,
  Pause,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  Layers,
  Clock,
  CheckCircle,
  XCircle,
  PauseCircle,
  AlertCircle,
  BarChart3,
  Search,
  Filter,
  Activity,
  Zap,
  Eye,
  Terminal,
} from 'lucide-react';

// ========================
// TYPES
// ========================

interface Goal {
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
  evaluation_result: any;
  children?: Goal[];
  children_count?: number;
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
  by_type: Record<string, number>;
  by_depth: Record<number, number>;
}

interface StuckGoal {
  id: string;
  title: string;
  status: string;
  progress: number;
  age_days: number;
  depth_level: number;
  is_atomic: boolean;
  parent_id: string | null;
  parent_title: string | null;
  children_count: number;
  has_execution_trace: boolean;
  reason: string;
}

// ========================
// UTILITIES
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
    case 'done': case 'completed': return 'text-green-400';
    case 'active': case 'running': return 'text-blue-400';
    case 'pending': return 'text-yellow-400';
    case 'blocked': case 'failed': return 'text-red-400';
    case 'frozen': return 'text-gray-400';
    default: return 'text-gray-300';
  }
}

function getStatusIcon(status: string): React.ElementType {
  switch (status) {
    case 'done': case 'completed': return CheckCircle;
    case 'active': case 'running': return Activity;
    case 'pending': return Clock;
    case 'blocked': return PauseCircle;
    case 'failed': return XCircle;
    case 'frozen': return AlertCircle;
    default: return Target;
  }
}

function getDepthLabel(level: number): string {
  switch (level) {
    case 0: return 'Mission';
    case 1: return 'Strategic';
    case 2: return 'Tactical';
    case 3: return 'Operational';
    default: return `L${level}`;
  }
}

// ========================
// GOAL TREE NODE
// ========================

function GoalTreeNode({
  goal,
  expanded,
  onToggle,
  onSelect,
  onAction,
}: {
  goal: Goal;
  expanded: boolean;
  onToggle: () => void;
  onSelect: (goal: Goal) => void;
  onAction: (goalId: string, action: string) => void;
}) {
  const StatusIcon = getStatusIcon(goal.status);
  const hasChildren = goal.children && goal.children.length > 0;

  return (
    <div className="select-none">
      <div
        className={`flex items-center gap-2 py-1.5 px-2 rounded hover:bg-gray-700/50 transition-colors cursor-pointer group ${
          goal.status === 'blocked' || goal.status === 'failed' ? 'bg-red-900/10' : ''
        }`}
        style={{ paddingLeft: `${goal.depth_level * 20 + 8}px` }}
      >
        {/* Expand/Collapse */}
        <button
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          className="text-gray-500 hover:text-gray-300 transition-colors w-4 h-4 flex items-center justify-center"
        >
          {hasChildren ? (
            expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <div className="w-3 h-3 rounded-full bg-gray-700" />
          )}
        </button>

        {/* Status Icon */}
        <StatusIcon size={14} className={getStatusColor(goal.status)} />

        {/* Atomic badge */}
        {goal.is_atomic && (
          <Zap size={12} className="text-cyan-400" />
        )}

        {/* Title */}
        <span
          className="text-sm text-gray-200 flex-1 truncate cursor-pointer hover:text-white"
          onClick={() => onSelect(goal)}
          title={goal.title}
        >
          {goal.title}
        </span>

        {/* Depth label */}
        <span className="text-[10px] text-gray-500 px-1.5 py-0.5 bg-gray-800 rounded">
          {getDepthLabel(goal.depth_level)}
        </span>

        {/* Progress */}
        <div className="flex items-center gap-1 w-20">
          <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full ${goal.progress >= 0.8 ? 'bg-green-500' : goal.progress >= 0.5 ? 'bg-blue-500' : goal.progress > 0 ? 'bg-yellow-500' : 'bg-gray-600'}`}
              style={{ width: `${goal.progress * 100}%` }}
            />
          </div>
          <span className="text-[10px] text-gray-400 w-8 text-right">
            {(goal.progress * 100).toFixed(0)}%
          </span>
        </div>

        {/* Quick Actions */}
        <div className="hidden group-hover:flex items-center gap-1">
          {goal.status === 'pending' && (
            <button
              onClick={(e) => { e.stopPropagation(); onAction(goal.id, 'execute'); }}
              className="p-1 hover:bg-green-900/50 rounded transition-colors"
              title="Execute"
            >
              <Play size={12} className="text-green-400" />
            </button>
          )}
          {(goal.status === 'pending' && !goal.is_atomic) && (
            <button
              onClick={(e) => { e.stopPropagation(); onAction(goal.id, 'decompose'); }}
              className="p-1 hover:bg-blue-900/50 rounded transition-colors"
              title="Decompose"
            >
              <GitBranch size={12} className="text-blue-400" />
            </button>
          )}
          {goal.status === 'active' && (
            <button
              onClick={(e) => { e.stopPropagation(); onAction(goal.id, 'freeze'); }}
              className="p-1 hover:bg-yellow-900/50 rounded transition-colors"
              title="Freeze"
            >
              <Pause size={12} className="text-yellow-400" />
            </button>
          )}
        </div>
      </div>

      {/* Children */}
      {expanded && hasChildren && (
        <div className="border-l border-gray-700/50 ml-4">
          {goal.children!.map((child) => (
            <GoalTreeNode
              key={child.id}
              goal={child}
              expanded={false}
              onToggle={() => {}}
              onSelect={onSelect}
              onAction={onAction}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ========================
// MAIN COMPONENT
// ========================

export default function Goals() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedGoals, setExpandedGoals] = useState<Set<string>>(new Set());
  const [selectedGoal, setSelectedGoal] = useState<Goal | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [depthFilter, setDepthFilter] = useState<number | null>(null);
  const [goalStats, setGoalStats] = useState<GoalStats | null>(null);
  const [stuckGoals, setStuckGoals] = useState<StuckGoal[]>([]);
  const [showStuckOnly, setShowStuckOnly] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchGoals = useCallback(async () => {
    try {
      const response = await apiClient.get('/goals/list');
      const goalsData: Goal[] = response.data?.goals || response.data || [];

      // Build tree structure
      const goalMap = new Map<string, Goal>();
      const roots: Goal[] = [];

      goalsData.forEach((goal: Goal) => {
        goal.children = [];
        goalMap.set(goal.id, goal);
      });

      goalsData.forEach((goal: Goal) => {
        if (goal.parent_id && goalMap.has(goal.parent_id)) {
          const parent = goalMap.get(goal.parent_id)!;
          parent.children!.push(goal);
        } else {
          roots.push(goal);
        }
      });

      // Sort children by depth then creation date
      roots.sort((a, b) => a.depth_level - b.depth_level || new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

      setGoals(roots);

      // Calculate stats
      const stats: GoalStats = {
        total: goalsData.length,
        pending: goalsData.filter((g: Goal) => g.status === 'pending').length,
        active: goalsData.filter((g: Goal) => g.status === 'active').length,
        done: goalsData.filter((g: Goal) => g.status === 'done').length,
        blocked: goalsData.filter((g: Goal) => g.status === 'blocked').length,
        failed: goalsData.filter((g: Goal) => g.status === 'failed').length,
        frozen: goalsData.filter((g: Goal) => g.status === 'frozen').length,
        cancelled: goalsData.filter((g: Goal) => g.status === 'cancelled').length,
        by_type: {},
        by_depth: {},
      };

      goalsData.forEach((g: Goal) => {
        stats.by_type[g.goal_type] = (stats.by_type[g.goal_type] || 0) + 1;
        stats.by_depth[g.depth_level] = (stats.by_depth[g.depth_level] || 0) + 1;
      });

      setGoalStats(stats);

      // Detect stuck goals
      const now = new Date();
      const stuck = goalsData
        .filter((g: Goal) => {
          const ageMs = now.getTime() - new Date(g.created_at).getTime();
          const ageDays = ageMs / (1000 * 60 * 60 * 24);
          return (
            (g.status === 'pending' || g.status === 'active') &&
            g.progress === 0 &&
            ageDays > 0.5 &&
            !g.is_atomic
          );
        })
        .map((g: Goal) => {
          const ageMs = now.getTime() - new Date(g.created_at).getTime();
          const ageDays = ageMs / (1000 * 60 * 60 * 24);
          const parent = g.parent_id ? goalMap.get(g.parent_id) : null;

          let reason = '';
          if (!g.is_atomic && g.children_count === 0) {
            reason = 'Non-atomic, not decomposed';
          } else if (g.status === 'active' && g.progress === 0) {
            reason = 'Active but no progress';
          } else {
            reason = 'Stuck in queue';
          }

          return {
            id: g.id,
            title: g.title,
            status: g.status,
            progress: g.progress,
            age_days: ageDays,
            depth_level: g.depth_level,
            is_atomic: g.is_atomic,
            parent_id: g.parent_id,
            parent_title: parent?.title || null,
            children_count: g.children_count || g.children?.length || 0,
            has_execution_trace: !!(g.execution_trace && Object.keys(g.execution_trace).length > 0),
            reason,
          };
        })
        .sort((a: StuckGoal, b: StuckGoal) => b.age_days - a.age_days);

      setStuckGoals(stuck);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch goals:', err);
      setError(err instanceof Error ? err.message : 'Failed to load goals');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGoals();
  }, [fetchGoals]);

  const toggleGoal = (goalId: string) => {
    setExpandedGoals((prev) => {
      const next = new Set(prev);
      if (next.has(goalId)) {
        next.delete(goalId);
      } else {
        next.add(goalId);
      }
      return next;
    });
  };

  const handleAction = async (goalId: string, action: string) => {
    setActionLoading(goalId);
    try {
      switch (action) {
        case 'execute':
          await apiClient.post(`/goals/${goalId}/execute`);
          break;
        case 'decompose':
          await apiClient.post(`/goals/${goalId}/decompose`, { max_depth: 2 });
          break;
        case 'freeze':
          await apiClient.post(`/goals/${goalId}/mutate`, {
            action: 'freeze',
            params: { reason: 'Frozen via dashboard' },
          });
          break;
      }
      await fetchGoals();
    } catch (err) {
      console.error(`Failed to ${action} goal:`, err);
    } finally {
      setActionLoading(null);
    }
  };

  // Filter goals
  const filterGoal = (goal: Goal): boolean => {
    if (showStuckOnly) {
      const isStuck = stuckGoals.some((sg) => sg.id === goal.id);
      if (!isStuck) return false;
    }

    if (statusFilter !== 'all' && goal.status !== statusFilter) return false;
    if (depthFilter !== null && goal.depth_level !== depthFilter) return false;
    if (searchQuery && !goal.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;

    return true;
  };

  const filterGoalTree = (goals: Goal[]): Goal[] => {
    return goals
      .filter(filterGoal)
      .map((goal) => ({
        ...goal,
        children: goal.children ? filterGoalTree(goal.children) : undefined,
      }));
  };

  const filteredGoals = filterGoalTree(goals);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <RefreshCw size={32} className="text-blue-400 animate-spin mr-3" />
        <span className="text-gray-400">Loading Goals...</span>
      </div>
    );
  }

  if (error && goals.length === 0) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <AlertTriangle size={48} className="text-red-400 mx-auto mb-4" />
          <div className="text-red-400 font-semibold mb-2">Failed to Load Goals</div>
          <div className="text-gray-400 text-sm mb-4">{error}</div>
          <button
            onClick={fetchGoals}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden bg-gray-900 flex">
      {/* Left Panel - Goal Tree */}
      <div className="w-2/3 flex flex-col border-r border-gray-700">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 bg-gray-800/50">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target size={22} className="text-blue-400" />
              <h2 className="text-lg font-semibold text-white">Goal Hierarchy</h2>
              <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">{goalStats?.total || 0} total</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowStuckOnly(!showStuckOnly)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                  showStuckOnly
                    ? 'bg-red-900/50 border border-red-700 text-red-300'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                <AlertTriangle size={12} />
                Stuck Only ({stuckGoals.length})
              </button>
              <button
                onClick={fetchGoals}
                className="p-1.5 hover:bg-gray-700 rounded transition-colors"
                title="Refresh"
              >
                <RefreshCw size={14} className="text-gray-400" />
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                placeholder="Search goals..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-gray-700 text-white text-sm rounded-lg pl-9 pr-3 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none"
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-gray-700 text-white text-sm rounded-lg px-2 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="active">Active</option>
              <option value="done">Done</option>
              <option value="blocked">Blocked</option>
              <option value="failed">Failed</option>
              <option value="frozen">Frozen</option>
            </select>

            {/* Depth Filter */}
            <select
              value={depthFilter ?? 'all'}
              onChange={(e) => setDepthFilter(e.target.value === 'all' ? null : parseInt(e.target.value))}
              className="bg-gray-700 text-white text-sm rounded-lg px-2 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="all">All Depths</option>
              <option value="0">L0 - Mission</option>
              <option value="1">L1 - Strategic</option>
              <option value="2">L2 - Tactical</option>
              <option value="3">L3 - Operational</option>
            </select>
          </div>
        </div>

        {/* Goal Tree */}
        <div className="flex-1 overflow-y-auto p-2">
          {filteredGoals.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Target size={48} className="mb-4 opacity-50" />
              <div className="text-sm">No goals match filters</div>
            </div>
          ) : (
            <div className="space-y-0.5">
              {filteredGoals.map((goal) => (
                <GoalTreeNode
                  key={goal.id}
                  goal={goal}
                  expanded={expandedGoals.has(goal.id)}
                  onToggle={() => toggleGoal(goal.id)}
                  onSelect={setSelectedGoal}
                  onAction={handleAction}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Stats & Detail */}
      <div className="w-1/3 flex flex-col bg-gray-800/30">
        {/* Stats */}
        {goalStats && (
          <div className="p-4 border-b border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 size={18} className="text-green-400" />
              <h3 className="text-sm font-semibold text-white">Goal Statistics</h3>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-4">
              {[
                { label: 'Pending', count: goalStats.pending, color: 'text-yellow-400', bg: 'bg-yellow-900/20' },
                { label: 'Active', count: goalStats.active, color: 'text-blue-400', bg: 'bg-blue-900/20' },
                { label: 'Done', count: goalStats.done, color: 'text-green-400', bg: 'bg-green-900/20' },
                { label: 'Blocked', count: goalStats.blocked, color: 'text-orange-400', bg: 'bg-orange-900/20' },
                { label: 'Failed', count: goalStats.failed, color: 'text-red-400', bg: 'bg-red-900/20' },
                { label: 'Frozen', count: goalStats.frozen, color: 'text-gray-400', bg: 'bg-gray-800/50' },
              ].map((item) => (
                <div key={item.label} className={`${item.bg} rounded-lg p-2 text-center`}>
                  <div className={`text-xl font-bold ${item.color}`}>{item.count}</div>
                  <div className="text-xs text-gray-500">{item.label}</div>
                </div>
              ))}
            </div>

            {/* Depth Distribution */}
            <div className="mb-2">
              <div className="text-xs text-gray-400 mb-2 flex items-center gap-1">
                <Layers size={12} />
                Depth Distribution
              </div>
              {Object.entries(goalStats.by_depth)
                .sort(([a], [b]) => parseInt(a) - parseInt(b))
                .map(([depth, count]) => (
                  <div key={depth} className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-500 w-16">{getDepthLabel(parseInt(depth))}</span>
                    <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500"
                        style={{ width: `${(count / goalStats.total) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400 w-8 text-right">{count}</span>
                  </div>
                ))}
            </div>

            {/* Type Distribution */}
            <div>
              <div className="text-xs text-gray-400 mb-2 flex items-center gap-1">
                <Filter size={12} />
                Type Distribution
              </div>
              {Object.entries(goalStats.by_type)
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <div key={type} className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-500 w-24 truncate">{type}</span>
                    <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500"
                        style={{ width: `${(count / goalStats.total) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400 w-8 text-right">{count}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Stuck Goals Alert */}
        {stuckGoals.length > 0 && (
          <div className="p-4 border-b border-gray-700 bg-red-900/10">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={16} className="text-red-400" />
              <h3 className="text-sm font-semibold text-red-300">Stuck Goals ({stuckGoals.length})</h3>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {stuckGoals.slice(0, 5).map((goal) => (
                <div key={goal.id} className="bg-red-900/20 rounded p-2 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-red-200 font-medium truncate">{goal.title}</span>
                    <span className="text-red-400">{goal.age_days.toFixed(0)}d</span>
                  </div>
                  <div className="text-red-400/70">{goal.reason}</div>
                  {goal.parent_title && (
                    <div className="text-red-400/50 mt-1">Parent: {goal.parent_title}</div>
                  )}
                  <button
                    onClick={() => handleAction(goal.id, 'decompose')}
                    disabled={actionLoading === goal.id}
                    className="mt-1 flex items-center gap-1 text-red-300 hover:text-red-200 transition-colors disabled:opacity-50"
                  >
                    <GitBranch size={10} />
                    Decompose
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Selected Goal Detail */}
        {selectedGoal && (
          <div className="flex-1 overflow-y-auto p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Eye size={16} className="text-blue-400" />
                Goal Detail
              </h3>
              <button
                onClick={() => setSelectedGoal(null)}
                className="text-gray-500 hover:text-gray-300"
              >
                <XCircle size={16} />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <div className="text-xs text-gray-500 mb-1">Title</div>
                <div className="text-sm text-gray-200">{selectedGoal.title}</div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">Status</div>
                  <div className={`text-sm font-medium ${getStatusColor(selectedGoal.status)}`}>
                    {selectedGoal.status}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Type</div>
                  <div className="text-sm text-gray-300">{selectedGoal.goal_type}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Depth</div>
                  <div className="text-sm text-gray-300">
                    L{selectedGoal.depth_level} ({getDepthLabel(selectedGoal.depth_level)})
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Atomic</div>
                  <div className="text-sm text-gray-300">{selectedGoal.is_atomic ? 'Yes' : 'No'}</div>
                </div>
              </div>

              <div>
                <div className="text-xs text-gray-500 mb-1">Progress</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-3 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${selectedGoal.progress >= 0.8 ? 'bg-green-500' : selectedGoal.progress >= 0.5 ? 'bg-blue-500' : selectedGoal.progress > 0 ? 'bg-yellow-500' : 'bg-gray-600'}`}
                      style={{ width: `${selectedGoal.progress * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-300 w-10 text-right">
                    {(selectedGoal.progress * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {selectedGoal.description && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">Description</div>
                  <div className="text-sm text-gray-400 bg-gray-800/50 rounded p-2 max-h-20 overflow-y-auto">
                    {selectedGoal.description}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">Created</div>
                  <div className="text-xs text-gray-400">
                    {new Date(selectedGoal.created_at).toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Age</div>
                  <div className="text-xs text-gray-400">{formatAge(selectedGoal.created_at)}</div>
                </div>
              </div>

              {selectedGoal.children && selectedGoal.children.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">Children ({selectedGoal.children.length})</div>
                  <div className="space-y-1">
                    {selectedGoal.children.map((child) => {
                      const ChildStatusIcon = getStatusIcon(child.status);
                      return (
                        <div key={child.id} className="flex items-center gap-2 text-xs bg-gray-800/50 rounded p-1.5">
                          <ChildStatusIcon size={12} className={getStatusColor(child.status)} />
                          <span className="text-gray-300 flex-1 truncate">{child.title}</span>
                          <span className="text-gray-500">{(child.progress * 100).toFixed(0)}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-2 border-t border-gray-700">
                {selectedGoal.status === 'pending' && (
                  <button
                    onClick={() => handleAction(selectedGoal.id, 'execute')}
                    disabled={actionLoading === selectedGoal.id}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-green-900/50 border border-green-700 rounded-lg text-sm text-green-300 hover:bg-green-900/70 transition-colors disabled:opacity-50"
                  >
                    <Play size={14} /> Execute
                  </button>
                )}
                {selectedGoal.status === 'pending' && !selectedGoal.is_atomic && (
                  <button
                    onClick={() => handleAction(selectedGoal.id, 'decompose')}
                    disabled={actionLoading === selectedGoal.id}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-blue-900/50 border border-blue-700 rounded-lg text-sm text-blue-300 hover:bg-blue-900/70 transition-colors disabled:opacity-50"
                  >
                    <GitBranch size={14} /> Decompose
                  </button>
                )}
                {selectedGoal.status === 'active' && (
                  <button
                    onClick={() => handleAction(selectedGoal.id, 'freeze')}
                    disabled={actionLoading === selectedGoal.id}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-yellow-900/50 border border-yellow-700 rounded-lg text-sm text-yellow-300 hover:bg-yellow-900/70 transition-colors disabled:opacity-50"
                  >
                    <Pause size={14} /> Freeze
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Empty state when no goal selected */}
        {!selectedGoal && (
          <div className="flex-1 flex items-center justify-center text-gray-600">
            <div className="text-center">
              <Terminal size={32} className="mx-auto mb-2 opacity-50" />
              <div className="text-sm">Select a goal to view details</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
