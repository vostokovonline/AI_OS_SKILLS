/**
 * Performance Dashboard
 *
 * System performance metrics: latency, throughput, queue lengths, container stats.
 * Displays goal execution metrics and resource utilization.
 */

import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  Activity,
  TrendingUp,
  Clock,
  HardDrive,
  Cpu,
  CheckCircle,
  AlertTriangle,
  RefreshCw
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface PerformanceMetrics {
  queue: {
    length: number;
    status: 'ok' | 'backlog';
  };
  containers: Record<string, {
    status: string;
    cpu_percent: number;
    memory_mb: number;
  }>;
  goals: {
    completed: number;
    active: number;
    total: number;
    completion_rate: number;
  };
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

const ContainerCard: React.FC<{
  name: string;
  stats: { status: string; cpu_percent: number; memory_mb: number };
}> = ({ name, stats }) => {
    if (stats.status === 'error') {
      return (
        <div className="bg-red-50 rounded-lg border border-red-200 p-4">
          <h4 className="font-semibold text-red-900 mb-2">{name}</h4>
          <p className="text-sm text-red-700">Error reading stats</p>
        </div>
      );
    }

    const cpuColor = stats.cpu_percent < 50 ? 'bg-green-500' : stats.cpu_percent < 80 ? 'bg-yellow-500' : 'bg-red-500';
    const memoryGB = (stats.memory_mb / 1024).toFixed(2);

    return (
      <div className="bg-white rounded-lg shadow p-4">
        <h4 className="font-semibold mb-3">{name.replace('ns_', '')}</h4>

        <div className="mb-3">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">CPU</span>
            <span className="font-medium">{stats.cpu_percent.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`${cpuColor} h-2 rounded-full`}
              style={{ width: `${Math.min(stats.cpu_percent, 100)}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Memory</span>
            <span className="font-medium">{memoryGB} GB</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full"
              style={{ width: `${Math.min((stats.memory_mb / 8192) * 100, 100)}%` }}
            />
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2 text-sm text-green-600">
          <CheckCircle className="w-4 h-4" />
          <span>Running</span>
        </div>
      </div>
    );
  };

// ============================================================================
// Main Page
// ============================================================================

const Performance: React.FC = () => {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const loadData = async () => {
    try {
      const response = await apiClient.get<PerformanceMetrics>('/analytics/performance-metrics?hours=1');
      setMetrics(response);
      setLoading(false);
      setLastUpdate(new Date());
      setError(null);
    } catch (err: any) {
      console.error('Failed to load performance metrics:', err);
      setError(err.message || 'Failed to load performance data');
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
          <p className="text-gray-600">Loading performance metrics...</p>
        </div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="h-screen w-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 mx-auto mb-4 text-red-600" />
          <p className="text-red-600 font-semibold">{error || 'Failed to load data'}</p>
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

  const queueLength = metrics.queue.length;
  const queueStatus = metrics.queue.status;
  const totalGoals = metrics.goals.total;
  const completedGoals = metrics.goals.completed;
  const activeGoals = metrics.goals.active;
  const completionRate = metrics.goals.completion_rate;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                <TrendingUp className="w-8 h-8 text-blue-600" />
                Performance Dashboard
              </h1>
              <p className="text-gray-600 mt-2">
                System performance metrics (Last 1 hour)
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
            title="Queue Length"
            value={queueLength}
            subtitle={queueStatus === 'ok' ? 'Processing normally' : 'Backlog detected'}
            icon={<Clock className="w-6 h-6 text-white" />}
            color={queueStatus === 'ok' ? 'bg-green-600' : 'bg-yellow-600'}
          />
          <MetricCard
            title="Total Goals"
            value={totalGoals}
            subtitle="Last 1 hour"
            icon={<Activity className="w-6 h-6 text-white" />}
            color="bg-blue-600"
          />
          <MetricCard
            title="Completed"
            value={completedGoals}
            subtitle={`${activeGoals} still active`}
            icon={<CheckCircle className="w-6 h-6 text-white" />}
            color="bg-green-600"
          />
          <MetricCard
            title="Completion Rate"
            value={`${completionRate.toFixed(1)}%`}
            subtitle="Goal success rate"
            icon={<TrendingUp className="w-6 h-6 text-white" />}
            color={completionRate > 80 ? 'bg-green-600' : completionRate > 50 ? 'bg-yellow-600' : 'bg-red-600'}
          />
        </div>

        {/* Containers Grid */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Container Resources</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(metrics.containers || {}).map(([name, stats]) => (
              <ContainerCard key={name} name={name} stats={stats} />
            ))}
          </div>
        </div>

        {/* Resource Utilization Summary */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Resource Utilization Summary</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* CPU Summary */}
            <div>
              <h3 className="text-sm font-medium text-gray-600 mb-3">Average CPU Usage</h3>
              {(() => {
                const containers = Object.values(metrics.containers || {}).filter(c => c.status === 'running');
                const avgCpu = containers.length > 0
                  ? containers.reduce((sum, c) => sum + c.cpu_percent, 0) / containers.length
                  : 0;

                return (
                  <div className="flex items-center gap-4">
                    <div className="flex-1 bg-gray-200 rounded-full h-4">
                      <div
                        className={`h-4 rounded-full ${avgCpu < 50 ? 'bg-green-500' : avgCpu < 80 ? 'bg-yellow-500' : 'bg-red-500'}`}
                        style={{ width: `${Math.min(avgCpu, 100)}%` }}
                      />
                    </div>
                    <span className="font-medium">{avgCpu.toFixed(1)}%</span>
                  </div>
                );
              })()}
            </div>

            {/* Memory Summary */}
            <div>
              <h3 className="text-sm font-medium text-gray-600 mb-3">Total Memory Usage</h3>
              {(() => {
                const containers = Object.values(metrics.containers || {}).filter(c => c.status === 'running');
                const totalMemory = containers.reduce((sum, c) => sum + c.memory_mb, 0);
                const memoryGB = (totalMemory / 1024).toFixed(2);

                return (
                  <div className="flex items-center gap-4">
                    <HardDrive className="w-5 h-5 text-blue-600" />
                    <span className="font-medium">{memoryGB} GB</span>
                    <span className="text-sm text-gray-500">across {containers.length} containers</span>
                  </div>
                );
              })()}
            </div>

            {/* Running Containers */}
            <div>
              <h3 className="text-sm font-medium text-gray-600 mb-3">Running Containers</h3>
              {(() => {
                const runningCount = Object.values(metrics.containers || {}).filter(c => c.status === 'running').length;
                const totalCount = Object.keys(metrics.containers || {}).length;

                return (
                  <div className="flex items-center gap-4">
                    <Cpu className="w-5 h-5 text-green-600" />
                    <span className="font-medium">{runningCount} / {totalCount}</span>
                    <span className="text-sm text-gray-500">running</span>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Performance;
