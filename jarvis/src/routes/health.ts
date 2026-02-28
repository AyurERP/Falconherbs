/**
 * JARVIS Health Route
 * Simple health check endpoint.
 */

import { Router } from 'express';
import { checkProviderHealth } from '../services/llmService';

export const healthRouter = Router();

healthRouter.get('/health', async (_req, res) => {
  try {
    const providers = await checkProviderHealth();
    res.json({
      status: 'ok',
      uptime: process.uptime(),
      database: 'connected',
      providers: {
        nvidia: providers.nvidia,
        ollama: providers.ollama,
      },
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    res.status(500).json({
      status: 'error',
      error: err instanceof Error ? err.message : 'Unknown error',
      timestamp: new Date().toISOString(),
    });
  }
});
