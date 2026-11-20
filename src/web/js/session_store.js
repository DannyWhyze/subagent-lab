/**
 * Session storage persistence layer for Subagent Lab Explorer.
 * Serializes and restores client session state across page reloads.
 */

export const STORAGE_KEY = 'subagent_lab_session_state';

/**
 * Persists application state to sessionStorage.
 * @param {Object} state - The complete session state object to persist.
 */
export function saveSessionState(state) {
    if (!state || typeof state !== 'object') return;
    try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
        console.warn('Failed to save session state to sessionStorage', e);
    }
}

/**
 * Restores application state from sessionStorage.
 * @returns {Object|null} The parsed state object or null if not found/invalid.
 */
export function restoreSessionState() {
    try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        return JSON.parse(raw);
    } catch (e) {
        console.warn('Failed to restore session state from sessionStorage', e);
        return null;
    }
}

/**
 * Clears saved session state from sessionStorage.
 */
export function clearSessionState() {
    try {
        sessionStorage.removeItem(STORAGE_KEY);
    } catch (e) {
        console.warn('Failed to clear session state from sessionStorage', e);
    }
}
