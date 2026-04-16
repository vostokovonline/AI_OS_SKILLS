/**
 * Unified Chat Dashboard
 *
 * Combines Chat interface and Questions system from Dashboard v1.
 * SSE-based real-time updates for live chat experience.
 */

import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import {
  Send,
  MessageCircle,
  User,
  Bot,
  HelpCircle,
  CheckCircle,
  Clock,
  RefreshCw
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface Question {
  artifact_id: string;
  question: string;
  context: string;
  priority: 'critical' | 'high' | 'normal' | 'low';
  goal_id: string;
  timeout_at: string | null;
  timeout_action: string;
  default_answer: string | null;
  options?: string[];
}

interface QuestionsResponse {
  questions: Question[];
}

// ============================================================================
// Components
// ============================================================================

const QuestionCard: React.FC<{
  question: Question;
  onAnswer: (questionId: string, answer: string) => void;
  onSkip: (questionId: string) => void;
  onDismiss: (questionId: string) => void;
}> = ({ question, onAnswer, onSkip, onDismiss }) => {
  const [answer, setAnswer] = useState('');

  const priorityConfig = {
    critical: { color: 'border-red-500 bg-red-50', icon: '🔴', label: 'CRITICAL' },
    high: { color: 'border-orange-500 bg-orange-50', icon: '🟠', label: 'HIGH' },
    normal: { color: 'border-green-500 bg-green-50', icon: '🟢', label: 'NORMAL' },
    low: { color: 'border-gray-500 bg-gray-50', icon: '⚪', label: 'LOW' },
  };

  const config = priorityConfig[question.priority];

  // Calculate timeout
  const timeRemaining = question.timeout_at
    ? Math.max(0, Math.floor((new Date(question.timeout_at).getTime() - Date.now()) / 60000))
    : null;

  return (
    <div className={`border-2 rounded-lg p-6 mb-4 ${config.color}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{config.icon}</span>
          <div>
            <h3 className="font-semibold">{config.label} Priority</h3>
            <p className="text-sm text-gray-600">Goal: {question.goal_id.slice(0, 8)}...</p>
          </div>
        </div>
        {timeRemaining !== null && (
          <div className={`flex items-center gap-2 text-sm ${timeRemaining < 5 ? 'text-red-600' : 'text-gray-600'}`}>
            <Clock className="w-4 h-4" />
            <span>{timeRemaining} min remaining</span>
          </div>
        )}
      </div>

      <div className="mb-4">
        <p className="font-medium mb-2">Question:</p>
        <p className="text-gray-800">{question.question}</p>
      </div>

      {question.context && (
        <div className="mb-4 p-3 bg-white rounded border">
          <p className="text-sm text-gray-600 mb-1">Context:</p>
          <p className="text-sm">{question.context}</p>
        </div>
      )}

      {question.options && question.options.length > 0 && (
        <div className="mb-4">
          <p className="text-sm text-gray-600 mb-2">Options:</p>
          <ul className="list-disc list-inside text-sm space-y-1">
            {question.options.map((opt, idx) => (
              <li key={idx}>{opt}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-4">
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Введите ваш ответ..."
          className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
        />
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => onAnswer(question.artifact_id, answer)}
          disabled={!answer.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <Send className="w-4 h-4" />
          Send Answer
        </button>
        {question.default_answer && (
          <button
            onClick={() => onSkip(question.artifact_id)}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 flex items-center gap-2"
          >
            Skip (Use Default)
          </button>
        )}
        <button
          onClick={() => onDismiss(question.artifact_id)}
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 flex items-center gap-2"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// Main Page
// ============================================================================

const UnifiedChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);
  const [showQuestions, setShowQuestions] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load chat history on mount if session exists
  useEffect(() => {
    // Try to get existing session from localStorage
    const savedSessionId = localStorage.getItem('chat_session_id');
    if (savedSessionId) {
      setSessionId(savedSessionId);
      loadChatHistory(savedSessionId);
    }
  }, []);

  const loadChatHistory = async (sid: string) => {
    setIsLoadingHistory(true);
    try {
      const response = await fetch(`/chat/${sid}/history?limit=50`);
      const data = await response.json();
      if (data.status === 'ok' && data.messages) {
        setMessages(data.messages.map((m: any) => ({
          role: m.role === 'assistant' ? 'assistant' : 'user',
          content: m.content,
          timestamp: m.created_at
        })));
      }
    } catch (err) {
      console.error('Failed to load chat history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Load questions
  const loadQuestions = async () => {
    try {
      const response = await apiClient.get<QuestionsResponse>('/questions/pending');
      setQuestions(response.questions || []);
    } catch (err) {
      console.error('Failed to load questions:', err);
    }
  };

  useEffect(() => {
    loadQuestions();
    const interval = setInterval(loadQuestions, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'auto', block: 'end' });
    }
  }, [messages, loading]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setLoading(true);

    try {
      // Use /chat/sync with session_id for conversation context
      const response = await fetch('/chat/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId || undefined,
          content: currentInput
        })
      });

      const data = await response.json();

      if (data.status === 'ok') {
        if (data.session_id && !sessionId) {
          setSessionId(data.session_id);
          localStorage.setItem('chat_session_id', data.session_id);
        }

        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: data.response || 'Нет ответа от системы',
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        throw new Error(data.response || 'Неизвестная ошибка');
      }
    } catch (err: any) {
      const errorText = err.message || 'Ошибка отправки сообщения';
      console.error('Chat error:', err);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `⚠️ Ошибка: ${errorText}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerQuestion = async (questionId: string, answer: string) => {
    try {
      await apiClient.post(`/questions/${questionId}/answer?answer=${encodeURIComponent(answer)}`);
      // Remove answered question
      setQuestions((prev) => prev.filter((q) => q.artifact_id !== questionId));
    } catch (err) {
      console.error('Failed to answer question:', err);
    }
  };

  const handleSkipQuestion = async (questionId: string) => {
    const question = questions.find((q) => q.artifact_id === questionId);
    if (!question?.default_answer) return;

    try {
      await apiClient.post(`/questions/${questionId}/answer?answer=${encodeURIComponent(question.default_answer)}`);
      setQuestions((prev) => prev.filter((q) => q.artifact_id !== questionId));
    } catch (err) {
      console.error('Failed to skip question:', err);
    }
  };

  const handleDismissQuestion = (questionId: string) => {
    // Just remove from local state
    setQuestions((prev) => prev.filter((q) => q.artifact_id !== questionId));
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white shadow-sm p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <MessageCircle className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Чат с системой</h1>
              <p className="text-sm text-gray-600">Общение с AI-OS + Вопросы системы</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowQuestions(!showQuestions)}
              className={`px-4 py-2 rounded flex items-center gap-2 ${
                showQuestions ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
              }`}
            >
              <HelpCircle className="w-4 h-4" />
              Вопросы ({questions.length})
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        <div className="max-w-7xl mx-auto h-full flex">
          {/* Chat Section */}
          <div className={`flex-1 flex flex-col ${showQuestions ? 'mr-4' : ''}`}>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && !isLoadingHistory && (
                <div className="text-center text-gray-500 mt-20">
                  <Bot className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                  <p className="text-lg font-medium">Сообщений пока нет</p>
                  <p className="text-sm">Начните общение с системой</p>
                </div>
              )}

              {isLoadingHistory && (
                <div className="text-center text-gray-500 mt-20">
                  <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-sm">Загрузка истории чата...</p>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[70%] rounded-lg p-4 ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border shadow-sm'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      {msg.role === 'user' ? (
                        <User className="w-4 h-4" />
                      ) : (
                        <Bot className="w-4 h-4" />
                      )}
                      <span className="text-sm font-medium">
                        {msg.role === 'user' ? 'You' : 'System'}
                      </span>
                      <span className="text-xs opacity-70">
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white border rounded-lg p-4 shadow-sm">
                    <div className="flex items-center gap-2">
                      <Bot className="w-4 h-4 animate-pulse" />
                      <span className="text-sm text-gray-600">Думаю...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 bg-white border-t">
              <div className="flex gap-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Введите сообщение... (Enter - отправить, Shift+Enter - новая строка)"
                  className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  rows={2}
                />
                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || loading}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 self-end"
                >
                  <Send className="w-4 h-4" />
                  Send
                </button>
              </div>
            </div>
          </div>

          {/* Questions Panel */}
          {showQuestions && (
            <div className="w-96 overflow-y-auto p-4 bg-white border-l">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <HelpCircle className="w-5 h-5 text-orange-600" />
                  Ожидающие вопросы
                </h2>
                <button
                  onClick={loadQuestions}
                  className="p-1 hover:bg-gray-100 rounded"
                  title="Refresh"
                >
                  <RefreshCw className="w-4 h-4 text-gray-600" />
                </button>
              </div>

              {questions.length === 0 ? (
                <div className="text-center text-gray-500 py-12">
                  <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-500" />
                  <p className="font-medium">All caught up!</p>
                  <p className="text-sm">No pending questions</p>
                </div>
              ) : (
                <div>
                  {questions.map((q) => (
                    <QuestionCard
                      key={q.artifact_id}
                      question={q}
                      onAnswer={handleAnswerQuestion}
                      onSkip={handleSkipQuestion}
                      onDismiss={handleDismissQuestion}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default UnifiedChat;
