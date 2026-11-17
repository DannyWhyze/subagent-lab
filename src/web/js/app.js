/**
 * Main Frontend Application Controller for Subagent Lab Explorer.
 * Accessible UI and end-to-end async persistence.
 */

import { startStream, abortStream } from './stream.js';
import { ChessBoardComponent, DEFAULT_FEN } from './chess_board.js';

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
let patternsData = [];
let currentSessionId = 'sess_' + Math.random().toString(36).substring(2, 10);
let activeAssistantTextNode = null;
let activeAssistantContainer = null;
let currentSpeaker = null;
let activeThoughtTextNode = null;
let currentThoughtSpeaker = null;
let currentThoughtContentEl = null;
let hadInterveningToolCall = false;
let activeCodeTextNode = null;
let currentCodeSpeaker = null;
let currentCodeContentEl = null;
let currentChatHistory = [];
let currentStageTimeline = [];
let isExecuting = false;
let chessBoard = null;

const STORAGE_KEY = 'subagent_lab_session_state';

/**
 * Scrolls container to bottom only if the user is already near the bottom.
 */
function scrollToBottomIfNearEnd(el, threshold = 80) {
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceToBottom <= threshold) {
        el.scrollTop = el.scrollHeight;
    }
}

/**
 * Commits active generated code node to history and resets references.
 */
function commitActiveCode() {
    if (activeCodeTextNode && activeCodeTextNode.nodeValue) {
        currentChatHistory.push({
            type: 'code',
            speaker: currentCodeSpeaker,
            content: activeCodeTextNode.nodeValue
        });
        activeCodeTextNode = null;
        currentCodeSpeaker = null;
        currentCodeContentEl = null;
    }
}

/**
 * Resets all streaming state variables before a new turn or upon clearing.
 */
function resetStreamingState() {
    activeAssistantTextNode = null;
    activeAssistantContainer = null;
    currentSpeaker = null;
    activeThoughtTextNode = null;
    currentThoughtSpeaker = null;
    currentThoughtContentEl = null;
    hadInterveningToolCall = false;
    activeCodeTextNode = null;
    currentCodeSpeaker = null;
    currentCodeContentEl = null;
}

/**
 * Safely parses markdown to HTML while stripping dangerous tags and script attributes.
 */
function renderSafeMarkdown(targetEl, markdownText) {
    if (!targetEl) return;
    const raw = markdownText || '';
    if (!window.marked || typeof window.marked.parse !== 'function') {
        targetEl.textContent = raw;
        return;
    }
    try {
        const dirtyHtml = window.marked.parse(raw);
        const parser = new DOMParser();
        const doc = parser.parseFromString(dirtyHtml, 'text/html');

        // Remove dangerous tags
        const dangerousSelectors = 'script, iframe, object, embed, style, link';
        doc.body.querySelectorAll(dangerousSelectors).forEach((el) => el.remove());

        // Sanitize attributes across all remaining elements
        const allElements = doc.body.querySelectorAll('*');
        allElements.forEach((el) => {
            Array.from(el.attributes).forEach((attr) => {
                const name = attr.name.toLowerCase();
                const val = attr.value.trim().toLowerCase();
                if (name.startsWith('on')) {
                    el.removeAttribute(attr.name);
                } else if ((name === 'href' || name === 'src') && val.startsWith('javascript:')) {
                    el.removeAttribute(attr.name);
                }
            });
        });

        targetEl.innerHTML = doc.body.innerHTML;
    } catch (e) {
        console.warn('Failed to parse and sanitize markdown', e);
        targetEl.textContent = raw;
    }
}

/**
 * Renders a system or error message into the chat container.
 */
function showSystemNotice(message, isError = false) {
    const noticeEl = document.createElement('div');
    noticeEl.className = `message system-message${isError ? ' error-message' : ''}`;
    noticeEl.textContent = message;
    chatContainer.appendChild(noticeEl);
    scrollToBottomIfNearEnd(chatContainer);
}

/**
 * Resolves the effective thinking effort parameter for backend requests.
 * Always returns a valid Literal ("off", "low", "medium", "high") even when UI dropdown is disabled.
 */
function getEffectiveThinking() {
    if (!thinkingSelect || thinkingSelect.value === 'disabled_na') {
        return 'off';
    }
    return thinkingSelect.value;
}

/**
 * Persists current session state to sessionStorage.
 */
function saveSessionState() {
    const effectiveThinking = thinkingSelect && thinkingSelect.value !== 'disabled_na'
        ? thinkingSelect.value
        : (thinkingSelect?.dataset?.prevValue || 'off');

    const state = {
        session_id: currentSessionId,
        last_pattern_id: patternSelect.value,
        last_thinking: effectiveThinking,
        chat_history: currentChatHistory,
        stage_timeline: currentStageTimeline,
        metrics_summary: {
            ttft: metricTtft.textContent,
            duration: metricDuration.textContent,
            tokens: metricTokens.textContent,
            tool_calls: metricToolCalls.textContent
        },
        chess_state: chessBoard ? {
            fen: chessBoard.fen,
            last_move: chessBoard.lastMove,
            player_color: chessBoard.playerColor
        } : null
    };
    try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
        console.warn('Failed to save to sessionStorage', e);
    }
}

/**
 * Restores session state from sessionStorage on page load.
 */
function restoreSessionState() {
    try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const state = JSON.parse(raw);

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
            chatContainer.innerHTML = '';
            currentChatHistory = state.chat_history;
            for (const item of currentChatHistory) {
                renderHistoryItem(item);
            }
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

        if (state.chess_state && chessBoard) {
            chessBoard.setPlayerMode(state.chess_state.player_color || 'spectator');
            chessBoard.renderFromFEN(state.chess_state.fen || DEFAULT_FEN, [], state.chess_state.last_move);
        }
    } catch (e) {
        console.warn('Failed to restore from sessionStorage', e);
    }
}

/**
 * Renders an existing historical message into the chat container.
 */
function renderHistoryItem(item) {
    const msgEl = document.createElement('div');
    if (item.type === 'user') {
        msgEl.className = 'message user-message';
        msgEl.textContent = item.content;
    } else if (item.type === 'thought') {
        const details = document.createElement('details');
        details.className = 'thought-box';
        const summary = document.createElement('summary');
        summary.className = 'thought-summary';
        summary.textContent = `Thinking Process (${item.speaker || 'Assistant'})`;
        details.appendChild(summary);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'thought-content';
        contentDiv.textContent = item.content;
        details.appendChild(contentDiv);

        chatContainer.appendChild(details);
        scrollToBottomIfNearEnd(chatContainer);
        return;
    } else if (item.type === 'code') {
        const details = document.createElement('details');
        details.className = 'code-box';
        const summary = document.createElement('summary');
        summary.className = 'code-summary';
        summary.textContent = `Generated Execution Code (${item.speaker || 'ast_code_agent'})`;
        details.appendChild(summary);

        const contentPre = document.createElement('pre');
        contentPre.className = 'code-content';
        contentPre.textContent = item.content;
        details.appendChild(contentPre);

        chatContainer.appendChild(details);
        scrollToBottomIfNearEnd(chatContainer);
        return;
    } else if (item.type === 'assistant') {
        msgEl.className = 'message assistant-message';
        if (item.speaker) {
            const badge = document.createElement('div');
            badge.className = 'speaker-badge';
            badge.textContent = item.speaker;
            msgEl.appendChild(badge);
        }
        const textContainer = document.createElement('div');
        textContainer.className = 'message-text';
        renderSafeMarkdown(textContainer, item.content);
        msgEl.appendChild(textContainer);
    } else if (item.type === 'tool') {
        const details = document.createElement('details');
        details.className = 'tool-box tool-event';
        const summary = document.createElement('summary');
        summary.className = 'tool-summary';
        summary.textContent = `Tool: ${item.tool}`;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'tool-content';
        const formattedInput = item.input
            ? (typeof item.input === 'object' ? JSON.stringify(item.input, null, 2) : item.input)
            : '';
        content.textContent = formattedInput
            ? `Input:\n${formattedInput}\n\nOutput:\n${item.output || ''}`
            : `Output:\n${item.output || ''}`;
        details.appendChild(content);

        chatContainer.appendChild(details);
        scrollToBottomIfNearEnd(chatContainer);
        return;
    } else if (item.type === 'subagent') {
        const details = document.createElement('details');
        details.className = 'subagent-box subagent-event';
        const summary = document.createElement('summary');
        summary.className = 'subagent-summary';
        summary.textContent = `Subagent: ${item.name}`;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'subagent-content';
        content.textContent = `Task: ${item.task}`;
        details.appendChild(content);

        chatContainer.appendChild(details);
        scrollToBottomIfNearEnd(chatContainer);
        return;
    }
    chatContainer.appendChild(msgEl);
    scrollToBottomIfNearEnd(chatContainer);
}

/**
 * Fetches pattern metadata from backend.
 */
async function loadPatterns() {
    try {
        const res = await fetch('/api/patterns');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        patternsData = await res.json();

        patternSelect.innerHTML = '';
        for (const p of patternsData) {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            patternSelect.appendChild(opt);
        }

        // Restore previously selected pattern if saved
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (raw) {
            const state = JSON.parse(raw);
            if (state.last_pattern_id && patternsData.some(p => p.id === state.last_pattern_id)) {
                patternSelect.value = state.last_pattern_id;
            }
        }

        updatePatternDetails();
        statusBadge.className = 'status-badge connected';
        statusBadge.textContent = 'Status: Connected';
    } catch (err) {
        statusBadge.className = 'status-badge error';
        statusBadge.textContent = 'Status: Disconnected';
        console.error('Failed to load patterns', err);
    }
}

/**
 * Renders clickable example prompt chips for the active pattern.
 */
function renderExamplePrompts(pattern) {
    if (!examplesChips) return;
    examplesChips.innerHTML = '';
    const prompts = pattern.example_prompts || [];

    if (prompts.length === 0) {
        if (examplesWrapper) examplesWrapper.style.display = 'none';
        return;
    }

    if (examplesWrapper) examplesWrapper.style.display = 'flex';
    for (const promptText of prompts) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'example-chip';
        btn.textContent = promptText;
        btn.addEventListener('click', () => {
            promptInput.value = promptText;
            promptInput.focus();
        });
        examplesChips.appendChild(btn);
    }
}

/**
 * Updates pattern details card based on current dropdown selection.
 */
function updatePatternDetails() {
    const selectedId = patternSelect.value;
    const pattern = patternsData.find(p => p.id === selectedId);
    if (!pattern) return;

    metaFramework.textContent = pattern.framework;
    metaIsolation.textContent = pattern.isolation_type;
    metaDesc.textContent = pattern.description;
    renderExamplePrompts(pattern);

    if (thinkingSelect) {
        if (selectedId === 'ms_chess') {
            if (!thinkingSelect.dataset.prevValue && thinkingSelect.value !== 'disabled_na') {
                thinkingSelect.dataset.prevValue = thinkingSelect.value;
            }
            let naOption = thinkingSelect.querySelector('option[value="disabled_na"]');
            if (!naOption) {
                naOption = document.createElement('option');
                naOption.value = 'disabled_na';
                naOption.textContent = 'Disabled (N/A)';
                thinkingSelect.appendChild(naOption);
            }
            thinkingSelect.value = 'disabled_na';
            thinkingSelect.disabled = true;
            thinkingSelect.title = 'Thinking mode not applicable for Chess (uses tactical prompt evaluation)';
        } else {
            const naOption = thinkingSelect.querySelector('option[value="disabled_na"]');
            if (naOption) {
                naOption.remove();
            }
            if (thinkingSelect.dataset.prevValue) {
                thinkingSelect.value = thinkingSelect.dataset.prevValue;
                delete thinkingSelect.dataset.prevValue;
            }
            thinkingSelect.disabled = false;
            thinkingSelect.title = 'Select thinking effort for supported patterns';
        }
    }

    if (chessPanel) {
        const isChess = selectedId === 'ms_chess';
        chessPanel.classList.toggle('hidden', !isChess);
        if (isChess && chessBoard) {
            fetch(`/api/chess/state?session_id=${currentSessionId}`)
                .then((res) => (res.ok ? res.json() : null))
                .then((state) => {
                    if (state) {
                        chessBoard.renderFromFEN(state.fen, state.legal_moves);
                        if (chessTurnBadge) {
                            chessTurnBadge.textContent = `Turn: ${state.turn} (${state.current_player})`;
                        }
                    } else {
                        chessBoard.renderFromFEN(DEFAULT_FEN);
                    }
                })
                .catch(() => {
                    chessBoard.renderFromFEN(DEFAULT_FEN);
                });
        }
    }

    saveSessionState();
}

/**
 * Commits any in-progress thought content to history and cleans up references.
 */
function commitActiveThought() {
    if (currentThoughtContentEl && currentThoughtContentEl.textContent) {
        currentChatHistory.push({
            type: 'thought',
            speaker: currentThoughtSpeaker || 'Assistant',
            content: currentThoughtContentEl.textContent
        });
    }
    activeThoughtTextNode = null;
    currentThoughtSpeaker = null;
    currentThoughtContentEl = null;
    hadInterveningToolCall = false;
}

/**
 * Commits and parses markdown for the active assistant message response.
 */
function commitActiveAssistant() {
    if (activeAssistantTextNode && activeAssistantTextNode.nodeValue) {
        const rawContent = activeAssistantTextNode.nodeValue;
        currentChatHistory.push({
            type: 'assistant',
            speaker: currentSpeaker,
            content: rawContent
        });
        if (activeAssistantContainer) {
            renderSafeMarkdown(activeAssistantContainer, rawContent);
        }
        activeAssistantTextNode = null;
        activeAssistantContainer = null;
        currentSpeaker = null;
    }
}

/**
 * Appends reasoning tokens into a collapsible thought-box container.
 * Unifies sequential thought turns from the same speaker across tool calls into one continuous box.
 */
function appendThought(delta, source) {
    const speaker = source || 'Assistant';
    if (!currentThoughtContentEl || currentThoughtSpeaker !== speaker) {
        commitActiveThought();
        commitActiveCode();
        commitActiveAssistant();

        currentThoughtSpeaker = speaker;
        const details = document.createElement('details');
        details.className = 'thought-box';

        const summary = document.createElement('summary');
        summary.className = 'thought-summary';
        summary.textContent = `Thinking Process (${speaker})`;
        details.appendChild(summary);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'thought-content';
        activeThoughtTextNode = document.createTextNode('');
        contentDiv.appendChild(activeThoughtTextNode);
        details.appendChild(contentDiv);

        currentThoughtContentEl = contentDiv;
        chatContainer.appendChild(details);
        hadInterveningToolCall = false;
    } else if (hadInterveningToolCall) {
        const divider = document.createTextNode('\n\n--- [Continuation after Tool Execution] ---\n');
        currentThoughtContentEl.appendChild(divider);
        activeThoughtTextNode = document.createTextNode('');
        currentThoughtContentEl.appendChild(activeThoughtTextNode);
        hadInterveningToolCall = false;
    }

    if (!activeThoughtTextNode) {
        activeThoughtTextNode = document.createTextNode('');
        currentThoughtContentEl.appendChild(activeThoughtTextNode);
    }

    activeThoughtTextNode.appendData(delta);
    scrollToBottomIfNearEnd(chatContainer);
}

/**
 * Appends generated execution code into a collapsible code-box container.
 */
function appendCode(delta, source) {
    const speaker = source || 'ast_code_agent';
    if (!activeCodeTextNode || currentCodeSpeaker !== speaker) {
        commitActiveCode();
        commitActiveThought();
        commitActiveAssistant();

        currentCodeSpeaker = speaker;
        const details = document.createElement('details');
        details.className = 'code-box';

        const summary = document.createElement('summary');
        summary.className = 'code-summary';
        summary.textContent = `Generated Execution Code (${speaker})`;
        details.appendChild(summary);

        const contentPre = document.createElement('pre');
        contentPre.className = 'code-content';
        activeCodeTextNode = document.createTextNode('');
        contentPre.appendChild(activeCodeTextNode);
        details.appendChild(contentPre);

        currentCodeContentEl = contentPre;
        chatContainer.appendChild(details);
    }
    activeCodeTextNode.appendData(delta);
    scrollToBottomIfNearEnd(chatContainer);
}

/**
 * Appends a token directly without layout thrashing, separating bubbles per speaker.
 */
function appendToken(delta, source) {
    commitActiveCode();
    commitActiveThought();

    const speaker = source || 'Assistant';
    if (!activeAssistantTextNode || currentSpeaker !== speaker) {
        commitActiveAssistant();
        currentSpeaker = speaker;
        const msgEl = document.createElement('div');
        msgEl.className = 'message assistant-message';

        if (speaker) {
            const badge = document.createElement('div');
            badge.className = 'speaker-badge';
            badge.textContent = speaker;
            msgEl.appendChild(badge);
        }

        const textContainer = document.createElement('div');
        textContainer.className = 'message-text';
        activeAssistantTextNode = document.createTextNode('');
        textContainer.appendChild(activeAssistantTextNode);
        msgEl.appendChild(textContainer);

        activeAssistantContainer = textContainer;
        chatContainer.appendChild(msgEl);
    }
    activeAssistantTextNode.appendData(delta);
    scrollToBottomIfNearEnd(chatContainer);
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
 * Handles incoming SSE events.
 */
function handleStreamEvent(event) {
    const type = event.event_type;
    const payload = event.payload;

    if (type === 'stage') {
        addTimelineStage(payload.stage, payload.agent);
    } else if (type === 'subagent') {
        hadInterveningToolCall = true;
        commitActiveCode();
        commitActiveAssistant();
        const details = document.createElement('details');
        details.className = 'subagent-box subagent-event';

        const summary = document.createElement('summary');
        summary.className = 'subagent-summary';
        summary.textContent = `Subagent: ${payload.name}`;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'subagent-content';
        content.textContent = `Task: ${payload.task}`;
        details.appendChild(content);

        chatContainer.appendChild(details);
        currentChatHistory.push({ type: 'subagent', name: payload.name, task: payload.task });
        scrollToBottomIfNearEnd(chatContainer);
    } else if (type === 'tool_call') {
        hadInterveningToolCall = true;
        commitActiveCode();
        commitActiveAssistant();
        const details = document.createElement('details');
        details.className = 'tool-box tool-event';

        const summary = document.createElement('summary');
        summary.className = 'tool-summary';
        summary.textContent = `Tool: ${payload.tool}`;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'tool-content';
        const formattedInput = typeof payload.input === 'object' ? JSON.stringify(payload.input, null, 2) : payload.input;
        content.textContent = `Input:\n${formattedInput}\n\nOutput:\n${payload.output || 'pending'}`;
        details.appendChild(content);

        chatContainer.appendChild(details);
        currentChatHistory.push({ type: 'tool', tool: payload.tool, input: payload.input, output: payload.output });
        scrollToBottomIfNearEnd(chatContainer);
    } else if (type === 'thought') {
        appendThought(payload.delta, payload.source);
    } else if (type === 'code') {
        appendCode(payload.delta, payload.source);
    } else if (type === 'token') {
        appendToken(payload.delta, payload.source);
    } else if (type === 'metrics') {
        metricTtft.textContent = `${payload.ttft_ms.toFixed(1)} ms`;
        metricDuration.textContent = `${payload.total_duration_ms.toFixed(1)} ms`;
        metricTokens.textContent = payload.token_count.toString();
        metricToolCalls.textContent = payload.tool_calls.toString();
    } else if (type === 'chess_board') {
        if (chessBoard) {
            chessBoard.renderFromFEN(payload.fen, payload.legal_moves, payload.last_move);
        }
        if (chessTurnBadge) {
            chessTurnBadge.textContent = `Turn: ${payload.turn} (${payload.current_player})`;
        }
        if (chessStatusBadge) {
            chessStatusBadge.textContent = payload.is_check
                ? 'Status: Check!'
                : (payload.is_game_over
                    ? `Status: Game Over (${payload.result || ''})`
                    : 'Status: In Progress');
        }
        if (chessMoveInfo) {
            chessMoveInfo.textContent = payload.last_move
                ? `Last Move: ${payload.san || payload.last_move}${payload.thought ? ' - ' + payload.thought : ''}`
                : 'Match in Progress';
        }
        saveSessionState();
    } else if (type === 'done') {
        commitActiveCode();
        commitActiveThought();
        const hasStreamedAssistant = Boolean(
            activeAssistantTextNode &&
            activeAssistantTextNode.nodeValue &&
            activeAssistantTextNode.nodeValue.trim().length > 0
        );
        if (!hasStreamedAssistant && payload && payload.final_answer) {
            const lastItem = currentChatHistory[currentChatHistory.length - 1];
            if (!lastItem || lastItem.type !== 'assistant' || lastItem.content !== payload.final_answer) {
                appendToken(payload.final_answer, currentSpeaker || 'Assistant');
            }
        }
        commitActiveAssistant();
        saveSessionState();
    } else if (type === 'error') {
        showSystemNotice(`Error: ${payload.message}`, true);
    }
}

/**
 * Starts execution stream.
 */
async function runQuery() {
    const prompt = promptInput.value.trim();
    const patternId = patternSelect.value;

    if (!prompt) {
        showSystemNotice('Please enter a query prompt.', true);
        return;
    }
    if (!patternId) {
        showSystemNotice('Please select an architecture pattern.', true);
        return;
    }

    // Append user message to DOM
    const userEl = document.createElement('div');
    userEl.className = 'message user-message';
    userEl.textContent = prompt;
    chatContainer.appendChild(userEl);
    scrollToBottomIfNearEnd(chatContainer);
    currentChatHistory.push({ type: 'user', content: prompt });

    promptInput.value = '';
    isExecuting = true;
    resetStreamingState();

    // Reset right panel stage timeline
    currentStageTimeline = [];
    stageTimeline.innerHTML = '<div class="timeline-empty">Execution in progress...</div>';

    // UI state adjustments
    runBtn.disabled = true;
    abortBtn.disabled = false;
    statusBadge.className = 'status-badge streaming';
    statusBadge.textContent = 'Status: Streaming';

    const reqData = {
        pattern_id: patternId,
        session_id: currentSessionId,
        prompt: prompt,
        thinking: getEffectiveThinking()
    };

    await startStream(
        '/api/stream',
        reqData,
        handleStreamEvent,
        (err) => {
            console.error('Stream failure:', err);
            handleStreamEvent({
                event_type: 'error',
                payload: { message: err.message }
            });
            finishExecution();
        },
        () => {
            finishExecution();
        }
    );
}

/**
 * Completes stream execution and restores buttons.
 */
function finishExecution() {
    isExecuting = false;
    runBtn.disabled = false;
    abortBtn.disabled = true;
    statusBadge.className = 'status-badge connected';
    statusBadge.textContent = 'Status: Connected';
    commitActiveCode();
    commitActiveThought();
    commitActiveAssistant();
    saveSessionState();
}

/**
 * Submits a validated human move to the backend API and initiates the AI counter-turn.
 */
async function handleHumanChessMove(moveStr) {
    if (isExecuting) return;

    if (chessStatusBadge) {
        chessStatusBadge.textContent = 'Status: Validating Move...';
    }

    try {
        const resp = await fetch('/api/chess/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                move: moveStr,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: 'Failed to apply move.' }));
            if (chessMoveInfo) {
                chessMoveInfo.textContent = `Illegal Move: ${err.detail || 'Try another move.'}`;
            }
            if (chessStatusBadge) {
                chessStatusBadge.textContent = 'Status: Illegal Move';
            }
            return;
        }

        const data = await resp.json();
        if (chessBoard) {
            chessBoard.renderFromFEN(data.fen, data.legal_moves, data.last_move);
        }
        if (chessMoveInfo) {
            chessMoveInfo.textContent = `You played: ${data.san} (${data.last_move})`;
        }

        if (data.game_over) {
            if (chessStatusBadge) {
                chessStatusBadge.textContent = 'Status: Game Over';
            }
            return;
        }

        // Trigger AI counter-move via SSE
        await triggerAiCounterTurn();
    } catch (e) {
        console.error('Chess move error:', e);
        if (chessMoveInfo) {
            chessMoveInfo.textContent = `Move error: ${e.message}`;
        }
    }
}

/**
 * Triggers the AI counter-move stream for the active session.
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
        thinking: getEffectiveThinking(),
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
 * Clears current output and resets metrics.
 */
function clearOutput() {
    if (isExecuting) {
        abortStream();
    }
    chatContainer.innerHTML = '<div class="message system-message">Output cleared. Ready for new query.</div>';
    stageTimeline.innerHTML = '<div class="timeline-empty">No active execution</div>';
    currentChatHistory = [];
    currentStageTimeline = [];
    currentSessionId = 'sess_' + Math.random().toString(36).substring(2, 10);
    resetStreamingState();

    if (chessBoard) {
        chessBoard.setPlayerMode('spectator');
        chessBoard.renderFromFEN(DEFAULT_FEN);
    }

    metricTtft.textContent = '0.0 ms';
    metricDuration.textContent = '0.0 ms';
    metricTokens.textContent = '0';
    metricToolCalls.textContent = '0';

    try {
        sessionStorage.removeItem(STORAGE_KEY);
    } catch (e) {
        console.warn('Failed to clear sessionStorage', e);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    if (chessBoardView) {
        chessBoard = new ChessBoardComponent(chessBoardView, {
            onMove: (moveStr) => {
                handleHumanChessMove(moveStr);
            },
        });
    }

    restoreSessionState();
    loadPatterns();

    patternSelect.addEventListener('change', updatePatternDetails);
    if (thinkingSelect) {
        thinkingSelect.addEventListener('change', () => {
            saveSessionState();
        });
    }
    runBtn.addEventListener('click', runQuery);
    abortBtn.addEventListener('click', () => {
        abortStream();
        finishExecution();
    });
    clearBtn.addEventListener('click', clearOutput);

    if (chessSpectatorBtn) {
        chessSpectatorBtn.addEventListener('click', () => {
            patternSelect.value = 'ms_chess';
            updatePatternDetails();
            promptInput.value = 'spectator:4';
            runQuery();
        });
    }

    if (chessPlayWhiteBtn) {
        chessPlayWhiteBtn.addEventListener('click', async () => {
            patternSelect.value = 'ms_chess';
            updatePatternDetails();
            chessBoard.setPlayerMode('white');
            if (chessTurnBadge) chessTurnBadge.textContent = 'Turn: 1 (White - Your Turn)';
            if (chessStatusBadge) chessStatusBadge.textContent = 'Status: Play White';
            if (chessMoveInfo) chessMoveInfo.textContent = 'Your turn. Click a white piece (e.g. e2) to view legal destinations.';
            const stateResp = await fetch(`/api/chess/state?session_id=${currentSessionId}`).catch(() => null);
            if (stateResp && stateResp.ok) {
                const s = await stateResp.json();
                chessBoard.renderFromFEN(s.fen, s.legal_moves);
            } else {
                chessBoard.renderFromFEN(DEFAULT_FEN);
            }
        });
    }

    if (chessPlayBlackBtn) {
        chessPlayBlackBtn.addEventListener('click', async () => {
            patternSelect.value = 'ms_chess';
            updatePatternDetails();
            chessBoard.setPlayerMode('black');
            if (chessTurnBadge) chessTurnBadge.textContent = 'Turn: 1 (White - AI Thinking)';
            if (chessStatusBadge) chessStatusBadge.textContent = 'Status: Play Black';
            if (chessMoveInfo) chessMoveInfo.textContent = 'You play Black. AI White is computing the opening move...';
            await triggerAiCounterTurn();
        });
    }

    if (chessResetBtn) {
        chessResetBtn.addEventListener('click', async () => {
            if (chessBoard) {
                chessBoard.setPlayerMode('spectator');
                chessBoard.renderFromFEN(DEFAULT_FEN);
            }
            if (chessTurnBadge) chessTurnBadge.textContent = 'Turn: 1 (White)';
            if (chessStatusBadge) chessStatusBadge.textContent = 'Status: Ready';
            if (chessMoveInfo) chessMoveInfo.textContent = 'Board reset to starting position.';
            promptInput.value = 'spectator:4';
            saveSessionState();
        });
    }

    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!runBtn.disabled) {
                runQuery();
            }
        }
    });
});
