"use strict";
/**
 * JARVIS Server
 * Express + SQLite backend for AI assistant.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const config_1 = require("./utils/config");
const logger_1 = require("./utils/logger");
const health_1 = require("./routes/health");
const conversations_1 = require("./routes/conversations");
const models_1 = require("./routes/models");
const test_1 = require("./routes/test");
const app = (0, express_1.default)();
app.use(express_1.default.json());
// API routes
app.use('/api', health_1.healthRouter);
app.use('/api', models_1.modelsRouter);
app.use('/api', test_1.testRouter);
app.use('/api/conversations', conversations_1.conversationsRouter);
// 404 handler
app.use((_req, res) => {
    res.status(404).json({ error: 'Not found' });
});
// Error handler (must be last)
app.use((err, _req, res, _next) => {
    logger_1.logger.error('Unhandled error', { error: err.message, stack: err.stack });
    res.status(500).json({ error: 'Internal server error' });
});
app.listen(config_1.config.port, () => {
    logger_1.logger.info(`JARVIS server running on port ${config_1.config.port}`);
});
