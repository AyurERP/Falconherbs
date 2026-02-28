/**
 * JARVIS Conversation Service
 * All database operations for conversations and messages.
 * Routes NEVER touch the database directly.
 */

import { v4 as uuidv4 } from 'uuid';
import { db } from '../db/connection';
import { logger } from '../utils/logger';
import type {
  Conversation,
  Message,
  CreateConversationInput,
  CreateMessageInput,
  UpdateConversationInput,
  PaginationParams,
  PaginatedResponse,
  ConversationWithMessages,
} from '../types';

export function createConversation(input?: CreateConversationInput): Conversation {
  const id = uuidv4();
  const title = input?.title?.trim() || 'New Conversation';

  const stmt = db.prepare(
    `INSERT INTO conversations (id, title) VALUES (?, ?)`
  );
  stmt.run(id, title);

  const row = db.prepare('SELECT * FROM conversations WHERE id = ?').get(id) as Conversation;
  logger.info('Conversation created', { id });
  return row;
}

export function getConversations(pagination: PaginationParams): PaginatedResponse<Conversation> {
  const { page, limit } = pagination;
  const offset = (page - 1) * limit;

  const countStmt = db.prepare('SELECT COUNT(*) as total FROM conversations');
  const { total } = countStmt.get() as { total: number };

  const stmt = db.prepare(`
    SELECT
      c.id,
      c.title,
      c.created_at,
      c.updated_at,
      (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as message_count,
      (SELECT SUBSTR(content, 1, 100) FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) as last_message_preview
    FROM conversations c
    ORDER BY c.updated_at DESC
    LIMIT ? OFFSET ?
  `);
  const rows = stmt.all(limit, offset) as Conversation[];

  return {
    data: rows,
    pagination: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit) || 1,
    },
  };
}

export function getConversationById(id: string): ConversationWithMessages | null {
  const convRow = db.prepare('SELECT * FROM conversations WHERE id = ?').get(id);
  if (!convRow) return null;

  const messages = db.prepare(
    'SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC'
  ).all(id) as Message[];

  const conversation = convRow as Conversation;
  return {
    ...conversation,
    messages,
  };
}

export function updateConversation(id: string, input: UpdateConversationInput): Conversation | null {
  const exists = db.prepare('SELECT id FROM conversations WHERE id = ?').get(id);
  if (!exists) return null;

  const stmt = db.prepare(
    `UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?`
  );
  stmt.run(input.title.trim(), id);

  const row = db.prepare('SELECT * FROM conversations WHERE id = ?').get(id) as Conversation;
  return row;
}

export function deleteConversation(id: string): boolean {
  const result = db.prepare('DELETE FROM conversations WHERE id = ?').run(id);
  if (result.changes > 0) {
    logger.info('Conversation deleted', { id });
    return true;
  }
  return false;
}

export function addMessage(conversationId: string, input: CreateMessageInput): Message | null {
  const exists = db.prepare('SELECT id FROM conversations WHERE id = ?').get(conversationId);
  if (!exists) return null;

  const id = uuidv4();
  const modelUsed = input.model_used?.trim() || null;
  const tokensUsed = input.tokens_used ?? 0;

  db.transaction(() => {
    db.prepare(`
      INSERT INTO messages (id, conversation_id, role, content, model_used, tokens_used)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(id, conversationId, input.role, input.content, modelUsed, tokensUsed);

    db.prepare(
      `UPDATE conversations SET updated_at = datetime('now') WHERE id = ?`
    ).run(conversationId);
  })();

  const row = db.prepare('SELECT * FROM messages WHERE id = ?').get(id) as Message;
  logger.info('Message added to conversation', { conversationId, role: input.role });
  return row;
}

export function getMessages(
  conversationId: string,
  pagination: PaginationParams
): PaginatedResponse<Message> | null {
  const exists = db.prepare('SELECT id FROM conversations WHERE id = ?').get(conversationId);
  if (!exists) return null;

  const { page, limit } = pagination;
  const offset = (page - 1) * limit;

  const countStmt = db.prepare(
    'SELECT COUNT(*) as total FROM messages WHERE conversation_id = ?'
  );
  const { total } = countStmt.get(conversationId) as { total: number };

  const stmt = db.prepare(`
    SELECT * FROM messages WHERE conversation_id = ?
    ORDER BY created_at ASC
    LIMIT ? OFFSET ?
  `);
  const rows = stmt.all(conversationId, limit, offset) as Message[];

  return {
    data: rows,
    pagination: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit) || 1,
    },
  };
}

export function deleteMessage(conversationId: string, messageId: string): boolean {
  const result = db.prepare(
    'DELETE FROM messages WHERE id = ? AND conversation_id = ?'
  ).run(messageId, conversationId);
  return result.changes > 0;
}

export function searchConversations(
  query: string,
  pagination: PaginationParams
): PaginatedResponse<Conversation> {
  const { page, limit } = pagination;
  const offset = (page - 1) * limit;
  const searchTerm = `%${query.trim()}%`;

  const countStmt = db.prepare(`
    SELECT COUNT(DISTINCT c.id) as total
    FROM conversations c
    LEFT JOIN messages m ON m.conversation_id = c.id
    WHERE c.title LIKE ? OR m.content LIKE ?
  `);
  const { total } = countStmt.get(searchTerm, searchTerm) as { total: number };

  const stmt = db.prepare(`
    SELECT
      c.id,
      c.title,
      c.created_at,
      c.updated_at,
      (SELECT COUNT(*) FROM messages m2 WHERE m2.conversation_id = c.id) as message_count,
      (SELECT SUBSTR(content, 1, 100) FROM messages m3 WHERE m3.conversation_id = c.id ORDER BY m3.created_at DESC LIMIT 1) as last_message_preview
    FROM conversations c
    LEFT JOIN messages m ON m.conversation_id = c.id
    WHERE c.title LIKE ? OR m.content LIKE ?
    GROUP BY c.id
    ORDER BY
      CASE WHEN c.title LIKE ? THEN 0 ELSE 1 END,
      c.updated_at DESC
    LIMIT ? OFFSET ?
  `);
  const rows = stmt.all(searchTerm, searchTerm, searchTerm, limit, offset) as Conversation[];

  return {
    data: rows,
    pagination: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit) || 1,
    },
  };
}

export function getRecentContext(
  conversationId: string,
  messageCount: number = 20
): Message[] | null {
  const exists = db.prepare('SELECT id FROM conversations WHERE id = ?').get(conversationId);
  if (!exists) return null;

  const stmt = db.prepare(`
    SELECT * FROM (
      SELECT * FROM messages
      WHERE conversation_id = ?
      ORDER BY created_at DESC
      LIMIT ?
    ) sub
    ORDER BY created_at ASC
  `);
  const rows = stmt.all(conversationId, messageCount) as Message[];
  return rows;
}
