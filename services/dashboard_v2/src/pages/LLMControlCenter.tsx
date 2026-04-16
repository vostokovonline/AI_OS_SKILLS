import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { Activity, DollarSign, Zap, TrendingUp, AlertTriangle, CheckCircle, Settings, BarChart3 } from 'lucide-react';

interface OverviewData {
  total_cost_usd: number;
  cost_by_model: Record<string, number>;
  cost_trend: 'increasing' | 'stable' | 'decreasing';
  total_calls: number;
  overall_success_rate: number;
  p95_latency_ms: number;
  slow_calls_count: number;
  top_models_by_roi: Array<{ model: string; roi: number; success_rate: number }>;
  active_policy: string;
  policy_compliance: number;
}

interface ModelMetrics {
  model_name: string;
  provider: string;
  total_calls: number;
  success_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  total_cost_usd: number;
  cost_per_1k_tokens: number;
  avg_tokens_per_call: number;
  cost_per_successful_goal?: number;
  success_rate_by_goal_type: Record<string, number>;
}

interface ModelRecommendation {
  goal_type: string;
  recommended_model: string;
  reason: string;
  expected_cost_usd: number;
  expected_latency_ms: number;
  confidence_score: number;
  alternatives: Array<{ model: string; reason: string }>;
}

interface PolicySimulation {
  policy_name: string;
  description: string;
  expected_monthly_cost_usd: number;
  expected_avg_latency_ms: number;
  expected_success_rate: number;
  cost_change_percent: number;
  latency_change_percent: number;
}

interface ROIRanking {
  ranking: Array<{
    model_name: string;
    roi_score: number;
    total_calls: number;
    success_rate: number;
    total_cost_usd: number;
    p95_latency_ms: number;
  }>;
  hours_analyzed: number;
}

export const LLMControlCenter: React.FC = () => {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [roiRanking, setRoiRanking] = useState<ROIRanking | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [modelMetrics, setModelMetrics] = useState<ModelMetrics | null>(null);
  const [recommendation, setRecommendation] = useState<ModelRecommendation | null>(null);
  const [simulation, setSimulation] = useState<PolicySimulation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load overview data
  useEffect(() => {
    const loadOverview = async () => {
      try {
        const [overviewData, roiData] = await Promise.all([
          apiClient.get<OverviewData>('/llm/control/overview'),
          apiClient.get<ROIRanking>('/llm/control/model-roi-ranking')
        ]);
        setOverview(overviewData);
        setRoiRanking(roiData);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadOverview();
    const interval = setInterval(loadOverview, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Get model recommendation
  const getRecommendation = async (goalType: string, maxLatency?: number, maxCost?: number) => {
    try {
      const params = new URLSearchParams({ goal_type: goalType });
      if (maxLatency) params.append('max_latency_ms', maxLatency.toString());
      if (maxCost) params.append('max_cost_per_goal', maxCost.toString());

      const data = await apiClient.get<ModelRecommendation>(`/llm/control/recommend-model?${params}`);
      setRecommendation(data);
    } catch (err: any) {
      console.error('Recommendation error:', err);
    }
  };

  // Simulate policy
  const simulatePolicy = async (policyName: string, maxCost?: number, maxLatency?: number, minSuccess?: number) => {
    try {
      const params = new URLSearchParams({ policy_name: policyName });
      if (maxCost) params.append('max_cost_per_call', maxCost.toString());
      if (maxLatency) params.append('max_latency_ms', maxLatency.toString());
      if (minSuccess) params.append('min_success_rate', minSuccess.toString());

      const data = await apiClient.get<PolicySimulation>(`/llm/control/simulate-policy?${params}`);
      setSimulation(data);
    } catch (err: any) {
      console.error('Simulation error:', err);
    }
  };

  // Get detailed metrics for model
  const loadModelMetrics = async (modelName: string) => {
    try {
      const data = await apiClient.get<ModelMetrics>(`/llm/control/model-metrics/${modelName}?hours=24`);
      setModelMetrics(data);
    } catch (err: any) {
      console.error('Model metrics error:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-lg text-gray-600">Loading LLM Control Center...</div>
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-red-600">Error: {error}</div>
      </div>
    );
  }

  const trendColor = overview?.cost_trend === 'increasing' ? 'text-red-600' :
                     overview?.cost_trend === 'decreasing' ? 'text-green-600' :
                     'text-gray-600';

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Settings className="w-8 h-8 text-blue-600" />
            LLM Control Center
          </h1>
          <p className="text-gray-600 mt-1">
            Model selection governance and cost optimization
          </p>
        </div>
        <div className="flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-600" />
          <span className="text-sm text-gray-600">
            Policy compliance: {overview?.policy_compliance ? Math.round(overview.policy_compliance * 100) : 0}%
          </span>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="24h Cost"
          value={`$${overview?.total_cost_usd.toFixed(4) || '0.0000'}`}
          icon={<DollarSign className="w-5 h-5" />}
          trend={overview?.cost_trend}
          trendColor={trendColor}
        />
        <MetricCard
          title="Total Calls"
          value={overview?.total_calls.toLocaleString() || '0'}
          icon={<Activity className="w-5 h-5" />}
        />
        <MetricCard
          title="Success Rate"
          value={`${((overview?.overall_success_rate || 0) * 100).toFixed(1)}%`}
          icon={<CheckCircle className="w-5 h-5" />}
        />
        <MetricCard
          title="P95 Latency"
          value={`${Math.round(overview?.p95_latency_ms || 0)}ms`}
          icon={<Zap className="w-5 h-5" />}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ROI Ranking Table */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-600" />
            Model ROI Ranking
            <span className="text-sm font-normal text-gray-500">
              (last {roiRanking?.hours_analyzed || 24}h)
            </span>
          </h2>
          {roiRanking?.ranking && roiRanking.ranking.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Model</th>
                    <th className="text-right py-2">ROI Score</th>
                    <th className="text-right py-2">Success</th>
                    <th className="text-right py-2">Calls</th>
                    <th className="text-right py-2">Cost (24h)</th>
                  </tr>
                </thead>
                <tbody>
                  {roiRanking.ranking.map((model) => (
                    <tr
                      key={model.model_name}
                      className="border-b hover:bg-gray-50 cursor-pointer"
                      onClick={() => {
                        setSelectedModel(model.model_name);
                        loadModelMetrics(model.model_name);
                      }}
                    >
                      <td className="py-2 font-medium">{model.model_name}</td>
                      <td className="text-right text-green-600 font-semibold">
                        {model.roi_score.toFixed(2)}
                      </td>
                      <td className="text-right">{(model.success_rate * 100).toFixed(1)}%</td>
                      <td className="text-right">{model.total_calls.toLocaleString()}</td>
                      <td className="text-right">${model.total_cost_usd.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              No data available yet. Metrics will populate as LLM calls are made.
            </div>
          )}
        </div>

        {/* Model Recommendation Engine */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            Model Recommendation
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Goal Type
              </label>
              <select
                className="w-full border rounded-lg px-3 py-2"
                onChange={(e) => getRecommendation(e.target.value)}
              >
                <option value="">Select goal type...</option>
                <option value="achievable">Achievable</option>
                <option value="continuous">Continuous</option>
                <option value="directional">Directional</option>
                <option value="exploratory">Exploratory</option>
              </select>
            </div>

            {recommendation && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg space-y-2">
                <div className="font-semibold text-lg">
                  Recommended: {recommendation.recommended_model}
                </div>
                <div className="text-sm text-gray-700">
                  {recommendation.reason}
                </div>
                <div className="grid grid-cols-2 gap-4 mt-3 text-sm">
                  <div>
                    <span className="text-gray-600">Expected Cost:</span>{' '}
                    <span className="font-semibold">${recommendation.expected_cost_usd.toFixed(4)}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Expected Latency:</span>{' '}
                    <span className="font-semibold">{Math.round(recommendation.expected_latency_ms)}ms</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Confidence:</span>{' '}
                    <span className="font-semibold">{Math.round(recommendation.confidence_score * 100)}%</span>
                  </div>
                </div>
                {recommendation.alternatives.length > 0 && (
                  <div className="mt-3">
                    <div className="text-sm font-medium text-gray-700 mb-2">Alternatives:</div>
                    {recommendation.alternatives.map((alt) => (
                      <div key={alt.model} className="text-sm text-gray-600">
                        • {alt.model}: {alt.reason}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Policy Simulation */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-purple-600" />
            Policy Simulation
          </h2>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Cost per Call ($)
                </label>
                <input
                  type="number"
                  step="0.0001"
                  className="w-full border rounded-lg px-3 py-2"
                  placeholder="e.g. 0.01"
                  id="maxCost"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Latency (ms)
                </label>
                <input
                  type="number"
                  className="w-full border rounded-lg px-3 py-2"
                  placeholder="e.g. 5000"
                  id="maxLatency"
                />
              </div>
            </div>
            <button
              onClick={() => {
                const maxCost = parseFloat((document.getElementById('maxCost') as HTMLInputElement)?.value || '0');
                const maxLatency = parseInt((document.getElementById('maxLatency') as HTMLInputElement)?.value || '0');
                simulatePolicy('custom_policy', maxCost || undefined, maxLatency || undefined);
              }}
              className="w-full bg-purple-600 text-white rounded-lg py-2 hover:bg-purple-700 transition"
            >
              Simulate Policy
            </button>

            {simulation && (
              <div className="mt-4 p-4 bg-purple-50 rounded-lg space-y-2">
                <div className="font-medium">{simulation.description}</div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Monthly Cost:</span>{' '}
                    <span className="font-semibold">${simulation.expected_monthly_cost_usd.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Avg Latency:</span>{' '}
                    <span className="font-semibold">{Math.round(simulation.expected_avg_latency_ms)}ms</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Success Rate:</span>{' '}
                    <span className="font-semibold">{(simulation.expected_success_rate * 100).toFixed(1)}%</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm pt-2 border-t">
                  <div className={simulation.cost_change_percent < 0 ? 'text-green-600' : 'text-red-600'}>
                    Cost: {simulation.cost_change_percent > 0 ? '+' : ''}{simulation.cost_change_percent.toFixed(1)}%
                  </div>
                  <div className={simulation.latency_change_percent < 0 ? 'text-green-600' : 'text-red-600'}>
                    Latency: {simulation.latency_change_percent > 0 ? '+' : ''}{simulation.latency_change_percent.toFixed(1)}%
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Selected Model Details */}
        {modelMetrics && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-600" />
              {selectedModel} - Detailed Metrics
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Provider:</span>{' '}
                  <span className="font-medium">{modelMetrics.provider}</span>
                </div>
                <div>
                  <span className="text-gray-600">Total Calls (24h):</span>{' '}
                  <span className="font-medium">{modelMetrics.total_calls.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-gray-600">Success Rate:</span>{' '}
                  <span className="font-medium">{(modelMetrics.success_rate * 100).toFixed(1)}%</span>
                </div>
                <div>
                  <span className="text-gray-600">Avg Latency:</span>{' '}
                  <span className="font-medium">{Math.round(modelMetrics.avg_latency_ms)}ms</span>
                </div>
                <div>
                  <span className="text-gray-600">P95 Latency:</span>{' '}
                  <span className="font-medium">{Math.round(modelMetrics.p95_latency_ms)}ms</span>
                </div>
                <div>
                  <span className="text-gray-600">P99 Latency:</span>{' '}
                  <span className="font-medium">{Math.round(modelMetrics.p99_latency_ms)}ms</span>
                </div>
                <div>
                  <span className="text-gray-600">Total Cost (24h):</span>{' '}
                  <span className="font-medium">${modelMetrics.total_cost_usd.toFixed(4)}</span>
                </div>
                <div>
                  <span className="text-gray-600">Cost per 1K Tokens:</span>{' '}
                  <span className="font-medium">${modelMetrics.cost_per_1k_tokens.toFixed(4)}</span>
                </div>
                {modelMetrics.cost_per_successful_goal && (
                  <div>
                    <span className="text-gray-600">Cost per Successful Goal:</span>{' '}
                    <span className="font-medium">${modelMetrics.cost_per_successful_goal.toFixed(4)}</span>
                  </div>
                )}
              </div>

              {Object.keys(modelMetrics.success_rate_by_goal_type).length > 0 && (
                <div className="pt-4 border-t">
                  <div className="text-sm font-medium text-gray-700 mb-2">Success Rate by Goal Type:</div>
                  {Object.entries(modelMetrics.success_rate_by_goal_type).map(([goalType, rate]) => (
                    <div key={goalType} className="flex justify-between text-sm py-1">
                      <span className="text-gray-600">{goalType}</span>
                      <span className="font-medium">{(rate * 100).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Slow Calls Warning */}
      {overview && overview.slow_calls_count > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-600" />
          <div>
            <div className="font-medium text-yellow-800">
              {overview.slow_calls_count} slow calls detected in the last 24 hours
            </div>
            <div className="text-sm text-yellow-700">
              Consider reviewing model selection or increasing timeout thresholds
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

interface MetricCardProps {
  title: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: string;
  trendColor?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, icon, trend, trendColor }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <div className="flex items-center justify-between">
      <div className="text-gray-600 text-sm font-medium">{title}</div>
      {icon}
    </div>
    <div className="mt-2 flex items-center gap-2">
      <div className="text-2xl font-bold">{value}</div>
      {trend && (
        <div className={`text-sm font-medium ${trendColor}`}>
          {trend === 'increasing' && '↑'}
          {trend === 'decreasing' && '↓'}
          {trend === 'stable' && '→'}
        </div>
      )}
    </div>
  </div>
);

export default LLMControlCenter;
