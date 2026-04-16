/**
 * Goal Creation Modal
 * Form to create new goals directly from the dashboard
 */

import React, { useState } from 'react';
import { Plus, X, Zap, Target, Layers, AlertCircle } from 'lucide-react';
import { apiClient } from '../../api/client';

interface GoalCreationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (goalId: string) => void;
}

export const GoalCreationModal: React.FC<GoalCreationModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    goal_type: 'achievable',
    is_atomic: false,
    domain: 'general',
    priority: 'normal'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const goalTypes = [
    { value: 'achievable', label: 'Achievable', icon: Target, description: 'Clear success criteria' },
    { value: 'continuous', label: 'Continuous', icon: Zap, description: 'Ongoing improvement' },
    { value: 'directional', label: 'Directional', icon: Layers, description: 'Values and principles' },
    { value: 'exploratory', label: 'Exploratory', icon: AlertCircle, description: 'Research and discovery' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await apiClient.createGoal({
        title: formData.title,
        description: formData.description,
        goal_type: formData.goal_type,
        is_atomic: formData.is_atomic,
        domain: formData.domain,
        priority: formData.priority
      });
      
      if (onSuccess && result?.id) {
        onSuccess(result.id);
      }
      
      setFormData({
        title: '',
        description: '',
        goal_type: 'achievable',
        is_atomic: false,
        domain: 'general',
        priority: 'normal'
      });
      
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create goal');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-600 rounded-lg">
              <Plus size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Create New Goal</h2>
              <p className="text-sm text-gray-400">Define a new objective for the system</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X size={20} className="text-gray-400" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-3 bg-red-900/30 border border-red-500 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Goal Title *
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-purple-500"
              placeholder="e.g., Optimize database queries"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-purple-500 h-24 resize-none"
              placeholder="Describe what this goal aims to achieve..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Goal Type
            </label>
            <div className="grid grid-cols-2 gap-2">
              {goalTypes.map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setFormData({ ...formData, goal_type: type.value })}
                  className={`
                    p-3 rounded-lg border text-left transition-all
                    ${formData.goal_type === type.value
                      ? 'bg-purple-900/30 border-purple-500 text-white'
                      : 'bg-gray-700 border-gray-600 text-gray-300 hover:border-gray-500'
                    }
                  `}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <type.icon size={16} className={formData.goal_type === type.value ? 'text-purple-400' : 'text-gray-400'} />
                    <span className="font-medium text-sm">{type.label}</span>
                  </div>
                  <p className="text-xs text-gray-500">{type.description}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Domain
              </label>
              <select
                value={formData.domain}
                onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-purple-500"
              >
                <option value="general">General</option>
                <option value="programming">Programming</option>
                <option value="research">Research</option>
                <option value="operations">Operations</option>
                <option value="analytics">Analytics</option>
              </select>
            </div>

            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Priority
              </label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-purple-500"
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg">
            <input
              type="checkbox"
              id="is_atomic"
              checked={formData.is_atomic}
              onChange={(e) => setFormData({ ...formData, is_atomic: e.target.checked })}
              className="w-4 h-4 rounded border-gray-600 text-purple-500 focus:ring-purple-500 bg-gray-700"
            />
            <label htmlFor="is_atomic" className="text-sm text-gray-300">
              Create as atomic goal (single action, verifiable result)
            </label>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !formData.title}
              className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create Goal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default GoalCreationModal;