/**
 * JARVIS Models Routes
 * LLM model listing and provider health.
 */

import { Router, Request, Response } from 'express';
import {
  getAvailableModels,
  checkProviderHealth,
} from '../services/llmService';
import { logger } from '../utils/logger';

export const modelsRouter = Router();

// GET /api/models
modelsRouter.get('/models', async (_req: Request, res: Response) => {
  try {
    const models = await getAvailableModels();
    res.status(200).json({ data: models });
  } catch (err) {
    logger.error('Failed to get models', { error: String(err) });
    res.status(500).json({ error: 'Failed to get models' });
  }
});

// GET /api/models/health
modelsRouter.get('/models/health', async (_req: Request, res: Response) => {
  try {
    const providers = await checkProviderHealth();
    res.status(200).json({ data: providers });
  } catch (err) {
    logger.error('Failed to check provider health', { error: String(err) });
    res.status(500).json({ error: 'Failed to check provider health' });
  }
});
