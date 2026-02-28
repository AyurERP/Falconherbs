/**
 * JARVIS Config Utility
 * Central configuration for the application.
 */

import path from 'path';
import { config as loadEnv } from 'dotenv';

// Load .env from project root (jarvis folder) regardless of cwd
loadEnv({ path: path.resolve(__dirname, '../../.env') });

export const config = {
  port: parseInt(process.env.PORT || '3001', 10),
  dbPath: process.env.DB_PATH || 'data/jarvis.db',
  nodeEnv: process.env.NODE_ENV || 'development',

  nvidia: {
    apiKey: process.env.NVIDIA_API_KEY || '',
    baseUrl: process.env.NVIDIA_API_URL || 'https://integrate.api.nvidia.com/v1',
    defaultModel: process.env.NVIDIA_DEFAULT_MODEL || 'meta/llama-3.1-8b-instruct',
    timeout: parseInt(process.env.NVIDIA_TIMEOUT || '30000', 10),
    maxRetries: parseInt(process.env.NVIDIA_MAX_RETRIES || '2', 10),
  },

  ollama: {
    baseUrl: process.env.OLLAMA_URL || 'http://localhost:11434',
    defaultModel: process.env.OLLAMA_DEFAULT_MODEL || 'qwen2.5-coder:7b',
    timeout: parseInt(process.env.OLLAMA_TIMEOUT || '60000', 10),
    maxRetries: parseInt(process.env.OLLAMA_MAX_RETRIES || '1', 10),
  },

  llm: {
    defaultProvider: (process.env.DEFAULT_LLM_PROVIDER || 'nvidia') as 'nvidia' | 'ollama',
    defaultTemperature: parseFloat(process.env.DEFAULT_TEMPERATURE || '0.7'),
    defaultMaxTokens: parseInt(process.env.DEFAULT_MAX_TOKENS || '2048', 10),
    systemPrompt:
      process.env.SYSTEM_PROMPT ||
      "You are JARVIS, a highly capable personal AI assistant. You are direct, efficient, and helpful. You remember past conversations and adapt to the user's preferences over time.",
  },
};
