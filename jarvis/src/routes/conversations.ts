/**
 * JARVIS Conversations Routes
 * REST API for conversations and messages.
 */

import { Router, Request, Response } from 'express';
import * as conversationService from '../services/conversationService';
import { logger } from '../utils/logger';

const VALID_ROLES = ['user', 'assistant', 'system'] as const;

function parsePagination(
  pageStr: string | undefined,
  limitStr: string | undefined,
  defaultLimit: number
): { page: number; limit: number } {
  let page = 1;
  let limit = defaultLimit;

  const p = parseInt(String(pageStr), 10);
  if (!isNaN(p) && p > 0) page = p;

  const l = parseInt(String(limitStr), 10);
  if (!isNaN(l) && l >= 1 && l <= 100) limit = l;

  return { page, limit };
}

export const conversationsRouter = Router();

// POST /api/conversations
conversationsRouter.post('/', (req: Request, res: Response) => {
  try {
    const body = req.body || {};
    const title = typeof body.title === 'string' ? body.title : undefined;

    const conversation = conversationService.createConversation({ title });
    res.status(201).json({ data: conversation });
  } catch (err) {
    logger.error('Failed to create conversation', { error: String(err) });
    res.status(500).json({ error: 'Failed to create conversation' });
  }
});

// GET /api/conversations
conversationsRouter.get('/', (req: Request, res: Response) => {
  try {
    const search = typeof req.query.search === 'string' ? req.query.search.trim() : undefined;
    const pagination = parsePagination(
      req.query.page as string,
      req.query.limit as string,
      20
    );

    if (search && search.length > 0) {
      const result = conversationService.searchConversations(search, pagination);
      res.status(200).json(result);
    } else {
      const result = conversationService.getConversations(pagination);
      res.status(200).json(result);
    }
  } catch (err) {
    logger.error('Failed to list conversations', { error: String(err) });
    res.status(500).json({ error: 'Failed to list conversations' });
  }
});

// GET /api/conversations/:id/messages (must be before /:id)
conversationsRouter.get('/:id/messages', (req: Request, res: Response) => {
  try {
    const { id: conversationId } = req.params;
    const pagination = parsePagination(
      req.query.page as string,
      req.query.limit as string,
      50
    );

    const result = conversationService.getMessages(conversationId, pagination);

    if (!result) {
      res.status(404).json({ error: 'Conversation not found' });
      return;
    }

    res.status(200).json(result);
  } catch (err) {
    logger.error('Failed to get messages', { error: String(err) });
    res.status(500).json({ error: 'Failed to get messages' });
  }
});

// GET /api/conversations/:id/context (must be before /:id)
conversationsRouter.get('/:id/context', (req: Request, res: Response) => {
  try {
    const { id: conversationId } = req.params;
    const countStr = req.query.count as string | undefined;
    let count = 20;

    const c = parseInt(String(countStr), 10);
    if (!isNaN(c) && c > 0) count = Math.min(c, 100);

    const messages = conversationService.getRecentContext(conversationId, count);

    if (!messages) {
      res.status(404).json({ error: 'Conversation not found' });
      return;
    }

    res.status(200).json({ data: messages });
  } catch (err) {
    logger.error('Failed to get context', { error: String(err) });
    res.status(500).json({ error: 'Failed to get context' });
  }
});

// GET /api/conversations/:id
conversationsRouter.get('/:id', (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const conversation = conversationService.getConversationById(id);

    if (!conversation) {
      res.status(404).json({ error: 'Conversation not found' });
      return;
    }

    res.status(200).json({ data: conversation });
  } catch (err) {
    logger.error('Failed to get conversation', { error: String(err) });
    res.status(500).json({ error: 'Failed to get conversation' });
  }
});

// PUT /api/conversations/:id
conversationsRouter.put('/:id', (req: Request, res: Response) => {
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
  } catch (err) {
    logger.error('Failed to update conversation', { error: String(err) });
    res.status(500).json({ error: 'Failed to update conversation' });
  }
});

// DELETE /api/conversations/:id
conversationsRouter.delete('/:id', (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const deleted = conversationService.deleteConversation(id);

    if (!deleted) {
      res.status(404).json({ error: 'Conversation not found' });
      return;
    }

    res.status(200).json({ message: 'Conversation deleted' });
  } catch (err) {
    logger.error('Failed to delete conversation', { error: String(err) });
    res.status(500).json({ error: 'Failed to delete conversation' });
  }
});

// POST /api/conversations/:id/messages
conversationsRouter.post('/:id/messages', (req: Request, res: Response) => {
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
  } catch (err) {
    logger.error('Failed to add message', { error: String(err) });
    res.status(500).json({ error: 'Failed to add message' });
  }
});

// DELETE /api/conversations/:id/messages/:messageId
conversationsRouter.delete('/:id/messages/:messageId', (req: Request, res: Response) => {
  try {
    const { id: conversationId, messageId } = req.params;
    const deleted = conversationService.deleteMessage(conversationId, messageId);

    if (!deleted) {
      res.status(404).json({ error: 'Message not found' });
      return;
    }

    res.status(200).json({ message: 'Message deleted' });
  } catch (err) {
    logger.error('Failed to delete message', { error: String(err) });
    res.status(500).json({ error: 'Failed to delete message' });
  }
});
