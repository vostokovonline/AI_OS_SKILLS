/**
 * System Health Dashboard
 *
 * Real-time health status of all services (PostgreSQL, Redis, Neo4j, Milvus, LiteLLM, Core API)
 * Displays latency, status, and error messages.
 */

import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Server,
  Database,
  HardDrive,
  Zap,
  Globe,
  RefreshCw
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency_ms?: number;
  error?: string;
}

interface SystemHealthResponse {
  postgres: ServiceHealth;
  redis: ServiceHealth;
  neo4j: ServiceHealth;
  milvus: ServiceHealth;
  litellm: ServiceHealth;
  core_api: ServiceHealth;
  overall: 'healthy' | 'degraded';
}

// ============================================================================
// Components
// ============================================================================

const ServiceCard: React.FC<{
  name: string;
  icon: React.ReactNode;
  health: ServiceHealth;
}> = ({ name, icon, health }) => {
    const statusConfig = {
      healthy: { color: 'bg-green-500', text: 'text-green-600', label: 'HEALTHY' },
      degraded: { color: 'bg-yellow-500', text: 'text-yellow-600', label: 'DEGRADED' },
      unhealthy: { color: 'bg-red-500', text: 'text-red-600', label: 'UNHEALTHY' },
    };

    const config = statusConfig[health.status];

    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${config.color} bg-opacity-10`}>
              {icon}
            </div>
            <h3 className="text-lg font-semibold">{name}</h3>
          </div>
          <div className={`px-3 py-1 rounded-full text-xs font-medium ${config.color} text-white`}>
            {config.label}
          </div>
        </div>

        {health.latency_ms !== undefined && (
          <div className="mb-2">
            <span className="text-sm text-gray-600">Latency: </span>
            <span className="font-medium">{health.latency_ms.toFixed(1)} ms</span>
          </div>
        )}

        {health.error && (
          <div className="mt-3 p-3 bg-red-50 rounded border border-red-200">
            <p className="text-sm text-red-700 break-words">{health.error}</p>
          </div>
        )}

        {health.status === 'healthy' && health.latency_ms !== undefined && (
          <div className="mt-3 flex items-center gap-2 text-sm text-green-600">
            <CheckCircle className="w-4 h-4" />
            <span>All systems operational</span>
          </div>
        )}
      </div>
    );
  };

// ============================================================================
// Main Page
// ============================================================================

const SystemHealth: React.FC = () => {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const loadHealth = async () => {
    try {
      const response = await apiClient.get<SystemHealthResponse>('/analytics/system-health');
      setHealth(response);
      setLoading(false);
      setLastUpdate(new Date());
      setError(null);
    } catch (err: any) {
      console.error('Failed to load system health:', err);
      setError(err.message || 'Failed to load health status');
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
    const interval = setInterval(loadHealth, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="h-screen w-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Server className="w-16 h-16 animate-pulse mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Checking system health...</p>
        </div>
      </div>
    );
  }

  if (error || !health) {
    return (
      <div className="h-screen w-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <XCircle className="w-16 h-16 mx-auto mb-4 text-red-600" />
          <p className="text-red-600 font-semibold">{error || 'Failed to load health data'}</p>
          <button
            onClick={loadHealth}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const overallHealthy = health.overall === 'healthy';

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                <Server className="w-8 h-8 text-blue-600" />
                System Health
              </h1>
              <p className="text-gray-600 mt-2">
                Real-time status of all services
              </p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">
                Last update: {lastUpdate.toLocaleTimeString()}
              </span>
              <button
                onClick={loadHealth}
                className="p-2 bg-white rounded shadow hover:bg-gray-100"
                title="Refresh"
              >
                <RefreshCw className="w-5 h-5 text-gray-600" />
              </button>
            </div>
          </div>
        </div>

        {/* Overall Status Banner */}
        <div className={`mb-8 p-6 rounded-lg ${overallHealthy ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
          <div className="flex items-center gap-4">
            {overallHealthy ? (
              <CheckCircle className="w-8 h-8 text-green-600" />
            ) : (
              <AlertTriangle className="w-8 h-8 text-yellow-600" />
            )}
            <div>
              <h2 className={`text-xl font-semibold ${overallHealthy ? 'text-green-900' : 'text-yellow-900'}`}>
                System {overallHealthy ? 'Healthy' : 'Degraded'}
              </h2>
              <p className={`text-sm ${overallHealthy ? 'text-green-700' : 'text-yellow-700'}`}>
                {overallHealthy
                  ? 'All services are operating normally'
                  : 'Some services are experiencing issues'}
              </p>
            </div>
          </div>
        </div>

        {/* Services Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <ServiceCard
            name="PostgreSQL"
            icon={<Database className="w-6 h-6 text-blue-600" />}
            health={health.postgres}
          />
          <ServiceCard
            name="Redis"
            icon={<Zap className="w-6 h-6 text-red-600" />}
            health={health.redis}
          />
          <ServiceCard
            name="Neo4j"
            icon={<Globe className="w-6 h-6 text-blue-500" />}
            health={health.neo4j}
          />
          <ServiceCard
            name="Milvus"
            icon={<HardDrive className="w-6 h-6 text-purple-600" />}
            health={health.milvus}
          />
          <ServiceCard
            name="LiteLLM"
            icon={<Server className="w-6 h-6 text-green-600" />}
            health={health.litellm}
          />
          <ServiceCard
            name="Core API"
            icon={<AlertTriangle className="w-6 h-6 text-orange-600" />}
            health={health.core_api}
          />
        </div>

        {/* Status Legend */}
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Status Legend</h3>
          <div className="flex gap-8">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-green-500"></div>
              <span className="text-sm">Healthy - All systems operational</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
              <span className="text-sm">Degraded - Service responding slowly</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-red-500"></div>
              <span className="text-sm">Unhealthy - Service unavailable</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemHealth;
