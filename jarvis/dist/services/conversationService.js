"use strict";
/**
 * JARVIS Conversation Service
 * All database operations for conversations and messages.
 * Routes NEVER touch the database directly.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.createConversation = createConversation;
exports.getConversations = getConversations;
exports.getConversationById = getConversationById;
exports.updateConversation = updateConversation;
exports.deleteConversation = deleteConversation;
exports.addMessage = addMessage;
exports.getMessages = getMessages;
exports.deleteMessage = deleteMessage;
exports.searchConversations = searchConversations;
exports.getRecentContext = getRecentContext;
const uuid_1 = require("uuid");
const connection_1 = require("../db/connection");
const logger_1 = require("../utils/logger");
function createConversation(input) {
    const id = (0, uuid_1.v4)();
    const title = input?.title?.trim() || 'New Conversation';
    const stmt = connection_1.db.prepare(`INSERT INTO conversations (id, title) VALUES (?, ?)`);
    stmt.run(id, title);
    const row = connection_1.db.prepare('SELECT * FROM conversations WHERE id = ?').get(id);
    logger_1.logger.info('Conversation created', { id });
    return row;
}
function getConversations(pagination) {
    const { page, limit } = pagination;
    const offset = (page - 1) * limit;
    const countStmt = connection_1.db.prepare('SELECT COUNT(*) as total FROM conversations');
    const { total } = countStmt.get();
    const stmt = connection_1.db.prepare(`
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
    const rows = stmt.all(limit, offset);
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
function getConversationById(id) {
    const convRow = connection_1.db.prepare('SELECT * FROM conversations WHERE id = ?').get(id);
    if (!convRow)
        return null;
    const messages = connection_1.db.prepare('SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC').all(id);
    const conversation = convRow;
    return {
        ...conversation,
        messages,
    };
}
function updateConversation(id, input) {
    const exists = connection_1.db.prepare('SELECT id FROM conversations WHERE id = ?').get(id);
    if (!exists)
        return null;
    const stmt = connection_1.db.prepare(`UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?`);
    stmt.run(input.title.trim(), id);
    const row = connection_1.db.prepare('SELECT * FROM conversations WHERE id = ?').get(id);
    return row;
}
function deleteConversation(id) {
    const result = connection_1.db.prepare('DELETE FROM conversations WHERE id = ?').run(id);
    if (result.changes > 0) {
        logger_1.logger.info('Conversation deleted', { id });
        return true;
    }
    return false;
}
function addMessage(conversationId, input) {
    const exists = connection_1.db.prepare('SELECT id FROM conversations WHERE id = ?').get(conversationId);
    if (!exists)
        return null;
    const id = (0, uuid_1.v4)();
    const modelUsed = input.model_used?.trim() || null;
    const tokensUsed = input.tokens_used ?? 0;
    connection_1.db.transaction(() => {
        connection_1.db.prepare(`
      INSERT INTO messages (id, conversation_id, role, content, model_used, tokens_used)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(id, conversationId, input.role, input.content, modelUsed, tokensUsed);
        connection_1.db.prepare(`UPDATE conversations SET updated_at = datetime('now') WHERE id = ?`).run(conversationId);
    })();
    const row = connection_1.db.prepare('SELECT * FROM messages WHERE id = ?').get(id);
    logger_1.logger.info('Message added to conversation', { conversationId, role: input.role });
    return row;
}
function getMessages(conversationId, pagination) {
    const exists = connection_1.db.prepare('SELECT id FROM conversations WHERE id = ?').get(conversationId);
    if (!exists)
        return null;
    const { page, limit } = pagination;
    const offset = (page - 1) * limit;
    const countStmt = connection_1.db.prepare('SELECT COUNT(*) as total FROM messages WHERE conversation_id = ?');
    const { total } = countStmt.get(conversationId);
    const stmt = connection_1.db.prepare(`
    SELECT * FROM messages WHERE conversation_id = ?
    ORDER BY created_at ASC
    LIMIT ? OFFSET ?
  `);
    const rows = stmt.all(conversationId, limit, offset);
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
function deleteMessage(conversationId, messageId) {
    const result = connection_1.db.prepare('DELETE FROM messages WHERE id = ? AND conversation_id = ?').run(messageId, conversationId);
    return result.changes > 0;
}
function searchConversations(query, pagination) {
    const { page, limit } = pagination;
    const offset = (page - 1) * limit;
    const searchTerm = `%${query.trim()}%`;
    const countStmt = connection_1.db.prepare(`
    SELECT COUNT(DISTINCT c.id) as total
    FROM conversations c
    LEFT JOIN messages m ON m.conversation_id = c.id
    WHERE c.title LIKE ? OR m.content LIKE ?
  `);
    const { total } = countStmt.get(searchTerm, searchTerm);
    const stmt = connection_1.db.prepare(`
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
    const rows = stmt.all(searchTerm, searchTerm, searchTerm, limit, offset);
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
function getRecentContext(conversationId, messageCount = 20) {
    const exists = connection_1.db.prepare('SELECT id FROM conversations WHERE id = ?').get(conversationId);
    if (!exists)
        return null;
    const stmt = connection_1.db.prepare(`
    SELECT * FROM (
      SELECT * FROM messages
      WHERE conversation_id = ?
      ORDER BY created_at DESC
      LIMIT ?
    ) sub
    ORDER BY created_at ASC
  `);
    const rows = stmt.all(conversationId, messageCount);
    return rows;
}
