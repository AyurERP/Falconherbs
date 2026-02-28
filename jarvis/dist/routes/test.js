"use strict";
/**
 * TEMPORARY test route for LLM — will be removed in Prompt 4.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.testRouter = void 0;
const express_1 = require("express");
const llmService_1 = require("../services/llmService");
const logger_1 = require("../utils/logger");
exports.testRouter = (0, express_1.Router)();
// POST /api/test/chat — TEMPORARY
exports.testRouter.post('/test/chat', async (req, res) => {
    try {
        const body = req.body || {};
        const message = typeof body.message === 'string' ? body.message.trim() : '';
        if (!message) {
            res.status(400).json({ error: 'message is required' });
            return;
        }
        const response = await (0, llmService_1.chat)({
            messages: [{ role: 'user', content: message }],
        });
        res.status(200).json(response);
    }
    catch (err) {
        logger_1.logger.error('Test chat failed', { error: String(err) });
        res.status(500).json({
            error: err instanceof Error ? err.message : 'LLM call failed',
        });
    }
});
