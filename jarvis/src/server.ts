/**
 * JARVIS Server
 * Express + SQLite backend for AI assistant.
 */

import express from 'express';
import { config } from './utils/config';
import { logger } from './utils/logger';

// Debug: confirm env loading (never log the actual key)
if (!config.nvidia.apiKey) {
  logger.warn('NVIDIA_API_KEY not loaded — check .env exists in jarvis folder with NVIDIA_API_KEY=...');
}
import { healthRouter } from './routes/health';
import { conversationsRouter } from './routes/conversations';
import { modelsRouter } from './routes/models';
import { testRouter } from './routes/test';

const app = express();

app.use(express.json());

// API routes
app.use('/api', healthRouter);
app.use('/api', modelsRouter);
app.use('/api', testRouter);
app.use('/api/conversations', conversationsRouter);

// 404 handler
app.use((_req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Error handler (must be last)
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  logger.error('Unhandled error', { error: err.message, stack: err.stack });
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(config.port, () => {
  logger.info(`JARVIS server running on port ${config.port}`);
});
