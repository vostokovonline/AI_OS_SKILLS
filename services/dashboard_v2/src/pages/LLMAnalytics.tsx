/**
 * LLM Analytics Dashboard
 *
 * Displays model usage metrics, latency charts, error rates, and token consumption.
 * Unified analytics ported from Dashboard v1 with enhanced visualizations.
 */

import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Database,
  RefreshCw
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface LLMMetrics {
  models: Record<string, ModelStats>;
  usage_24h: {
    total_calls: number;
    success_rate: number;
    error_count: number;
  };
  latency: {
    avg_ms: number;
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
  };
  tokens: {
    total_tokens: number;
    avg_tokens_per_call: number;
  };
}

interface ModelStats {
  calls: number;
  success: number;
  error_rate: number;
  avg_duration_ms: number;
  total_tokens: number;
}

interface TimeSeriesData {
  timestamp: string;
  calls: number;
  success: number;
  errors: number;
  avg_duration_ms: number;
  total_tokens: number;
}

interface ModelLimits {
  limits: Array<{
    model_name: string;
    rpm_limit: number;
    current_rpm: number;
    usage_percent: number;
    status: 'ok' | 'warning' | 'critical';
    last_updated: string | null;
  }>;
}

// ============================================================================
// Components
// ============================================================================

const MetricCard: React.FC<{
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
}> = ({ title, value, subtitle, icon, color }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-600 mb-1">{title}</p>
        <p className="text-2xl font-bold">{value}</p>
        {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
      </div>
      <div className={`${color} p-3 rounded-full`}>
        {icon}
      </div>
    </div>
  </div>
);

const LatencyBar: React.FC<{ label: string; value: number; max: number; color: string }> =
  ({ label, value, max, color }) => {
    const percent = Math.min((value / max) * 100, 100);
    return (
      <div className="flex items-center gap-4">
        <div className="w-24 text-sm text-gray-600">{label}</div>
        <div className="flex-1">
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className={`${color} h-3 rounded-full transition-all duration-300`}
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>
        <div className="w-16 text-right text-sm font-medium">{value.toFixed(1)} ms</div>
      </div>
    );
  };

const SimpleTimeChart: React.FC<{ data: TimeSeriesData[]; field: 'calls' | 'avg_duration_ms' | 'total_tokens'; color: string; label: string }> =
  ({ data, field, color, label }) => {
    if (!data || data.length === 0) return null;

    const maxValue = Math.max(...data.map(d => d[field]), 1);

    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">{label}</h3>
        <div className="space-y-2">
          {data.slice(0, 12).map((point, idx) => {
            const percent = (point[field] / maxValue) * 100;
            const time = new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            return (
              <div key={idx} className="flex items-center gap-4">
                <div className="w-16 text-xs text-gray-500">{time}</div>
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    className={`${color} h-2 rounded-full`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
                <div className="w-20 text-right text-sm">{point[field].toLocaleString()}</div>
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

const LLMAnalytics: React.FC = () => {
  const [metrics, setMetrics] = useState<LLMMetrics | null>(null);
  const [history, setHistory] = useState<TimeSeriesData[]>([]);
  const [limits, setLimits] = useState<ModelLimits | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const loadData = async () => {
    try {
      // Load metrics
      const metricsResponse = await apiClient.get<LLMMetrics>('/analytics/llm-overview');
      setMetrics(metricsResponse);

      // Load history (last 24h, 24 points)
      const historyResponse = await apiClient.get<{ history: TimeSeriesData[] }>('/analytics/llm-history?hours=24&points=24');
      setHistory(historyResponse.history || []);

      // Load model limits
      try {
        const limitsResponse = await apiClient.get<ModelLimits>('/analytics/model-limits');
        setLimits(limitsResponse);
      } catch (err) {
        // Limits might not be available
        setLimits(null);
      }

      setLoading(false);
      setLastUpdate(new Date());
      setError(null);
    } catch (err: any) {
      console.error('Failed to load LLM analytics:', err);
      setError(err.message || 'Failed to load analytics');
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="h-screen w-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-16 h-16 animate-pulse mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Loading LLM analytics...</p>
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

  const totalCalls = metrics?.usage_24h.total_calls || 0;
  const successRate = metrics?.usage_24h.success_rate || 0;
  const errorCount = metrics?.usage_24h.error_count || 0;
  const avgLatency = metrics?.latency.avg_ms || 0;
  const totalTokens = metrics?.tokens.total_tokens || 0;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                <Activity className="w-8 h-8 text-blue-600" />
                LLM Analytics
              </h1>
              <p className="text-gray-600 mt-2">
                Model usage metrics, latency, and token consumption (Last 24h)
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

        {/* Overview Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <MetricCard
            title="Total Calls"
            value={totalCalls.toLocaleString()}
            icon={<Activity className="w-6 h-6 text-white" />}
            color="bg-blue-600"
          />
          <MetricCard
            title="Success Rate"
            value={`${successRate.toFixed(1)}%`}
            subtitle={`${errorCount} errors`}
            icon={successRate > 90 ? <CheckCircle className="w-6 h-6 text-white" /> : <AlertTriangle className="w-6 h-6 text-white" />}
            color={successRate > 90 ? 'bg-green-600' : 'bg-yellow-600'}
          />
          <MetricCard
            title="Avg Latency"
            value={`${avgLatency.toFixed(0)} ms`}
            subtitle="P95: {metrics?.latency.p95_ms.toFixed(0)} ms"
            icon={<Clock className="w-6 h-6 text-white" />}
            color="bg-purple-600"
          />
          <MetricCard
            title="Total Tokens"
            value={totalTokens.toLocaleString()}
            subtitle={`${(totalTokens / 1000).toFixed(1)}k tokens`}
            icon={<Database className="w-6 h-6 text-white" />}
            color="bg-orange-600"
          />
        </div>

        {/* Latency Percentiles */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h3 className="text-lg font-semibold mb-4">Latency Percentiles</h3>
          <div className="space-y-4">
            <LatencyBar label="P50" value={metrics?.latency.p50_ms || 0} max={metrics?.latency.p99_ms || 1000} color="bg-green-500" />
            <LatencyBar label="P95" value={metrics?.latency.p95_ms || 0} max={metrics?.latency.p99_ms || 1000} color="bg-yellow-500" />
            <LatencyBar label="P99" value={metrics?.latency.p99_ms || 0} max={metrics?.latency.p99_ms || 1000} color="bg-red-500" />
          </div>
        </div>

        {/* By-Model Breakdown */}
        {metrics?.models && Object.keys(metrics.models).length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-8">
            <h3 className="text-lg font-semibold mb-4">By Model</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="py-2 px-4 text-left">Model</th>
                    <th className="py-2 px-4 text-left">Calls</th>
                    <th className="py-2 px-4 text-left">Success</th>
                    <th className="py-2 px-4 text-left">Error Rate</th>
                    <th className="py-2 px-4 text-left">Avg Latency</th>
                    <th className="py-2 px-4 text-left">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(metrics.models).map(([modelName, stats]) => (
                    <tr key={modelName} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-4 font-medium">{modelName}</td>
                      <td className="py-3 px-4">{stats.calls.toLocaleString()}</td>
                      <td className="py-3 px-4">
                        <span className="text-green-600">{stats.success.toLocaleString()}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={stats.error_rate < 5 ? 'text-green-600' : stats.error_rate < 10 ? 'text-yellow-600' : 'text-red-600'}>
                          {stats.error_rate.toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-3 px-4">{stats.avg_duration_ms.toFixed(1)} ms</td>
                      <td className="py-3 px-4">{stats.total_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Time Series Charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <SimpleTimeChart
            data={history}
            field="calls"
            color="bg-blue-500"
            label="Calls Over Time"
          />
          <SimpleTimeChart
            data={history}
            field="avg_duration_ms"
            color="bg-purple-500"
            label="Latency Over Time"
          />
        </div>

        {/* Model Limits */}
        {limits && limits.limits.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Model Limits (RPM)</h3>
            <div className="space-y-4">
              {limits.limits.map((limit) => (
                <div key={limit.model_name} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{limit.model_name}</span>
                      <span className={`text-xs px-2 py-1 rounded ${
                        limit.status === 'ok' ? 'bg-green-100 text-green-700' :
                        limit.status === 'warning' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {limit.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600">
                      {limit.current_rpm} / {limit.rpm_limit} RPM
                    </div>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className={`h-3 rounded-full transition-all duration-300 ${
                        limit.usage_percent < 80 ? 'bg-green-500' :
                        limit.usage_percent < 95 ? 'bg-yellow-500' :
                        'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(limit.usage_percent, 100)}%` }}
                    />
                  </div>
                  <div className="text-right text-xs text-gray-500 mt-1">
                    {limit.usage_percent.toFixed(1)}% utilized
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LLMAnalytics;
