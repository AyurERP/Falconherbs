/**
 * TEMPORARY test route for LLM — will be removed in Prompt 4.
 */

import { Router, Request, Response } from 'express';
import { chat } from '../services/llmService';
import { logger } from '../utils/logger';

export const testRouter = Router();

// POST /api/test/chat — TEMPORARY
testRouter.post('/test/chat', async (req: Request, res: Response) => {
  try {
    const body = req.body || {};
    const message = typeof body.message === 'string' ? body.message.trim() : '';

    if (!message) {
      res.status(400).json({ error: 'message is required' });
      return;
    }

    const response = await chat({
      messages: [{ role: 'user', content: message }],
    });

    res.status(200).json(response);
  } catch (err) {
    logger.error('Test chat failed', { error: String(err) });
    res.status(500).json({
      error: err instanceof Error ? err.message : 'LLM call failed',
    });
  }
});
