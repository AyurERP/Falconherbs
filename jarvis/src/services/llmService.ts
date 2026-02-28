/**
 * JARVIS LLM Service
 * NVIDIA API (primary) + Ollama (fallback).
 * Uses raw fetch() — no external LLM libraries.
 */

import { config } from '../utils/config';
import { logger } from '../utils/logger';
import type {
  LLMMessage,
  LLMRequestOptions,
  LLMResponse,
  LLMProviderConfig,
  ModelInfo,
} from '../types';

/** Waits for specified milliseconds */
const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

const NVIDIA_MODELS: ModelInfo[] = [
  {
    id: 'meta/llama-3.1-8b-instruct',
    name: 'Llama 3.1 8B',
    provider: 'nvidia',
    description: 'Fast general purpose',
    bestFor: ['quick-tasks', 'chat'],
    maxContext: 8192,
  },
  {
    id: 'meta/llama-3.1-70b-instruct',
    name: 'Llama 3.1 70B',
    provider: 'nvidia',
    description: 'High quality reasoning',
    bestFor: ['code', 'analysis'],
    maxContext: 8192,
  },
  {
    id: 'qwen/qwen2.5-7b-instruct',
    name: 'Qwen 2.5 7B',
    provider: 'nvidia',
    description: 'Fast coding and chat',
    bestFor: ['code', 'quick-tasks'],
    maxContext: 32768,
  },
  {
    id: 'qwen/qwen2.5-72b-instruct',
    name: 'Qwen 2.5 72B',
    provider: 'nvidia',
    description: 'Best quality Qwen',
    bestFor: ['code', 'analysis', 'deep-work'],
    maxContext: 32768,
  },
];

async function callProvider(
  provider: LLMProviderConfig,
  options: LLMRequestOptions
): Promise<LLMResponse> {
  const model = options.model || provider.defaultModel;
  const temperature = options.temperature ?? config.llm.defaultTemperature;
  const maxTokens = options.max_tokens ?? config.llm.defaultMaxTokens;
  const stream = options.stream ?? false;

  const url =
    provider.name === 'ollama'
      ? `${provider.baseUrl}/v1/chat/completions`
      : `${provider.baseUrl}/chat/completions`;

  const body = {
    model,
    messages: options.messages,
    temperature,
    max_tokens: maxTokens,
    stream,
  };

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (provider.apiKey) {
    headers['Authorization'] = `Bearer ${provider.apiKey}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), provider.timeout);

  const startTime = Date.now();

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const latencyMs = Date.now() - startTime;

    if (!response.ok) {
      let errorBody: { error?: { message?: string } } = {};
      try {
        errorBody = (await response.json()) as { error?: { message?: string } };
      } catch {
        errorBody = {};
      }
      throw new Error(
        `${provider.name} API failed: ${response.status} ${response.statusText} — ` +
          `Model: ${model}, ` +
          `Error: ${errorBody?.error?.message || 'Unknown error'}`
      );
    }

    const data = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
      usage?: { total_tokens?: number };
    };

    const content =
      data.choices?.[0]?.message?.content ?? '';
    const tokensUsed = data.usage?.total_tokens ?? 0;

    logger.info('LLM call', {
      provider: provider.name,
      model,
      tokens: tokensUsed,
      latency: latencyMs,
    });

    return {
      content,
      model,
      provider: provider.name,
      tokens_used: tokensUsed,
      latency_ms: latencyMs,
      fallback_used: false,
    };
  } catch (err) {
    clearTimeout(timeoutId);

    if (err instanceof Error) {
      if (err.name === 'AbortError') {
        throw new Error(
          `${provider.name} API timeout after ${provider.timeout}ms — ` +
            `Model: ${model}. Server may be overloaded.`
        );
      }
    }
    throw err;
  }
}

async function callWithRetry(
  provider: LLMProviderConfig,
  options: LLMRequestOptions
): Promise<LLMResponse> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= provider.maxRetries; attempt++) {
    try {
      return await callProvider(provider, options);
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < provider.maxRetries) {
        logger.warn('LLM retry', {
          provider: provider.name,
          attempt: attempt + 1,
          error: lastError.message,
        });
        await sleep(1000);
      }
    }
  }

  throw lastError ?? new Error('Unknown error');
}

function buildProviderConfig(providerName: 'nvidia' | 'ollama'): LLMProviderConfig {
  if (providerName === 'nvidia') {
    return {
      name: 'nvidia',
      baseUrl: config.nvidia.baseUrl,
      apiKey: config.nvidia.apiKey || null,
      defaultModel: config.nvidia.defaultModel,
      availableModels: NVIDIA_MODELS.map((m) => m.id),
      timeout: config.nvidia.timeout,
      maxRetries: config.nvidia.maxRetries,
    };
  }
  return {
    name: 'ollama',
    baseUrl: config.ollama.baseUrl,
    apiKey: null,
    defaultModel: config.ollama.defaultModel,
    availableModels: [],
    timeout: config.ollama.timeout,
    maxRetries: config.ollama.maxRetries,
  };
}

function ensureSystemPrompt(messages: LLMMessage[]): LLMMessage[] {
  const hasSystem = messages.length > 0 && messages[0].role === 'system';
  if (hasSystem) return messages;
  return [
    { role: 'system', content: config.llm.systemPrompt },
    ...messages,
  ];
}

/**
 * Main chat function — use this from other services.
 */
export async function chat(options: LLMRequestOptions): Promise<LLMResponse> {
  const providerName = options.provider ?? config.llm.defaultProvider;
  const messages = ensureSystemPrompt(options.messages);

  const primaryConfig = buildProviderConfig(providerName);

  let nvidiaError: Error | null = null;
  let ollamaError: Error | null = null;

  // Try primary provider
  try {
    const response = await callWithRetry(primaryConfig, { ...options, messages });
    return response;
  } catch (err) {
    const e = err instanceof Error ? err : new Error(String(err));
    if (providerName === 'nvidia') {
      nvidiaError = e;
    } else {
      ollamaError = e;
    }
  }

  // Fallback: if primary was nvidia, try Ollama
  if (providerName === 'nvidia') {
    logger.warn('Primary provider failed, falling back to Ollama', {
      nvidiaError: nvidiaError?.message,
    });

    const ollamaConfig = buildProviderConfig('ollama');
    try {
      const response = await callWithRetry(ollamaConfig, {
        ...options,
        messages,
        model: undefined, // Use Ollama default model on fallback
      });
      return { ...response, fallback_used: true };
    } catch (err) {
      ollamaError = err instanceof Error ? err : new Error(String(err));
    }
  }

  // All providers failed
  throw new Error(
    `All LLM providers failed.\n` +
      `NVIDIA: ${nvidiaError?.message ?? 'not tried'}\n` +
      `Ollama: ${ollamaError?.message ?? 'not tried'}\n` +
      `Check API keys and Ollama status.`
  );
}

/**
 * Returns list of available models from all providers.
 */
export async function getAvailableModels(): Promise<ModelInfo[]> {
  const models: ModelInfo[] = [...NVIDIA_MODELS];

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(`${config.ollama.baseUrl}/api/tags`, {
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      const data = (await response.json()) as { models?: Array<{ name: string }> };
      const ollamaModels = data.models ?? [];
      for (const m of ollamaModels) {
        models.push({
          id: m.name,
          name: m.name,
          provider: 'ollama',
          description: 'Local model via Ollama',
          bestFor: ['chat', 'quick-tasks'],
          maxContext: 8192,
        });
      }
    }
  } catch {
    logger.warn('Ollama not available — local fallback will not work');
  }

  return models;
}

/**
 * Quick health check for both providers.
 */
export async function checkProviderHealth(): Promise<{
  nvidia: boolean;
  ollama: boolean;
}> {
  const result = { nvidia: false, ollama: false };

  // NVIDIA: check API key
  result.nvidia = !!config.nvidia.apiKey?.trim();

  // Ollama: GET base URL
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const response = await fetch(config.ollama.baseUrl, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    result.ollama = response.ok;
  } catch {
    result.ollama = false;
  }

  logger.info('Provider health', result);
  return result;
}
