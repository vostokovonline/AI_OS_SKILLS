/**
 * v2 UI - API Client
 *
 * Handles communication with AI-OS backend
 * Implements the UI → System event contract
 */

import axios, { AxiosInstance } from 'axios';
import {
  GraphQuery,
  GraphResponse,
  ExecuteActionRequest,
  ExecuteActionResponse,
  UIEvent,
  TimelineSnapshot,
  InspectorContext,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class AOSClient {
  private client: AxiosInstance;

  constructor(baseURL: string = API_BASE_URL) {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('[API] Error:', error.response?.data || error.message);
        throw error;
      }
    );
  }

  /**
   * Query the goal/agent/skill graph
   */
  async queryGraph(query: GraphQuery): Promise<GraphResponse> {
    const response = await this.client.get<GraphResponse>('/graph', {
      params: query,
    });
    return response.data;
  }

  /**
   * Fetch V1 goals list (for integration with legacy backend)
   */
  async fetchV1Goals(): Promise<any> {
    const response = await this.client.get('/goals/list');
    return response.data;
  }

  /**
   * Fetch V1 goal tree
   */
  async fetchV1GoalTree(goalId: string): Promise<any> {
    const response = await this.client.get(`/goals/${goalId}/tree`);
    return response.data;
  }

  /**
   * Fetch artifacts for a goal
   */
  async fetchGoalArtifacts(goalId: string): Promise<any> {
    const response = await this.client.get(`/goals/${goalId}/artifacts`);
    return response.data;
  }

  /**
   * Get artifact details
   */
  async getArtifact(artifactId: string): Promise<any> {
    const response = await this.client.get(`/artifacts/${artifactId}`);
    return response.data;
  }

  /**
   * Get artifact file content
   */
  async getArtifactContent(artifactId: string): Promise<any> {
    const response = await this.client.get(`/artifacts/${artifactId}/content`);
    return response.data;
  }

  /**
   * Check goal conflicts
   */
  async checkConflicts(goalId: string): Promise<any> {
    const response = await this.client.post(`/goals/${goalId}/check-conflicts`);
    return response.data;
  }

  /**
   * Get all conflicts for user
   */
  async getConflicts(userId: string): Promise<any> {
    const response = await this.client.get(`/goals/${userId}/conflicts`);
    return response.data;
  }

  /**
   * Resolve a conflict
   */
  async resolveConflict(conflictId: string, resolution: string): Promise<any> {
    const response = await this.client.post(`/conflicts/${conflictId}/resolve`, {
      resolution
    });
    return response.data;
  }

  /**
   * Get contextual memory
   */
  async getContextualMemory(userId: string): Promise<any> {
    const response = await this.client.get(`/personality/${userId}/contextual-memory`);
    return response.data;
  }

  /**
   * Update contextual memory
   */
  async updateContextualMemory(userId: string, data: any): Promise<any> {
    const response = await this.client.put(`/personality/${userId}/contextual-memory`, data);
    return response.data;
  }

  /**
   * Get personality snapshots
   */
  async getSnapshots(userId: string, limit: number = 10): Promise<any> {
    const response = await this.client.get(`/personality/${userId}/snapshots`, {
      params: { limit }
    });
    return response.data;
  }

  /**
   * Create personality snapshot
   */
  async createSnapshot(userId: string, reason: string = 'manual'): Promise<any> {
    const response = await this.client.post(`/personality/${userId}/snapshot`, null, {
      params: { reason }
    });
    return response.data;
  }

  /**
   * Rollback to snapshot version
   */
  async rollbackToSnapshot(userId: string, snapshotVersion: number): Promise<any> {
    const response = await this.client.post(`/personality/${userId}/rollback/${snapshotVersion}`);
    return response.data;
  }

  /**
   * Get a specific node by ID
   */
  async getNode(nodeId: string): Promise<any> {
    const response = await this.client.get(`/nodes/${nodeId}`);
    return response.data;
  }

  /**
   * Get inspector context for a node
   */
  async getInspectorContext(nodeId: string): Promise<InspectorContext> {
    const response = await this.client.get(`/nodes/${nodeId}/inspector`);
    return response.data;
  }

  /**
   * Decompose a goal into sub-goals
   */
  async decomposeGoal(goalId: string, maxDepth: number = 1): Promise<any> {
    const response = await this.client.post(`/goals/${goalId}/decompose`, {
      max_depth: maxDepth,
    });
    return response.data;
  }

  /**
   * Execute an action on a node
   */
  async executeAction(request: ExecuteActionRequest): Promise<ExecuteActionResponse> {
    const response = await this.client.post<ExecuteActionResponse>(
      `/nodes/${request.nodeId}/execute`,
      {
        action: request.action,
        context: request.context,
      }
    );
    return response.data;
  }

  /**
   * Request a simulation
   */
  async simulate(nodeId: string, whatIf?: any): Promise<any> {
    const response = await this.client.post(`/nodes/${nodeId}/simulate`, {
      what_if: whatIf,
    });
    return response.data;
  }

  /**
   * Get timeline snapshot
   */
  async getTimelineSnapshot(timestamp?: string): Promise<TimelineSnapshot[]> {
    const response = await this.client.get<TimelineSnapshot[]>('/timeline', {
      params: timestamp ? { at: timestamp } : undefined,
    });
    return response.data;
  }

  /**
   * Generic GET request for any endpoint
   */
  async get<T = any>(url: string, params?: any): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  /**
   * Generic POST request for any endpoint
   */
  async post<T = any>(url: string, data?: any): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  /**
   * Update constraints
   */
  async updateConstraints(constraints: {
    ethics?: string[];
    budget?: number;
    timeHorizon?: string;
  }): Promise<any> {
    const response = await this.client.put('/constraints', constraints);
    return response.data;
  }

  /**
   * Override a decision
   */
  async overrideDecision(
    decisionId: string,
    override: {
      action: 'block' | 'force' | 'modify';
      reason: string;
    }
  ): Promise<any> {
    const response = await this.client.post(`/decisions/${decisionId}/override`, override);
    return response.data;
  }

  /**
   * Send a UI event to the system
   */
  async sendEvent(event: UIEvent): Promise<any> {
    const response = await this.client.post('/ui/events', event);
    return response.data;
  }

  /**
   * Subscribe to server-sent events for real-time updates
   */
  subscribeToUpdates(callback: (event: any) => void): EventSource {
    const eventSource = new EventSource(`${API_BASE_URL}/ui/stream`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        callback(data);
      } catch (error) {
        console.error('[API] Failed to parse SSE event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[API] SSE connection error:', error);
    };

    return eventSource;
  }

  // ========================================================================
  // EMOTIONAL LAYER API
  // ========================================================================

  /**
   * Get current emotional state for a user
   */
  async getCurrentEmotionalState(userId: string): Promise<any> {
    const response = await this.client.get(`/emotional/state/${userId}`);
    return response.data;
  }

  /**
   * Get emotional state history
   */
  async getEmotionalHistory(userId: string, limit: number = 100): Promise<any[]> {
    try {
      const response = await this.client.get(`/emotional/history/${userId}`, {
        params: { limit }
      });

      // Ensure we always return an array
      if (Array.isArray(response.data)) {
        return response.data;
      }

      // If API returns an object with a data property or similar
      if (response.data && typeof response.data === 'object') {
        // Check for common response formats
        if (Array.isArray(response.data.data)) {
          return response.data.data;
        }
        if (Array.isArray(response.data.history)) {
          return response.data.history;
        }
        if (Array.isArray(response.data.states)) {
          return response.data.states;
        }
      }

      console.warn('[API] getEmotionalHistory returned non-array data:', response.data);
      return [];
    } catch (error) {
      console.error('[API] Failed to fetch emotional history:', error);
      return [];
    }
  }

  /**
   * Get emotional influence for decision-making
   */
  async getEmotionalInfluence(
    userId: string,
    signals: any
  ): Promise<any> {
    const response = await this.client.post(`/emotional/influence/${userId}`, signals);
    return response.data;
  }

  /**
   * Get emotional context as agent-friendly dict
   */
  async getEmotionalContext(
    userId: string,
    signals: any
  ): Promise<any> {
    const response = await this.client.post(`/emotional/context/${userId}`, signals);
    return response.data;
  }

  // ========================================================================
  // DECOMPOSITION API
  // ========================================================================

  /**
   * Start decomposition by asking a question
   */
  async askDecomposition(req: {
    goal_id: string;
    question_text: string;
    question_type?: string;
    initiated_by?: string;
  }): Promise<any> {
    const response = await this.client.post('/decomposition/ask', req);
    return response.data;
  }

  /**
   * Get active decomposition session for a goal
   */
  async getActiveDecompositionSession(goalId: string): Promise<any> {
    const response = await this.client.get('/decomposition/session/active', {
      params: { goal_id: goalId }
    });
    return response.data;
  }

  /**
   * Submit answer to a decomposition question
   */
  async submitDecompositionAnswer(req: {
    question_id: string;
    answer_text: string;
    answered_by?: string;
  }): Promise<any> {
    const response = await this.client.post('/decomposition/answer', req);
    return response.data;
  }

  /**
   * Get decomposition session with all questions and answers
   */
  async getDecompositionSession(sessionId: string): Promise<any> {
    const response = await this.client.get(`/decomposition/session/${sessionId}`);
    return response.data;
  }

  /**
   * Get all pending goals for decomposition
   */
  async getPendingGoals(): Promise<any> {
    const response = await this.client.get('/goals/list');
    return response.data;
  }

  /**
   * Decompose goal from completed session answers
   */
  async decomposeFromAnswers(sessionId: string): Promise<any> {
    const response = await this.client.post(`/decomposition/${sessionId}/decompose`);
    return response.data;
  }

  // ========================================================================
  // GOAL CREATION API
  // ========================================================================

  /**
   * Create a new goal
   */
  async createGoal(req: {
    title: string;
    description?: string;
    goal_type?: string;
    is_atomic?: boolean;
    domain?: string;
    priority?: string;
  }): Promise<any> {
    const response = await this.client.post('/goals/create', req);
    return response.data;
  }

  /**
   * Execute a goal
   */
  async executeGoal(goalId: string): Promise<any> {
    const response = await this.client.post(`/goals/${goalId}/execute`);
    return response.data;
  }

  /**
   * Get goal status
   */
  async getGoalStatus(goalId: string): Promise<any> {
    const response = await this.client.get(`/goals/${goalId}/status`);
    return response.data;
  }

  /**
   * Mutate goal (update properties)
   */
  async mutateGoal(goalId: string, mutation: {
    action: string;
    params?: any;
  }): Promise<any> {
    const response = await this.client.post(`/goals/${goalId}/mutate`, mutation);
    return response.data;
  }

  // ========================================================================
  // SEMANTIC LAYER API (v7.x)
  // ========================================================================

  /**
   * Get system metrics (observability)
   */
  async getSystemMetrics(): Promise<any> {
    const response = await this.client.get('/metrics/system');
    return response.data;
  }

  /**
   * Get TS Router status
   */
  async getRouterStatus(): Promise<any> {
    const response = await this.client.get('/semantic/router/status');
    return response.data;
  }

  /**
   * Get policy learning status
   */
  async getPolicyStatus(): Promise<any> {
    const response = await this.client.get('/semantic/policy/status');
    return response.data;
  }

  /**
   * Set system goal (balanced, maximize_accuracy, low_latency, minimize_cost, reliable)
   */
  async setSystemGoal(goal: string): Promise<any> {
    const response = await this.client.post('/semantic/goal/set', { goal });
    return response.data;
  }
}

// Singleton instance
export const apiClient = new AOSClient();
