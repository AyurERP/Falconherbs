"use strict";
/**
 * JARVIS LLM Service
 * NVIDIA API (primary) + Ollama (fallback).
 * Uses raw fetch() — no external LLM libraries.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.chat = chat;
exports.getAvailableModels = getAvailableModels;
exports.checkProviderHealth = checkProviderHealth;
const config_1 = require("../utils/config");
const logger_1 = require("../utils/logger");
/** Waits for specified milliseconds */
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const NVIDIA_MODELS = [
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
async function callProvider(provider, options) {
    const model = options.model || provider.defaultModel;
    const temperature = options.temperature ?? config_1.config.llm.defaultTemperature;
    const maxTokens = options.max_tokens ?? config_1.config.llm.defaultMaxTokens;
    const stream = options.stream ?? false;
    const url = provider.name === 'ollama'
        ? `${provider.baseUrl}/v1/chat/completions`
        : `${provider.baseUrl}/chat/completions`;
    const body = {
        model,
        messages: options.messages,
        temperature,
        max_tokens: maxTokens,
        stream,
    };
    const headers = {
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
            let errorBody = {};
            try {
                errorBody = (await response.json());
            }
            catch {
                errorBody = {};
            }
            throw new Error(`${provider.name} API failed: ${response.status} ${response.statusText} — ` +
                `Model: ${model}, ` +
                `Error: ${errorBody?.error?.message || 'Unknown error'}`);
        }
        const data = (await response.json());
        const content = data.choices?.[0]?.message?.content ?? '';
        const tokensUsed = data.usage?.total_tokens ?? 0;
        logger_1.logger.info('LLM call', {
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
    }
    catch (err) {
        clearTimeout(timeoutId);
        if (err instanceof Error) {
            if (err.name === 'AbortError') {
                throw new Error(`${provider.name} API timeout after ${provider.timeout}ms — ` +
                    `Model: ${model}. Server may be overloaded.`);
            }
        }
        throw err;
    }
}
async function callWithRetry(provider, options) {
    let lastError = null;
    for (let attempt = 0; attempt <= provider.maxRetries; attempt++) {
        try {
            return await callProvider(provider, options);
        }
        catch (err) {
            lastError = err instanceof Error ? err : new Error(String(err));
            if (attempt < provider.maxRetries) {
                logger_1.logger.warn('LLM retry', {
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
function buildProviderConfig(providerName) {
    if (providerName === 'nvidia') {
        return {
            name: 'nvidia',
            baseUrl: config_1.config.nvidia.baseUrl,
            apiKey: config_1.config.nvidia.apiKey || null,
            defaultModel: config_1.config.nvidia.defaultModel,
            availableModels: NVIDIA_MODELS.map((m) => m.id),
            timeout: config_1.config.nvidia.timeout,
            maxRetries: config_1.config.nvidia.maxRetries,
        };
    }
    return {
        name: 'ollama',
        baseUrl: config_1.config.ollama.baseUrl,
        apiKey: null,
        defaultModel: config_1.config.ollama.defaultModel,
        availableModels: [],
        timeout: config_1.config.ollama.timeout,
        maxRetries: config_1.config.ollama.maxRetries,
    };
}
function ensureSystemPrompt(messages) {
    const hasSystem = messages.length > 0 && messages[0].role === 'system';
    if (hasSystem)
        return messages;
    return [
        { role: 'system', content: config_1.config.llm.systemPrompt },
        ...messages,
    ];
}
/**
 * Main chat function — use this from other services.
 */
async function chat(options) {
    const providerName = options.provider ?? config_1.config.llm.defaultProvider;
    const messages = ensureSystemPrompt(options.messages);
    const primaryConfig = buildProviderConfig(providerName);
    let nvidiaError = null;
    let ollamaError = null;
    // Try primary provider
    try {
        const response = await callWithRetry(primaryConfig, { ...options, messages });
        return response;
    }
    catch (err) {
        const e = err instanceof Error ? err : new Error(String(err));
        if (providerName === 'nvidia') {
            nvidiaError = e;
        }
        else {
            ollamaError = e;
        }
    }
    // Fallback: if primary was nvidia, try Ollama
    if (providerName === 'nvidia') {
        logger_1.logger.warn('Primary provider failed, falling back to Ollama', {
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
        }
        catch (err) {
            ollamaError = err instanceof Error ? err : new Error(String(err));
        }
    }
    // All providers failed
    throw new Error(`All LLM providers failed.\n` +
        `NVIDIA: ${nvidiaError?.message ?? 'not tried'}\n` +
        `Ollama: ${ollamaError?.message ?? 'not tried'}\n` +
        `Check API keys and Ollama status.`);
}
/**
 * Returns list of available models from all providers.
 */
async function getAvailableModels() {
    const models = [...NVIDIA_MODELS];
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const response = await fetch(`${config_1.config.ollama.baseUrl}/api/tags`, {
            signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (response.ok) {
            const data = (await response.json());
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
    }
    catch {
        logger_1.logger.warn('Ollama not available — local fallback will not work');
    }
    return models;
}
/**
 * Quick health check for both providers.
 */
async function checkProviderHealth() {
    const result = { nvidia: false, ollama: false };
    // NVIDIA: check API key
    result.nvidia = !!config_1.config.nvidia.apiKey?.trim();
    // Ollama: GET base URL
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);
        const response = await fetch(config_1.config.ollama.baseUrl, {
            signal: controller.signal,
        });
        clearTimeout(timeoutId);
        result.ollama = response.ok;
    }
    catch {
        result.ollama = false;
    }
    logger_1.logger.info('Provider health', result);
    return result;
}
