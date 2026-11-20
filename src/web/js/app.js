/**
 * Main Frontend Application Controller for Subagent Lab Explorer.
 * Coordinates between modular controllers: chat renderer, patterns, chess, and session persistence.
 */

import { startStream, abortStream } from './stream.js';
import { saveSessionState, restoreSessionState, clearSessionState } from './session_store.js';
import { ChatRenderer, scrollToBottomIfNearEnd, showSystemNotice } from './chat_renderer.js';
import { PatternsController } from './patterns_controller.js';
import { ChessController } from './chess_controller.js';

// DOM Elements
const statusBadge = document.getElementById('statusBadge');
const patternSelect = document.getElementById('patternSelect');
const thinkingSelect = document.getElementById('thinkingSelect');
const runBtn = document.getElementById('runBtn');
const abortBtn = document.getElementById('abortBtn');
const clearBtn = document.getElementById('clearBtn');
const chatContainer = document.getElementById('chatContainer');
const promptInput = document.getElementById('promptInput');
const examplesWrapper = document.getElementById('examplesWrapper');
const examplesChips = document.getElementById('examplesChips');

// Metric Elements
const metricTtft = document.getElementById('metricTtft');
const metricDuration = document.getElementById('metricDuration');
const metricTokens = document.getElementById('metricTokens');
const metricToolCalls = document.getElementById('metricToolCalls');

// Inspector Elements
const metaFramework = document.getElementById('metaFramework');
const metaIsolation = document.getElementById('metaIsolation');
const metaDesc = document.getElementById('metaDesc');
const stageTimeline = document.getElementById('stageTimeline');

// Chess Elements
const chessPanel = document.getElementById('chess-panel');
const chessBoardView = document.getElementById('chess-board-view');
const chessTurnBadge = document.getElementById('chessTurnBadge');
const chessStatusBadge = document.getElementById('chessStatusBadge');
const chessSpectatorBtn = document.getElementById('chessSpectatorBtn');
const chessPlayWhiteBtn = document.getElementById('chessPlayWhiteBtn');
const chessPlayBlackBtn = document.getElementById('chessPlayBlackBtn');
const chessResetBtn = document.getElementById('chessResetBtn');
const chessMoveInfo = document.getElementById('chessMoveInfo');

// Application State
let currentSessionId = 'sess_' + Math.random().toString(36).substring(2, 10);
let currentStageTimeline = [];
let isExecuting = false;

// Component Instances
const chatRenderer = new ChatRenderer(chatContainer);

const patternsController = new PatternsController(
    {
        patternSelect,
        thinkingSelect,
        statusBadge,
        metaFramework,
        metaIsolation,
        metaDesc,
        examplesWrapper,
        examplesChips,
        chessPanel,
    },
    {
        onSelectPrompt: (promptText) => {
            promptInput.value = promptText;
            promptInput.focus();
        },
        onSaveState: () => saveCurrentSession(),
        fetchChessState: (sessId, board, turnBadge) => chessController.fetchState(sessId),
    }
);

const chessController = new ChessController(
    {
        chessPanel,
        chessBoardView,
        chessTurnBadge,
        chessStatusBadge,
        chessMoveInfo,
        chessSpectatorBtn,
        chessPlayWhiteBtn,
        chessPlayBlackBtn,
        chessResetBtn,
    },
    {
        onTriggerAiCounter: async () => triggerAiCounterTurn(),
        onSelectPattern: (id) => patternsController.setSelectedPatternId(id),
        onSetPrompt: (promptText) => { promptInput.value = promptText; },
        onRunQuery: () => runQuery(),
        onSaveState: () => saveCurrentSession(),
        isExecuting: () => isExecuting,
    }
);

/**
 * Persists current session state using session_store.
 */
function saveCurrentSession() {
    const effectiveThinking = patternsController.getEffectiveThinking();
    saveSessionState({
        session_id: currentSessionId,
        last_pattern_id: patternsController.getSelectedPatternId(),
        last_thinking: effectiveThinking,
        chat_history: chatRenderer.getHistory(),
        stage_timeline: currentStageTimeline,
        metrics_summary: {
            ttft: metricTtft.textContent,
            duration: metricDuration.textContent,
            tokens: metricTokens.textContent,
            tool_calls: metricToolCalls.textContent,
        },
        chess_state: chessController.getState(),
    });
}

/**
 * Restores session state from session_store on page load.
 */
function restoreCurrentSession() {
    const state = restoreSessionState();
    if (!state) return;

    if (state.session_id) {
        currentSessionId = state.session_id;
    }

    if (state.last_thinking && thinkingSelect) {
        thinkingSelect.value = state.last_thinking;
    }

    if (state.metrics_summary) {
        metricTtft.textContent = state.metrics_summary.ttft || '0.0 ms';
        metricDuration.textContent = state.metrics_summary.duration || '0.0 ms';
        metricTokens.textContent = state.metrics_summary.tokens || '0';
        metricToolCalls.textContent = state.metrics_summary.tool_calls || '0';
    }

    if (Array.isArray(state.chat_history) && state.chat_history.length > 0) {
        chatRenderer.setHistory(state.chat_history);
    }

    if (Array.isArray(state.stage_timeline) && state.stage_timeline.length > 0) {
        stageTimeline.innerHTML = '';
        currentStageTimeline = state.stage_timeline;
        for (const item of currentStageTimeline) {
            const div = document.createElement('div');
            div.className = 'timeline-item';
            div.textContent = `Stage: ${item.stage} (Agent: ${item.agent})`;
            stageTimeline.appendChild(div);
        }
    }

    if (state.chess_state) {
        chessController.restoreState(state.chess_state);
    }
}

/**
 * Adds an execution stage item to the right-panel timeline.
 */
function addTimelineStage(stage, agent) {
    const emptyEl = stageTimeline.querySelector('.timeline-empty');
    if (emptyEl) {
        stageTimeline.innerHTML = '';
    }
    currentStageTimeline.push({ stage, agent });
    const item = document.createElement('div');
    item.className = 'timeline-item';
    item.textContent = `Stage: ${stage} (Agent: ${agent})`;
    stageTimeline.appendChild(item);
    scrollToBottomIfNearEnd(stageTimeline);
}

/**
 * Handles incoming SSE events from backend streaming endpoint.
 */
function handleStreamEvent(event) {
    const type = event.event_type;
    const payload = event.payload;

    if (type === 'stage') {
        addTimelineStage(payload.stage, payload.agent);
    } else if (type === 'subagent') {
        chatRenderer.handleSubagent(payload);
    } else if (type === 'tool_call') {
        chatRenderer.handleToolCall(payload);
    } else if (type === 'thought') {
        chatRenderer.appendThought(payload.delta, payload.source);
    } else if (type === 'code') {
        chatRenderer.appendCode(payload.delta, payload.source);
    } else if (type === 'token') {
        chatRenderer.appendToken(payload.delta, payload.source);
    } else if (type === 'metrics') {
        metricTtft.textContent = `${payload.ttft_ms.toFixed(1)} ms`;
        metricDuration.textContent = `${payload.total_duration_ms.toFixed(1)} ms`;
        metricTokens.textContent = payload.token_count.toString();
        metricToolCalls.textContent = payload.tool_calls.toString();
    } else if (type === 'chess_board') {
        chessController.handleStreamBoardEvent(payload);
        saveCurrentSession();
    } else if (type === 'done') {
        chatRenderer.handleDone(payload);
        saveCurrentSession();
    } else if (type === 'error') {
        showSystemNotice(chatContainer, `Error: ${payload.message}`, true);
    }
}

/**
 * Starts execution stream for user prompt.
 */
async function runQuery() {
    const prompt = promptInput.value.trim();
    const patternId = patternsController.getSelectedPatternId();

    if (!prompt) {
        showSystemNotice(chatContainer, 'Please enter a query prompt.', true);
        return;
    }
    if (!patternId) {
        showSystemNotice(chatContainer, 'Please select an architecture pattern.', true);
        return;
    }

    chatRenderer.addUserMessage(prompt);
    promptInput.value = '';
    isExecuting = true;
    chatRenderer.resetStreamingState();

    currentStageTimeline = [];
    stageTimeline.innerHTML = '<div class="timeline-empty">Execution in progress...</div>';

    runBtn.disabled = true;
    abortBtn.disabled = false;
    statusBadge.className = 'status-badge streaming';
    statusBadge.textContent = 'Status: Streaming';

    const reqData = {
        pattern_id: patternId,
        session_id: currentSessionId,
        prompt: prompt,
        thinking: patternsController.getEffectiveThinking(),
    };

    await startStream(
        '/api/stream',
        reqData,
        handleStreamEvent,
        (err) => {
            console.error('Stream failure:', err);
            handleStreamEvent({
                event_type: 'error',
                payload: { message: err.message },
            });
            finishExecution();
        },
        () => {
            finishExecution();
        }
    );
}

/**
 * Completes stream execution and restores controls.
 */
function finishExecution() {
    isExecuting = false;
    runBtn.disabled = false;
    abortBtn.disabled = true;
    statusBadge.className = 'status-badge connected';
    statusBadge.textContent = 'Status: Connected';
    chatRenderer.commitActiveCode();
    chatRenderer.commitActiveThought();
    chatRenderer.commitActiveAssistant();
    saveCurrentSession();
}

/**
 * Triggers the AI counter-move stream for the active chess session.
 */
async function triggerAiCounterTurn() {
    isExecuting = true;
    runBtn.disabled = true;
    abortBtn.disabled = false;
    statusBadge.className = 'status-badge streaming';
    statusBadge.textContent = 'Status: AI Thinking...';

    const reqData = {
        pattern_id: 'ms_chess',
        session_id: currentSessionId,
        prompt: 'ai_counter_turn',
        thinking: patternsController.getEffectiveThinking(),
    };

    await startStream(
        '/api/stream',
        reqData,
        handleStreamEvent,
        (err) => {
            console.error('Counter-turn stream failure:', err);
            handleStreamEvent({
                event_type: 'error',
                payload: { message: err.message },
            });
            finishExecution();
        },
        () => {
            finishExecution();
        }
    );
}

/**
 * Clears current output, resets metrics, and generates a fresh session.
 */
function clearOutput() {
    if (isExecuting) {
        abortStream();
    }
    chatRenderer.clear('Output cleared. Ready for new query.');
    stageTimeline.innerHTML = '<div class="timeline-empty">No active execution</div>';
    currentStageTimeline = [];
    currentSessionId = 'sess_' + Math.random().toString(36).substring(2, 10);

    chessController.reset();

    metricTtft.textContent = '0.0 ms';
    metricDuration.textContent = '0.0 ms';
    metricTokens.textContent = '0';
    metricToolCalls.textContent = '0';

    clearSessionState();
}

// Event Listeners Initialization
document.addEventListener('DOMContentLoaded', () => {
    chessController.init(() => currentSessionId);
    chessController.setupEventListeners(() => currentSessionId);

    restoreCurrentSession();

    const savedState = restoreSessionState();
    patternsController.loadPatterns(savedState?.last_pattern_id || null);

    patternSelect.addEventListener('change', () => {
        patternsController.updatePatternDetails(currentSessionId, chessController.chessBoard, chessTurnBadge);
    });

    if (thinkingSelect) {
        thinkingSelect.addEventListener('change', () => {
            saveCurrentSession();
        });
    }

    runBtn.addEventListener('click', runQuery);
    abortBtn.addEventListener('click', () => {
        abortStream();
        finishExecution();
    });
    clearBtn.addEventListener('click', clearOutput);

    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!runBtn.disabled) {
                runQuery();
            }
        }
    });
});
