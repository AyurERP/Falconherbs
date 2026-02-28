"use strict";
/**
 * JARVIS Health Route
 * Simple health check endpoint.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.healthRouter = void 0;
const express_1 = require("express");
const llmService_1 = require("../services/llmService");
exports.healthRouter = (0, express_1.Router)();
exports.healthRouter.get('/health', async (_req, res) => {
    try {
        const providers = await (0, llmService_1.checkProviderHealth)();
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
    }
    catch (err) {
        res.status(500).json({
            status: 'error',
            error: err instanceof Error ? err.message : 'Unknown error',
            timestamp: new Date().toISOString(),
        });
    }
});
