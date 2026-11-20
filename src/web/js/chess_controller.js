/**
 * Chess interaction and state controller for Subagent Lab Explorer.
 * Coordinates between ChessBoardComponent, backend move validation API, and AI counter-turns.
 */

import { ChessBoardComponent, DEFAULT_FEN } from './chess_board.js';

/**
 * Controller managing chessboard UI, move validations, and game modes.
 */
export class ChessController {
    /**
     * @param {Object} elements - UI DOM elements for chess.
     * @param {Object} callbacks - Interaction callbacks.
     */
    constructor(elements, callbacks = {}) {
        this.chessPanel = elements.chessPanel;
        this.chessBoardView = elements.chessBoardView;
        this.chessTurnBadge = elements.chessTurnBadge;
        this.chessStatusBadge = elements.chessStatusBadge;
        this.chessMoveInfo = elements.chessMoveInfo;
        this.chessSpectatorBtn = elements.chessSpectatorBtn;
        this.chessPlayWhiteBtn = elements.chessPlayWhiteBtn;
        this.chessPlayBlackBtn = elements.chessPlayBlackBtn;
        this.chessResetBtn = elements.chessResetBtn;

        this.onTriggerAiCounter = callbacks.onTriggerAiCounter || (async () => {});
        this.onSelectPattern = callbacks.onSelectPattern || (() => {});
        this.onSetPrompt = callbacks.onSetPrompt || (() => {});
        this.onRunQuery = callbacks.onRunQuery || (() => {});
        this.onSaveState = callbacks.onSaveState || (() => {});
        this.isExecuting = callbacks.isExecuting || (() => false);

        this.chessBoard = null;
    }

    /**
     * Initializes the ChessBoardComponent with move callback.
     * @param {Function} getSessionId - Function returning current session ID string.
     */
    init(getSessionId) {
        if (!this.chessBoardView) return;
        this.chessBoard = new ChessBoardComponent(this.chessBoardView, {
            onMove: (moveStr) => {
                const sessionId = typeof getSessionId === 'function' ? getSessionId() : getSessionId;
                this.handleHumanMove(moveStr, sessionId);
            },
        });
    }

    /**
     * Submits a validated human move to the backend API and initiates the AI counter-turn.
     * @param {string} moveStr - UCI move string (e.g. "e2e4").
     * @param {string} sessionId - Active session ID.
     */
    async handleHumanMove(moveStr, sessionId) {
        if (this.isExecuting()) return;

        if (this.chessStatusBadge) {
            this.chessStatusBadge.textContent = 'Status: Validating Move...';
        }

        try {
            const resp = await fetch('/api/chess/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    move: moveStr,
                }),
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: 'Failed to apply move.' }));
                if (this.chessMoveInfo) {
                    this.chessMoveInfo.textContent = `Illegal Move: ${err.detail || 'Try another move.'}`;
                }
                if (this.chessStatusBadge) {
                    this.chessStatusBadge.textContent = 'Status: Illegal Move';
                }
                return;
            }

            const data = await resp.json();
            if (this.chessBoard) {
                this.chessBoard.renderFromFEN(data.fen, data.legal_moves, data.last_move);
            }
            if (this.chessMoveInfo) {
                this.chessMoveInfo.textContent = `You played: ${data.san} (${data.last_move})`;
            }

            if (data.game_over) {
                if (this.chessStatusBadge) {
                    this.chessStatusBadge.textContent = 'Status: Game Over';
                }
                return;
            }

            await this.onTriggerAiCounter();
        } catch (e) {
            console.error('Chess move error:', e);
            if (this.chessMoveInfo) {
                this.chessMoveInfo.textContent = `Move error: ${e.message}`;
            }
        }
    }

    /**
     * Updates chessboard view and telemetry from incoming SSE chess_board event.
     * @param {Object} payload - chess_board event payload.
     */
    handleStreamBoardEvent(payload) {
        if (!payload) return;
        if (this.chessBoard) {
            this.chessBoard.renderFromFEN(payload.fen, payload.legal_moves, payload.last_move);
        }
        if (this.chessTurnBadge) {
            this.chessTurnBadge.textContent = `Turn: ${payload.turn} (${payload.current_player})`;
        }
        if (this.chessStatusBadge) {
            this.chessStatusBadge.textContent = payload.is_check
                ? 'Status: Check!'
                : (payload.is_game_over
                    ? `Status: Game Over (${payload.result || ''})`
                    : 'Status: In Progress');
        }
        if (this.chessMoveInfo) {
            this.chessMoveInfo.textContent = payload.last_move
                ? `Last Move: ${payload.san || payload.last_move}${payload.thought ? ' - ' + payload.thought : ''}`
                : 'Match in Progress';
        }
    }

    /**
     * Fetches board state for current session from backend.
     * @param {string} sessionId - Active session ID.
     */
    async fetchState(sessionId) {
        if (!this.chessBoard) return;
        try {
            const res = await fetch(`/api/chess/state?session_id=${sessionId}`);
            if (res.ok) {
                const state = await res.json();
                this.chessBoard.renderFromFEN(state.fen, state.legal_moves);
                if (this.chessTurnBadge) {
                    this.chessTurnBadge.textContent = `Turn: ${state.turn} (${state.current_player})`;
                }
            } else {
                this.chessBoard.renderFromFEN(DEFAULT_FEN);
            }
        } catch {
            this.chessBoard.renderFromFEN(DEFAULT_FEN);
        }
    }

    /**
     * Sets up event listeners for chess control buttons.
     * @param {Function} getSessionId - Function returning active session ID.
     */
    setupEventListeners(getSessionId) {
        if (this.chessSpectatorBtn) {
            this.chessSpectatorBtn.addEventListener('click', () => {
                this.onSelectPattern('ms_chess');
                this.onSetPrompt('spectator:4');
                this.onRunQuery();
            });
        }

        if (this.chessPlayWhiteBtn) {
            this.chessPlayWhiteBtn.addEventListener('click', async () => {
                this.onSelectPattern('ms_chess');
                if (this.chessBoard) {
                    this.chessBoard.setPlayerMode('white');
                }
                if (this.chessTurnBadge) this.chessTurnBadge.textContent = 'Turn: 1 (White - Your Turn)';
                if (this.chessStatusBadge) this.chessStatusBadge.textContent = 'Status: Play White';
                if (this.chessMoveInfo) this.chessMoveInfo.textContent = 'Your turn. Click a white piece (e.g. e2) to view legal destinations.';
                const sessionId = typeof getSessionId === 'function' ? getSessionId() : getSessionId;
                await this.fetchState(sessionId);
            });
        }

        if (this.chessPlayBlackBtn) {
            this.chessPlayBlackBtn.addEventListener('click', async () => {
                this.onSelectPattern('ms_chess');
                if (this.chessBoard) {
                    this.chessBoard.setPlayerMode('black');
                }
                if (this.chessTurnBadge) this.chessTurnBadge.textContent = 'Turn: 1 (White - AI Thinking)';
                if (this.chessStatusBadge) this.chessStatusBadge.textContent = 'Status: Play Black';
                if (this.chessMoveInfo) this.chessMoveInfo.textContent = 'You play Black. AI White is computing the opening move...';
                await this.onTriggerAiCounter();
            });
        }

        if (this.chessResetBtn) {
            this.chessResetBtn.addEventListener('click', () => {
                if (this.chessBoard) {
                    this.chessBoard.setPlayerMode('spectator');
                    this.chessBoard.renderFromFEN(DEFAULT_FEN);
                }
                if (this.chessTurnBadge) this.chessTurnBadge.textContent = 'Turn: 1 (White)';
                if (this.chessStatusBadge) this.chessStatusBadge.textContent = 'Status: Ready';
                if (this.chessMoveInfo) this.chessMoveInfo.textContent = 'Board reset to starting position.';
                this.onSetPrompt('spectator:4');
                this.onSaveState();
            });
        }
    }

    /**
     * Returns serializable chess state for session persistence.
     * @returns {Object|null} Chess state object.
     */
    getState() {
        if (!this.chessBoard) return null;
        return {
            fen: this.chessBoard.fen,
            last_move: this.chessBoard.lastMove,
            player_color: this.chessBoard.playerColor
        };
    }

    /**
     * Restores chessboard state from saved session object.
     * @param {Object} state - Serialized chess state.
     */
    restoreState(state) {
        if (!state || !this.chessBoard) return;
        this.chessBoard.setPlayerMode(state.player_color || 'spectator');
        this.chessBoard.renderFromFEN(state.fen || DEFAULT_FEN, [], state.last_move);
    }

    /**
     * Resets board to default spectator state.
     */
    reset() {
        if (this.chessBoard) {
            this.chessBoard.setPlayerMode('spectator');
            this.chessBoard.renderFromFEN(DEFAULT_FEN);
        }
    }
}
