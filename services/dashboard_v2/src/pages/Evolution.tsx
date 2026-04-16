/**
 * Evolution Dashboard - Self-Evolving AI OS Monitoring
 *
 * Shows:
 * - Evolution status and metrics
 * - Capability gaps
 * - Skill lifecycle
 * - Learning pipeline status
 * - Control panel
 */

import { useEffect, useState } from 'react';
import { 
  Brain, 
  Zap, 
  Target, 
  Activity,
  Settings,
  Play,
  CheckCircle, 
  XCircle,
  AlertTriangle, 
  Clock,
  Gauge,
  ChevronRight,
  TrendingUp
} from 'lucide-react';

interface EvolutionMetrics {
  capability_gaps: number;
  skills_active: number;
  skills_new: number;
  last_evolution: string;
  evolution_rate: number;
}

interface CapabilityGap {
  gap_id: string;
  capability: string;
  priority: 'high' | 'medium' | 'low';
  status: 'detected' | 'resolving' | 'resolved';
  occurrences: number;
}

interface SkillPerformance {
  skill_id: string;
  executions: number;
  success_rate: number;
  latency_ms: number;
  status: 'active' | 'new' | 'deprecated';
}

interface LifecycleEvent {
  skill_id: string;
  status: string;
  timestamp: string;
  reason: string;
}

interface LearningPipeline {
  traces_total: number;
  success_rate: number;
  top_skills: { skill: string; count: number }[];
}

const EvolutionDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<EvolutionMetrics | null>(null);
  const [gaps, setGaps] = useState<CapabilityGap[]>([]);
  const [skills, setSkills] = useState<SkillPerformance[]>([]);
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [pipeline, setPipeline] = useState<LearningPipeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoEvolution, setAutoEvolution] = useState(true);
  const [explorationRate, setExplorationRate] = useState(15);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const loadData = async () => {
    try {
      // Load metrics (unused for now but available)
      await fetch('/api/capability/evolution/status');
      
      // Load capability gaps
      const gapsRes = await fetch('/api/capability/gaps');
      const gapsData = await gapsRes.json();
      
      // Load lifecycle history
      const historyRes = await fetch('/api/skills/lifecycle/history?limit=20');
      const historyData = await historyRes.json();
      
      // Load trace stats
      const statsRes = await fetch('/api/trace/stats');
      const statsData = await statsRes.json();
      
      // Load skills list
      const skillsRes = await fetch('/api/skills/list');
      const skillsData = await skillsRes.json();

      // Parse metrics
      const traceStats = statsData?.trace_stats || {};
      const skillUsage = traceStats?.skill_usage || {};
      
      setMetrics({
        capability_gaps: gapsData?.gaps_count || 0,
        skills_active: skillsData?.skills?.length || 0,
        skills_new: historyData?.total || 0,
        last_evolution: historyData?.events?.[0]?.timestamp || 'Never',
        evolution_rate: historyData?.total > 0 ? (historyData.total / 24) : 0
      });

      // Parse gaps
      const parsedGaps: CapabilityGap[] = (gapsData?.gaps || []).slice(0, 10).map((g: any) => ({
        gap_id: g.gap_id,
        capability: g.required_capability?.name || 'unknown',
        priority: g.priority || 'medium',
        status: g.status || 'detected',
        occurrences: 1
      }));
      setGaps(parsedGaps);

      // Parse skills from usage
      const parsedSkills: SkillPerformance[] = Object.entries(skillUsage).map(([skill, count]) => ({
        skill_id: skill,
        executions: count as number,
        success_rate: 1.0,
        latency_ms: 500,
        status: 'active' as const
      }));
      setSkills(parsedSkills);

      // Parse events
      const parsedEvents: LifecycleEvent[] = (historyData?.events || []).slice(0, 10).map((e: any) => ({
        skill_id: e.skill_id,
        status: e.to_status,
        timestamp: e.timestamp,
        reason: e.reason
      }));
      setEvents(parsedEvents);

      // Parse pipeline
      setPipeline({
        traces_total: traceStats?.total_traces || 0,
        success_rate: 1.0,
        top_skills: Object.entries(skillUsage).map(([skill, count]) => ({ 
          skill, 
          count: count as number 
        })).sort((a, b) => b.count - a.count).slice(0, 5)
      });

      setLastUpdate(new Date());
    } catch (err) {
      console.error('Failed to load evolution data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const runEvolution = async () => {
    try {
      await fetch('/api/capability/evolution/run', { method: 'POST' });
      loadData();
    } catch (err) {
      console.error('Evolution failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading Evolution Dashboard...</div>
      </div>
    );
  }

  const hasGaps = (metrics?.capability_gaps || 0) > 0;

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Brain className="w-8 h-8 text-purple-600" />
            Evolution Dashboard
          </h1>
          <p className="text-gray-500 mt-1">
            Self-Evolving AI OS Monitor • Last updated: {lastUpdate.toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-green-500 rounded-full animate-pulse" />
          <span className="text-sm text-gray-600">Live</span>
        </div>
      </div>

      {/* Main Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Capability Gaps"
          value={metrics?.capability_gaps || 0}
          icon={AlertTriangle}
          color={hasGaps ? "red" : "green"}
          subtitle="Needs attention"
        />
        <MetricCard
          title="Active Skills"
          value={metrics?.skills_active || 0}
          icon={Zap}
          color="blue"
          subtitle="In registry"
        />
        <MetricCard
          title="New This Session"
          value={metrics?.skills_new || 0}
          icon={Target}
          color="purple"
          subtitle="Generated"
        />
        <MetricCard
          title="Evolution Rate"
          value={`${(metrics?.evolution_rate || 0).toFixed(1)}/hr`}
          icon={TrendingUp}
          color="green"
          subtitle="Learning speed"
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Capability Gaps */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            Capability Gaps
            <span className="text-sm font-normal text-gray-500">({gaps.length})</span>
          </h2>
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {gaps.length === 0 ? (
              <div className="text-gray-500 text-center py-8">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-2" />
                No capability gaps detected!
              </div>
            ) : (
              gaps.map((gap) => (
                <div key={gap.gap_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${
                      gap.priority === 'high' ? 'bg-red-500' : 
                      gap.priority === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                    }`} />
                    <span className="font-medium">{gap.capability}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span className={`px-2 py-1 rounded text-xs ${
                      gap.priority === 'high' ? 'bg-red-100 text-red-700' : 
                      gap.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'
                    }`}>
                      {gap.priority}
                    </span>
                    <ChevronRight className="w-4 h-4" />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Learning Pipeline */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-500" />
            Learning Pipeline
          </h2>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Total Traces</span>
              <span className="font-bold">{pipeline?.traces_total || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Success Rate</span>
              <span className="font-bold text-green-600">
                {((pipeline?.success_rate || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div>
              <span className="text-gray-600 block mb-2">Top Skills</span>
              <div className="space-y-2">
                {(pipeline?.top_skills || []).map((skill, i) => (
                  <div key={skill.skill} className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold">
                      {i + 1}
                    </div>
                    <span className="flex-1">{skill.skill}</span>
                    <span className="text-gray-500">{skill.count}x</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Skill Performance */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Gauge className="w-5 h-5 text-green-500" />
          Skill Performance
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left py-3 px-4">Skill</th>
                <th className="text-right py-3 px-4">Executions</th>
                <th className="text-right py-3 px-4">Success Rate</th>
                <th className="text-right py-3 px-4">Latency</th>
                <th className="text-right py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {skills.map((skill) => (
                <tr key={skill.skill_id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4 font-medium">{skill.skill_id}</td>
                  <td className="py-3 px-4 text-right">{skill.executions}</td>
                  <td className="py-3 px-4 text-right">
                    <span className={`font-bold ${
                      skill.success_rate >= 0.9 ? 'text-green-600' : 
                      skill.success_rate >= 0.7 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {(skill.success_rate * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">{skill.latency_ms}ms</td>
                  <td className="py-3 px-4 text-right">
                    <span className={`px-2 py-1 rounded text-xs ${
                      skill.status === 'active' ? 'bg-green-100 text-green-700' :
                      skill.status === 'new' ? 'bg-purple-100 text-purple-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {skill.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Events */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Clock className="w-5 h-5 text-purple-500" />
          Recent Lifecycle Events
        </h2>
        <div className="space-y-3 max-h-48 overflow-y-auto">
          {events.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              No events yet
            </div>
          ) : (
            events.map((event, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {event.status === 'active' ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : event.status === 'failed' ? (
                  <XCircle className="w-5 h-5 text-red-500" />
                ) : (
                  <Activity className="w-5 h-5 text-blue-500" />
                )}
                <div className="flex-1">
                  <span className="font-medium">{event.skill_id}</span>
                  <span className="text-gray-500 text-sm ml-2">{event.reason}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Control Panel */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Settings className="w-5 h-5 text-gray-500" />
          Control Panel
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <div className="font-medium">Auto-Evolution</div>
              <div className="text-sm text-gray-500">Automatically resolve gaps</div>
            </div>
            <button
              onClick={() => setAutoEvolution(!autoEvolution)}
              className={`w-12 h-6 rounded-full transition-colors ${
                autoEvolution ? 'bg-green-500' : 'bg-gray-300'
              }`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transform transition-transform ${
                autoEvolution ? 'translate-x-6' : 'translate-x-0.5'
              }`} />
            </button>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <div className="font-medium">Exploration Rate</div>
              <div className="text-sm text-gray-500">Try new skills</div>
            </div>
            <select
              value={explorationRate}
              onChange={(e) => setExplorationRate(Number(e.target.value))}
              className="border rounded px-2 py-1"
            >
              <option value={5}>5%</option>
              <option value={10}>10%</option>
              <option value={15}>15%</option>
              <option value={25}>25%</option>
            </select>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <div className="font-medium">Actions</div>
              <div className="text-sm text-gray-500">Manual controls</div>
            </div>
            <button
              onClick={runEvolution}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
            >
              <Play className="w-4 h-4" />
              Run
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Metric Card Component
const MetricCard: React.FC<{
  title: string;
  value: string | number;
  icon: React.FC<{ className?: string }>;
  color: 'blue' | 'red' | 'green' | 'purple' | 'yellow';
  subtitle: string;
}> = ({ title, value, icon: Icon, color, subtitle }) => {
  const colors = {
    blue: 'bg-blue-50 border-blue-200 text-blue-600',
    red: 'bg-red-50 border-red-200 text-red-600',
    green: 'bg-green-50 border-green-200 text-green-600',
    purple: 'bg-purple-50 border-purple-200 text-purple-600',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-600'
  };

  return (
    <div className={`bg-white rounded-lg shadow p-6 border-l-4 ${colors[color].split(' ')[0].replace('bg-', 'border-')}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-500 text-sm">{title}</span>
        <Icon className={`w-5 h-5 ${colors[color].split(' ')[2]}`} />
      </div>
      <div className={`text-3xl font-bold ${colors[color].split(' ')[2]}`}>
        {value}
      </div>
      <div className="text-gray-400 text-sm mt-1">{subtitle}</div>
    </div>
  );
};

export default EvolutionDashboard;
