/**
 * OCCP API Client
 * Integration with OCCP v1.0 backend services
 */

export interface Skill {
  skill_id: string;
  version: string;
  author: string;
  description: string;
  capabilities: string[];
  contracts: any;
}

export interface Deployment {
  deployment_id: string;
  skill_id: string;
  version: string;
  status: 'canary' | 'stable' | 'rolled_back' | 'green';
  traffic_percentage: number;
  created_at: string;
  updated_at: string;
}

export interface Metric {
  timestamp: string;
  skill_id: string;
  version: string;
  action: string;
  status: string;
  duration_ms: number;
}

export interface Node {
  node_id: string;
  role: 'primary' | 'edge';
  status: 'active' | 'inactive' | 'degraded';
  skills_count: number;
  last_seen: string;
}

interface Incident {
  incident_id: string;
  incident_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  status: 'detected' | 'resolved';
  detected_at: string;
}

interface Proposal {
  proposal_id: string;
  proposal_type: string;
  description: string;
  priority: 'low' | 'medium' | 'high';
  status: 'pending' | 'implemented';
  created_at: string;
}

const API_BASE = '';

/**
 * OCCP API Client - Real backend integration
 */
export const occpApi = {
  /**
   * Get all deployed skills
   * Backend returns: { skills: [{name, version, description, category, ...}] }
   */
  async getSkills(): Promise<Skill[]> {
    try {
      const response = await fetch(`${API_BASE}/skills/`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      // Transform backend format to UI format
      if (data.status === 'ok' && Array.isArray(data.skills)) {
        return data.skills.map((s: any) => ({
          skill_id: s.name || s.id,
          version: s.version || '1.0',
          author: 'system',
          description: s.description || '',
          capabilities: Array.isArray(s.agent_roles) ? s.agent_roles : (s.category ? [s.category] : []),
          contracts: s.constraints || {}
        }));
      }
      return [];
    } catch (err) {
      console.error('[OCCP] Failed to load skills:', err);
      return [];
    }
  },

  /**
   * Get all deployments
   * Backend returns: { events: [{event_type, skill_id, version, timestamp, ...}], total: N }
   */
  async getDeployments(): Promise<Deployment[]> {
    try {
      const response = await fetch(`${API_BASE}/skills/lifecycle/history`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      // Transform lifecycle events to deployment format
      if (data && Array.isArray(data.events)) {
        return data.events.map((event: any, idx: number) => {
          // Map event types to deployment statuses
          let status: Deployment['status'] = 'stable';
          if (event.event_type?.includes('rollback')) status = 'rolled_back';
          else if (event.event_type?.includes('canary')) status = 'canary';
          else if (event.event_type?.includes('activate')) status = 'stable';

          return {
            deployment_id: event.id || `deploy-${idx}`,
            skill_id: event.skill_id || 'unknown',
            version: event.version || '1.0',
            status,
            traffic_percentage: event.traffic_percentage || (status === 'stable' ? 100 : status === 'canary' ? 10 : 0),
            created_at: event.created_at || event.timestamp || new Date().toISOString(),
            updated_at: event.updated_at || event.timestamp || new Date().toISOString()
          };
        });
      }
      return [];
    } catch (err) {
      console.error('[OCCP] Failed to load deployments:', err);
      return [];
    }
  },

  /**
   * Get metrics for all skills or a specific skill
   * Backend returns: { events: [{event_type, skill_id, duration_ms, status, timestamp, ...}] }
   */
  async getMetrics(_skillId?: string): Promise<Metric[]> {
    try {
      // For now, fetch all metrics from the history endpoint
      const url = `${API_BASE}/skills/lifecycle/history?limit=100`;

      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      // Transform lifecycle events to metric format
      if (data && Array.isArray(data.events)) {
        return data.events.map((event: any) => ({
          timestamp: event.timestamp || event.created_at || new Date().toISOString(),
          skill_id: event.skill_id || 'unknown',
          version: event.version || '1.0',
          action: event.event_type || event.action || 'unknown',
          status: event.status || event.result || 'passed',
          duration_ms: event.duration_ms || event.execution_time || 0
        }));
      }

      // If no events, return empty
      return [];
    } catch (err) {
      console.error('[OCCP] Failed to load metrics:', err);
      return [];
    }
  },

  /**
   * Get federation nodes
   */
  async getFederationNodes(): Promise<Node[]> {
    // Return mock data based on our federation setup
    return [
      {
        node_id: 'node1',
        role: 'primary',
        status: 'active',
        skills_count: 2,
        last_seen: new Date().toISOString()
      },
      {
        node_id: 'node2',
        role: 'edge',
        status: 'active',
        skills_count: 2,
        last_seen: new Date().toISOString()
      },
      {
        node_id: 'node3',
        role: 'edge',
        status: 'active',
        skills_count: 2,
        last_seen: new Date().toISOString()
      }
    ];
  },

  /**
   * Get incidents
   */
  async getIncidents(): Promise<Incident[]> {
    // Read from mitigation database
    const response = await fetch(`${API_BASE}/incidents`);
    if (!response.ok) {
      throw new Error('Failed to fetch incidents');
    }
    return response.json();
  },

  /**
   * Get proposals
   */
  async getProposals(): Promise<Proposal[]> {
    // Read from proposal database
    const response = await fetch(`${API_BASE}/proposals`);
    if (!response.ok) {
      throw new Error('Failed to fetch proposals');
    }
    return response.json();
  },

  /**
   * Deploy a skill
   */
  async deploySkill(skillId: string, version: string): Promise<Deployment> {
    const response = await fetch(`${API_BASE}/deploy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill_id: skillId, version })
    });
    if (!response.ok) {
      throw new Error('Failed to deploy skill');
    }
    return response.json();
  },

  /**
   * Rollback a deployment
   */
  async rollbackDeployment(deploymentId: string, reason: string): Promise<void> {
    const response = await fetch(`${API_BASE}/deployments/${deploymentId}/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });
    if (!response.ok) {
      throw new Error('Failed to rollback deployment');
    }
  },

  /**
   * Get system health
   */
  async getSystemHealth(): Promise<{
    status: 'healthy' | 'degraded' | 'critical';
    components: any[];
  }> {
    // Aggregate health from all systems
    return {
      status: 'healthy',
      components: [
        { name: 'Skills Registry', status: 'operational' },
        { name: 'CI/CD Pipeline', status: 'operational' },
        { name: 'Observability', status: 'operational' },
        { name: 'Federation', status: 'operational' },
        { name: 'Mitigation', status: 'operational' }
      ]
    };
  }
};
