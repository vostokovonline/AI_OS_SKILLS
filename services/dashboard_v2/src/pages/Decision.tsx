/**
 * Decision Dashboard
 *
 * Displays arbitration layer metrics and decision history
 * Shows selected vs rejected intents, budget allocation, and decision timeline
 */

import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  Target,
  TrendingUp,
  DollarSign,
  CheckCircle2,
  XCircle,
  BarChart3,
  RefreshCw
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface ArbitrationMetrics {
  current_budget: number;
  total_budget?: number;
  selection_rate_24h: number;
  total_processed_24h: number;
  total_selected_24h: number;
  total_rejected_24h: number;
  avg_utility_per_selected: number;
  avg_cost_per_selected: number;
  recent_decisions_count: number;
}

interface ScoredIntent {
  goal_id: string;
  utility: number;
  cost: number;
  risk: number;
  confidence: number;
  rejection_reason?: string; // "low_utility" | "high_risk" | "budget_exhausted" | "lower_priority"
}

interface ArbitrationResult {
  selected_count: number;
  rejected_count: number;
  total_count: number;
  selection_rate: number;
  total_utility: number;
  total_cost: number;
  budget_remaining: number | null;
  timestamp: string;
  selected: ScoredIntent[];
  rejected: ScoredIntent[];
}

// ============================================================================
// Components
// ============================================================================

const MetricCard: React.FC<{
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}> = ({ title, value, icon, color }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-600 mb-1">{title}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
      <div className={`${color} p-3 rounded-full`}>
        {icon}
      </div>
    </div>
  </div>
);

const BudgetGauge: React.FC<{
  current: number;
  total: number;
}> = ({ current, total }) => {
  const percentage = (current / total) * 100;
  const remaining = total - current;

  // Color based on usage
  const getColor = () => {
    if (percentage < 50) return 'bg-green-500';
    if (percentage < 80) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <DollarSign className="w-5 h-5 text-green-600" />
        Budget Allocation
      </h3>

      <div className="mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-gray-600">Used: {current.toFixed(1)} units</span>
          <span className="text-gray-600">Remaining: {remaining.toFixed(1)} units</span>
        </div>

        <div className="w-full bg-gray-200 rounded-full h-4">
          <div
            className={`${getColor()} h-4 rounded-full transition-all duration-500`}
            style={{ width: `${percentage}%` }}
          />
        </div>

        <p className="text-center mt-2 text-sm text-gray-600">
          {percentage.toFixed(1)}% utilized
        </p>
      </div>
    </div>
  );
};

const IntentRow: React.FC<{
  intent: ScoredIntent;
  status: 'selected' | 'rejected';
}> = ({ intent, status }) => (
  <tr className="border-b hover:bg-gray-50">
    <td className="py-3 px-4">
      <code className="text-sm bg-gray-100 px-2 py-1 rounded">
        {intent.goal_id.slice(0, 8)}...
      </code>
    </td>
    <td className="py-3 px-4">
      <div className="flex items-center gap-2">
        <span className={intent.utility > 0.6 ? 'text-green-600' : 'text-yellow-600'}>
          {intent.utility.toFixed(2)}
        </span>
        <div className="w-16 bg-gray-200 rounded-full h-2">
          <div
            className="bg-green-500 h-2 rounded-full"
            style={{ width: `${intent.utility * 100}%` }}
          />
        </div>
      </div>
    </td>
    <td className="py-3 px-4">{intent.cost.toFixed(1)}</td>
    <td className="py-3 px-4">
      <span className={intent.risk < 0.4 ? 'text-green-600' : intent.risk < 0.7 ? 'text-yellow-600' : 'text-red-600'}>
        {(intent.risk * 100).toFixed(0)}%
      </span>
    </td>
    {status === 'rejected' && (
      <td className="py-3 px-4">
        {intent.rejection_reason && (
          <span className={`text-xs px-2 py-1 rounded ${
            intent.rejection_reason === 'budget_exhausted' ? 'bg-red-100 text-red-700' :
            intent.rejection_reason === 'low_utility' ? 'bg-yellow-100 text-yellow-700' :
            intent.rejection_reason === 'high_risk' ? 'bg-orange-100 text-orange-700' :
            'bg-gray-100 text-gray-700'
          }`}>
            {intent.rejection_reason.replace('_', ' ')}
          </span>
        )}
      </td>
    )}
    <td className="py-3 px-4">
      {status === 'selected' ? (
        <CheckCircle2 className="w-5 h-5 text-green-500" />
      ) : (
        <XCircle className="w-5 h-5 text-red-500" />
      )}
    </td>
  </tr>
);

// Decision Timeline Component
const DecisionTimeline: React.FC<{
  history: ArbitrationResult[];
}> = ({ history }) => {
  if (history.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Decision Timeline</h3>
        <p className="text-gray-500 text-center py-8">No decision history yet</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">Decision Timeline (Last {history.length} decisions)</h3>

      <div className="space-y-3">
        {history.map((result, idx) => {
          const timestamp = new Date(result.timestamp).toLocaleTimeString();
          const selectedCount = result.selected_count;
          const rejectedCount = result.rejected_count;
          const total = result.total_count;
          const selectedPercent = (selectedCount / total) * 100;

          return (
            <div key={idx} className="flex items-center gap-4">
              <div className="w-20 text-xs text-gray-500 text-right">{timestamp}</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium">{total} intents</span>
                  <span className="text-xs text-gray-500">
                    {selectedCount} selected / {rejectedCount} rejected
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden flex">
                  <div
                    className="bg-green-500 h-4 transition-all duration-300"
                    style={{ width: `${selectedPercent}%` }}
                    title={`Selected: ${selectedCount}`}
                  />
                  <div
                    className="bg-red-500 h-4 transition-all duration-300"
                    style={{ width: `${100 - selectedPercent}%` }}
                    title={`Rejected: ${rejectedCount}`}
                  />
                </div>
              </div>
              <div className="w-16 text-right">
                <span className={`text-sm font-semibold ${selectedPercent > 50 ? 'text-green-600' : 'text-red-600'}`}>
                  {selectedPercent.toFixed(0)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ============================================================================
// Main Page
// ============================================================================

const Decision: React.FC = () => {
  const [metrics, setMetrics] = useState<ArbitrationMetrics | null>(null);
  const [latest, setLatest] = useState<ArbitrationResult | null>(null);
  const [history, setHistory] = useState<ArbitrationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const loadData = async () => {
    try {
      // Load metrics
      const metricsResponse = await apiClient.get<ArbitrationMetrics>('/arbitration/metrics');
      setMetrics(metricsResponse);

      // Load latest decision
      try {
        const latestResponse = await apiClient.get<ArbitrationResult>('/arbitration/latest');
        setLatest(latestResponse);
      } catch (err) {
        // No decisions yet - that's ok
        setLatest(null);
      }

      // Load history (last 20 decisions)
      try {
        const historyResponse = await apiClient.get<ArbitrationResult[]>('/arbitration/history?limit=20');
        setHistory(historyResponse);
      } catch (err) {
        // History might not be available
        setHistory([]);
      }

      setLoading(false);
      setLastUpdate(new Date());
      setError(null);
    } catch (err: any) {
      console.error('Failed to load decision data:', err);
      setError(err.message || 'Failed to load decision data');
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="h-screen w-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Target className="w-16 h-16 animate-pulse mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Loading decision system...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-screen w-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <XCircle className="w-16 h-16 mx-auto mb-4 text-red-600" />
          <p className="text-red-600 font-semibold">{error}</p>
          <button
            onClick={loadData}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const totalBudget = metrics?.total_budget || 10.0;
  const budgetUsed = totalBudget - (metrics?.current_budget || totalBudget);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                <Target className="w-8 h-8 text-blue-600" />
                Decision Dashboard
              </h1>
              <p className="text-gray-600 mt-2">
                Arbitration layer metrics and decision history
              </p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">
                Last update: {lastUpdate.toLocaleTimeString()}
              </span>
              <button
                onClick={loadData}
                className="p-2 bg-white rounded shadow hover:bg-gray-100"
                title="Refresh"
              >
                <RefreshCw className="w-5 h-5 text-gray-600" />
              </button>
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <MetricCard
            title="Current Budget"
            value={`${metrics?.current_budget.toFixed(1) || 0} / ${totalBudget}`}
            icon={<DollarSign className="w-6 h-6 text-white" />}
            color="bg-green-600"
          />
          <MetricCard
            title="Selection Rate"
            value={`${((metrics?.selection_rate_24h || 0) * 100).toFixed(1)}%`}
            icon={<TrendingUp className="w-6 h-6 text-white" />}
            color="bg-blue-600"
          />
          <MetricCard
            title="Avg Utility"
            value={(metrics?.avg_utility_per_selected || 0).toFixed(2)}
            icon={<BarChart3 className="w-6 h-6 text-white" />}
            color="bg-purple-600"
          />
          <MetricCard
            title="Processed (24h)"
            value={metrics?.total_processed_24h || 0}
            icon={<Target className="w-6 h-6 text-white" />}
            color="bg-orange-600"
          />
        </div>

        {/* Budget Gauge */}
        <div className="mb-8">
          <BudgetGauge current={budgetUsed} total={totalBudget} />
        </div>

        {/* Decision Timeline */}
        <div className="mb-8">
          <DecisionTimeline history={history} />
        </div>

        {/* Latest Decision Details */}
        {latest && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-xl font-semibold mb-4">Latest Decision</h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-1">Total Intents</p>
                <p className="text-3xl font-bold">{latest.total_count}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-1">Selected</p>
                <p className="text-3xl font-bold text-green-600">{latest.selected_count}</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-1">Rejected</p>
                <p className="text-3xl font-bold text-red-600">{latest.rejected_count}</p>
              </div>
            </div>

            {/* Selected Table */}
            {latest.selected.length > 0 && (
              <div className="mb-6">
                <h4 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  Selected Intents ({latest.selected.length})
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="py-2 px-4 text-left">Goal ID</th>
                        <th className="py-2 px-4 text-left">Utility</th>
                        <th className="py-2 px-4 text-left">Cost</th>
                        <th className="py-2 px-4 text-left">Risk</th>
                        <th className="py-2 px-4 text-left">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latest.selected.map((intent, idx) => (
                        <IntentRow
                          key={`selected-${idx}`}
                          intent={intent}
                          status="selected"
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Rejected Table */}
            {latest.rejected.length > 0 && (
              <div>
                <h4 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <XCircle className="w-5 h-5 text-red-600" />
                  Rejected Intents ({latest.rejected.length})
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="py-2 px-4 text-left">Goal ID</th>
                        <th className="py-2 px-4 text-left">Utility</th>
                        <th className="py-2 px-4 text-left">Cost</th>
                        <th className="py-2 px-4 text-left">Risk</th>
                        <th className="py-2 px-4 text-left">Reason</th>
                        <th className="py-2 px-4 text-left">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latest.rejected.map((intent, idx) => (
                        <IntentRow
                          key={`rejected-${idx}`}
                          intent={intent}
                          status="rejected"
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* No Data State */}
        {!latest && (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <Target className="w-16 h-16 mx-auto mb-4 text-gray-400" />
            <h3 className="text-xl font-semibold text-gray-700 mb-2">
              No Decisions Yet
            </h3>
            <p className="text-gray-600">
              Waiting for execution batch to complete...
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Decision;
