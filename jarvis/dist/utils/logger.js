"use strict";
/**
 * JARVIS Logger Utility
 * Simple structured logging for the application.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.logger = void 0;
function formatMessage(level, message, meta) {
    const timestamp = new Date().toISOString();
    const metaStr = meta ? ` ${JSON.stringify(meta)}` : '';
    return `[${timestamp}] [${level.toUpperCase()}] ${message}${metaStr}`;
}
exports.logger = {
    info(message, meta) {
        console.log(formatMessage('info', message, meta));
    },
    warn(message, meta) {
        console.warn(formatMessage('warn', message, meta));
    },
    error(message, meta) {
        console.error(formatMessage('error', message, meta));
    },
    debug(message, meta) {
        if (process.env.NODE_ENV === 'development') {
            console.debug(formatMessage('debug', message, meta));
        }
    },
};
