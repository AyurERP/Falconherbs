"use strict";
/**
 * JARVIS Conversations Routes
 * REST API for conversations and messages.
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.conversationsRouter = void 0;
const express_1 = require("express");
const conversationService = __importStar(require("../services/conversationService"));
const logger_1 = require("../utils/logger");
const VALID_ROLES = ['user', 'assistant', 'system'];
function parsePagination(pageStr, limitStr, defaultLimit) {
    let page = 1;
    let limit = defaultLimit;
    const p = parseInt(String(pageStr), 10);
    if (!isNaN(p) && p > 0)
        page = p;
    const l = parseInt(String(limitStr), 10);
    if (!isNaN(l) && l >= 1 && l <= 100)
        limit = l;
    return { page, limit };
}
exports.conversationsRouter = (0, express_1.Router)();
// POST /api/conversations
exports.conversationsRouter.post('/', (req, res) => {
    try {
        const body = req.body || {};
        const title = typeof body.title === 'string' ? body.title : undefined;
        const conversation = conversationService.createConversation({ title });
        res.status(201).json({ data: conversation });
    }
    catch (err) {
        logger_1.logger.error('Failed to create conversation', { error: String(err) });
        res.status(500).json({ error: 'Failed to create conversation' });
    }
});
// GET /api/conversations
exports.conversationsRouter.get('/', (req, res) => {
    try {
        const search = typeof req.query.search === 'string' ? req.query.search.trim() : undefined;
        const pagination = parsePagination(req.query.page, req.query.limit, 20);
        if (search && search.length > 0) {
            const result = conversationService.searchConversations(search, pagination);
            res.status(200).json(result);
        }
        else {
            const result = conversationService.getConversations(pagination);
            res.status(200).json(result);
        }
    }
    catch (err) {
        logger_1.logger.error('Failed to list conversations', { error: String(err) });
        res.status(500).json({ error: 'Failed to list conversations' });
    }
});
// GET /api/conversations/:id/messages (must be before /:id)
exports.conversationsRouter.get('/:id/messages', (req, res) => {
    try {
        const { id: conversationId } = req.params;
        const pagination = parsePagination(req.query.page, req.query.limit, 50);
        const result = conversationService.getMessages(conversationId, pagination);
        if (!result) {
            res.status(404).json({ error: 'Conversation not found' });
            return;
        }
        res.status(200).json(result);
    }
    catch (err) {
        logger_1.logger.error('Failed to get messages', { error: String(err) });
        res.status(500).json({ error: 'Failed to get messages' });
    }
});
// GET /api/conversations/:id/context (must be before /:id)
exports.conversationsRouter.get('/:id/context', (req, res) => {
    try {
        const { id: conversationId } = req.params;
        const countStr = req.query.count;
        let count = 20;
        const c = parseInt(String(countStr), 10);
        if (!isNaN(c) && c > 0)
            count = Math.min(c, 100);
        const messages = conversationService.getRecentContext(conversationId, count);
        if (!messages) {
            res.status(404).json({ error: 'Conversation not found' });
            return;
        }
        res.status(200).json({ data: messages });
    }
    catch (err) {
        logger_1.logger.error('Failed to get context', { error: String(err) });
        res.status(500).json({ error: 'Failed to get context' });
    }
});
// GET /api/conversations/:id
exports.conversationsRouter.get('/:id', (req, res) => {
    try {
        const { id } = req.params;
        const conversation = conversationService.getConversationById(id);
        if (!conversation) {
            res.status(404).json({ error: 'Conversation not found' });
            return;
        }
        res.status(200).json({ data: conversation });
    }
    catch (err) {
        logger_1.logger.error('Failed to get conversation', { error: String(err) });
        res.status(500).json({ error: 'Failed to get conversation' });
    }
});
// PUT /api/conversations/:id
exports.conversationsRouter.put('/:id', (req, res) => {
    try {
        const { id } = req.params;
        const body = req.body || {};
        const title = typeof body.title === 'string' ? body.title.trim() : '';
        if (!title) {
            res.status(400).json({ error: 'Title is required and must be non-empty' });
            return;
        }
        if (title.length > 200) {
            res.status(400).json({ error: 'Title must be at most 200 characters' });
            return;
        }
        const conversation = conversationService.updateConversation(id, { title });
        if (!conversation) {
            res.status(404).json({ error: 'Conversation not found' });
            return;
        }
        res.status(200).json({ data: conversation });
    }
    catch (err) {
        logger_1.logger.error('Failed to update conversation', { error: String(err) });
        res.status(500).json({ error: 'Failed to update conversation' });
    }
});
// DELETE /api/conversations/:id
exports.conversationsRouter.delete('/:id', (req, res) => {
    try {
        const { id } = req.params;
        const deleted = conversationService.deleteConversation(id);
        if (!deleted) {
            res.status(404).json({ error: 'Conversation not found' });
            return;
        }
        res.status(200).json({ message: 'Conversation deleted' });
    }
    catch (err) {
        logger_1.logger.error('Failed to delete conversation', { error: String(err) });
        res.status(500).json({ error: 'Failed to delete conversation' });
    }
});
// POST /api/conversations/:id/messages
exports.conversationsRouter.post('/:id/messages', (req, res) => {
    try {
        const { id: conversationId } = req.params;
        const body = req.body || {};
        const role = body.role;
        if (!VALID_ROLES.includes(role)) {
            res.status(400).json({
                error: "Role must be one of: 'user', 'assistant', 'system'",
            });
            return;
        }
        const content = typeof body.content === 'string' ? body.content.trim() : '';
        if (!content) {
            res.status(400).json({ error: 'Content must be a non-empty string' });
            return;
        }
        const modelUsed = typeof body.model_used === 'string' ? body.model_used.trim() : undefined;
        if (modelUsed !== undefined && !modelUsed) {
            res.status(400).json({ error: 'model_used must be non-empty if provided' });
            return;
        }
        const tokensUsed = body.tokens_used;
        if (tokensUsed !== undefined) {
            const n = Number(tokensUsed);
            if (!Number.isInteger(n) || n < 0) {
                res.status(400).json({ error: 'tokens_used must be a non-negative integer' });
                return;
            }
        }
        const message = conversationService.addMessage(conversationId, {
            role,
            content,
            model_used: modelUsed,
            tokens_used: tokensUsed,
        });
        if (!message) {
            res.status(404).json({ error: 'Conversation not found' });
            return;
        }
        res.status(201).json({ data: message });
    }
    catch (err) {
        logger_1.logger.error('Failed to add message', { error: String(err) });
        res.status(500).json({ error: 'Failed to add message' });
    }
});
// DELETE /api/conversations/:id/messages/:messageId
exports.conversationsRouter.delete('/:id/messages/:messageId', (req, res) => {
    try {
        const { id: conversationId, messageId } = req.params;
        const deleted = conversationService.deleteMessage(conversationId, messageId);
        if (!deleted) {
            res.status(404).json({ error: 'Message not found' });
            return;
        }
        res.status(200).json({ message: 'Message deleted' });
    }
    catch (err) {
        logger_1.logger.error('Failed to delete message', { error: String(err) });
        res.status(500).json({ error: 'Failed to delete message' });
    }
});
