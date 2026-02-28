/**
 * Core types for the entire application
 * Add to this file as we build more features
 */

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  last_message_preview?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model_used: string | null;
  tokens_used: number;
  created_at: string;
}

export interface CreateConversationInput {
  title?: string;
}

export interface CreateMessageInput {
  role: 'user' | 'assistant' | 'system';
  content: string;
  model_used?: string;
  tokens_used?: number;
}

export interface UpdateConversationInput {
  title: string;
}

export interface PaginationParams {
  page: number;
  limit: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export interface ConversationWithMessages extends Conversation {
  messages: Message[];
}

// ============ LLM TYPES ============

export interface LLMMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface LLMRequestOptions {
  messages: LLMMessage[];
  model?: string;
  provider?: 'nvidia' | 'ollama';
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
}

export interface LLMResponse {
  content: string;
  model: string;
  provider: string;
  tokens_used: number;
  latency_ms: number;
  fallback_used: boolean;
}

export interface LLMProviderConfig {
  name: string;
  baseUrl: string;
  apiKey: string | null;
  defaultModel: string;
  availableModels: string[];
  timeout: number;
  maxRetries: number;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  description: string;
  bestFor: string[];
  maxContext: number;
}
