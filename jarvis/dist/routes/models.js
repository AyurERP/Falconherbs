"use strict";
/**
 * JARVIS Models Routes
 * LLM model listing and provider health.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.modelsRouter = void 0;
const express_1 = require("express");
const llmService_1 = require("../services/llmService");
const logger_1 = require("../utils/logger");
exports.modelsRouter = (0, express_1.Router)();
// GET /api/models
exports.modelsRouter.get('/models', async (_req, res) => {
    try {
        const models = await (0, llmService_1.getAvailableModels)();
        res.status(200).json({ data: models });
    }
    catch (err) {
        logger_1.logger.error('Failed to get models', { error: String(err) });
        res.status(500).json({ error: 'Failed to get models' });
    }
});
// GET /api/models/health
exports.modelsRouter.get('/models/health', async (_req, res) => {
    try {
        const providers = await (0, llmService_1.checkProviderHealth)();
        res.status(200).json({ data: providers });
    }
    catch (err) {
        logger_1.logger.error('Failed to check provider health', { error: String(err) });
        res.status(500).json({ error: 'Failed to check provider health' });
    }
});
