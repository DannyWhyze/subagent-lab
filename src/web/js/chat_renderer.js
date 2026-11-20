/**
 * Chat DOM streaming renderer and Markdown presentation layer for Subagent Lab Explorer.
 * Handles incremental token assembly, thought/code/tool collapsible containers, and XSS sanitization.
 */

/**
 * Scrolls container to bottom only if the user is already near the bottom.
 * @param {HTMLElement} el - The scrollable DOM container.
 * @param {number} threshold - Pixel distance threshold from bottom.
 */
export function scrollToBottomIfNearEnd(el, threshold = 80) {
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceToBottom <= threshold) {
        el.scrollTop = el.scrollHeight;
    }
}

/**
 * Safely parses markdown to HTML while stripping dangerous tags and script attributes.
 * @param {HTMLElement} targetEl - Target DOM element to render sanitized HTML into.
 * @param {string} markdownText - Raw markdown text to parse.
 */
export function renderSafeMarkdown(targetEl, markdownText) {
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
 * @param {HTMLElement} chatContainer - Target chat container.
 * @param {string} message - Notice message text.
 * @param {boolean} isError - Whether notice is an error.
 */
export function showSystemNotice(chatContainer, message, isError = false) {
    if (!chatContainer) return;
    const noticeEl = document.createElement('div');
    noticeEl.className = `message system-message${isError ? ' error-message' : ''}`;
    noticeEl.textContent = message;
    chatContainer.appendChild(noticeEl);
    scrollToBottomIfNearEnd(chatContainer);
}

/**
 * Renders an existing historical message into the chat container.
 * @param {HTMLElement} chatContainer - Target chat container.
 * @param {Object} item - History item object.
 */
export function renderHistoryItem(chatContainer, item) {
    if (!chatContainer || !item) return;
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
 * Stateful controller for streaming dialogue, thoughts, execution code, and tool containers.
 */
export class ChatRenderer {
    /**
     * @param {HTMLElement} chatContainer - The scrollable chat DOM container.
     */
    constructor(chatContainer) {
        this.chatContainer = chatContainer;
        this.activeAssistantTextNode = null;
        this.activeAssistantContainer = null;
        this.currentSpeaker = null;
        this.activeThoughtTextNode = null;
        this.currentThoughtSpeaker = null;
        this.currentThoughtContentEl = null;
        this.hadInterveningToolCall = false;
        this.activeCodeTextNode = null;
        this.currentCodeSpeaker = null;
        this.currentCodeContentEl = null;
        this.chatHistory = [];
    }

    /**
     * Commits active generated code node to history and resets references.
     */
    commitActiveCode() {
        if (this.activeCodeTextNode && this.activeCodeTextNode.nodeValue) {
            this.chatHistory.push({
                type: 'code',
                speaker: this.currentCodeSpeaker,
                content: this.activeCodeTextNode.nodeValue
            });
            this.activeCodeTextNode = null;
            this.currentCodeSpeaker = null;
            this.currentCodeContentEl = null;
        }
    }

    /**
     * Commits in-progress thought content to history and cleans up references.
     */
    commitActiveThought() {
        if (this.currentThoughtContentEl && this.currentThoughtContentEl.textContent) {
            this.chatHistory.push({
                type: 'thought',
                speaker: this.currentThoughtSpeaker || 'Assistant',
                content: this.currentThoughtContentEl.textContent
            });
        }
        this.activeThoughtTextNode = null;
        this.currentThoughtSpeaker = null;
        this.currentThoughtContentEl = null;
        this.hadInterveningToolCall = false;
    }

    /**
     * Commits and parses markdown for the active assistant message response.
     */
    commitActiveAssistant() {
        if (this.activeAssistantTextNode && this.activeAssistantTextNode.nodeValue) {
            const rawContent = this.activeAssistantTextNode.nodeValue;
            this.chatHistory.push({
                type: 'assistant',
                speaker: this.currentSpeaker,
                content: rawContent
            });
            if (this.activeAssistantContainer) {
                renderSafeMarkdown(this.activeAssistantContainer, rawContent);
            }
            this.activeAssistantTextNode = null;
            this.activeAssistantContainer = null;
            this.currentSpeaker = null;
        }
    }

    /**
     * Resets all streaming state variables before a new turn or upon clearing.
     */
    resetStreamingState() {
        this.activeAssistantTextNode = null;
        this.activeAssistantContainer = null;
        this.currentSpeaker = null;
        this.activeThoughtTextNode = null;
        this.currentThoughtSpeaker = null;
        this.currentThoughtContentEl = null;
        this.hadInterveningToolCall = false;
        this.activeCodeTextNode = null;
        this.currentCodeSpeaker = null;
        this.currentCodeContentEl = null;
    }

    /**
     * Appends reasoning tokens into a collapsible thought-box container.
     * @param {string} delta - Chunk of thought text.
     * @param {string} source - Thought author/speaker.
     */
    appendThought(delta, source) {
        const speaker = source || 'Assistant';
        if (!this.currentThoughtContentEl || this.currentThoughtSpeaker !== speaker) {
            this.commitActiveThought();
            this.commitActiveCode();
            this.commitActiveAssistant();

            this.currentThoughtSpeaker = speaker;
            const details = document.createElement('details');
            details.className = 'thought-box';

            const summary = document.createElement('summary');
            summary.className = 'thought-summary';
            summary.textContent = `Thinking Process (${speaker})`;
            details.appendChild(summary);

            const contentDiv = document.createElement('div');
            contentDiv.className = 'thought-content';
            this.activeThoughtTextNode = document.createTextNode('');
            contentDiv.appendChild(this.activeThoughtTextNode);
            details.appendChild(contentDiv);

            this.currentThoughtContentEl = contentDiv;
            this.chatContainer.appendChild(details);
            this.hadInterveningToolCall = false;
        } else if (this.hadInterveningToolCall) {
            const divider = document.createTextNode('\n\n--- [Continuation after Tool Execution] ---\n');
            this.currentThoughtContentEl.appendChild(divider);
            this.activeThoughtTextNode = document.createTextNode('');
            this.currentThoughtContentEl.appendChild(this.activeThoughtTextNode);
            this.hadInterveningToolCall = false;
        }

        if (!this.activeThoughtTextNode) {
            this.activeThoughtTextNode = document.createTextNode('');
            this.currentThoughtContentEl.appendChild(this.activeThoughtTextNode);
        }

        this.activeThoughtTextNode.appendData(delta);
        scrollToBottomIfNearEnd(this.chatContainer);
    }

    /**
     * Appends generated execution code into a collapsible code-box container.
     * @param {string} delta - Chunk of generated code text.
     * @param {string} source - Code generator author/speaker.
     */
    appendCode(delta, source) {
        const speaker = source || 'ast_code_agent';
        if (!this.activeCodeTextNode || this.currentCodeSpeaker !== speaker) {
            this.commitActiveCode();
            this.commitActiveThought();
            this.commitActiveAssistant();

            this.currentCodeSpeaker = speaker;
            const details = document.createElement('details');
            details.className = 'code-box';

            const summary = document.createElement('summary');
            summary.className = 'code-summary';
            summary.textContent = `Generated Execution Code (${speaker})`;
            details.appendChild(summary);

            const contentPre = document.createElement('pre');
            contentPre.className = 'code-content';
            this.activeCodeTextNode = document.createTextNode('');
            contentPre.appendChild(this.activeCodeTextNode);
            details.appendChild(contentPre);

            this.currentCodeContentEl = contentPre;
            this.chatContainer.appendChild(details);
        }
        this.activeCodeTextNode.appendData(delta);
        scrollToBottomIfNearEnd(this.chatContainer);
    }

    /**
     * Appends a token directly without layout thrashing, separating bubbles per speaker.
     * @param {string} delta - Chunk of assistant response token.
     * @param {string} source - Message author/speaker.
     */
    appendToken(delta, source) {
        this.commitActiveCode();
        this.commitActiveThought();

        const speaker = source || 'Assistant';
        if (!this.activeAssistantTextNode || this.currentSpeaker !== speaker) {
            this.commitActiveAssistant();
            this.currentSpeaker = speaker;
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
            this.activeAssistantTextNode = document.createTextNode('');
            textContainer.appendChild(this.activeAssistantTextNode);
            msgEl.appendChild(textContainer);

            this.activeAssistantContainer = textContainer;
            this.chatContainer.appendChild(msgEl);
        }
        this.activeAssistantTextNode.appendData(delta);
        scrollToBottomIfNearEnd(this.chatContainer);
    }

    /**
     * Handles tool call SSE event.
     * @param {Object} payload - Tool call event payload.
     */
    handleToolCall(payload) {
        this.hadInterveningToolCall = true;
        this.commitActiveCode();
        this.commitActiveAssistant();

        const details = document.createElement('details');
        details.className = 'tool-box tool-event';

        const summary = document.createElement('summary');
        summary.className = 'tool-summary';
        summary.textContent = `Tool: ${payload.tool}`;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'tool-content';
        const formattedInput = typeof payload.input === 'object'
            ? JSON.stringify(payload.input, null, 2)
            : payload.input;
        content.textContent = `Input:\n${formattedInput}\n\nOutput:\n${payload.output || 'pending'}`;
        details.appendChild(content);

        this.chatContainer.appendChild(details);
        this.chatHistory.push({
            type: 'tool',
            tool: payload.tool,
            input: payload.input,
            output: payload.output
        });
        scrollToBottomIfNearEnd(this.chatContainer);
    }

    /**
     * Handles subagent delegation SSE event.
     * @param {Object} payload - Subagent delegation event payload.
     */
    handleSubagent(payload) {
        this.hadInterveningToolCall = true;
        this.commitActiveCode();
        this.commitActiveAssistant();

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

        this.chatContainer.appendChild(details);
        this.chatHistory.push({
            type: 'subagent',
            name: payload.name,
            task: payload.task
        });
        scrollToBottomIfNearEnd(this.chatContainer);
    }

    /**
     * Handles stream completion done event with duplicate token protection.
     * @param {Object} payload - Done event payload.
     */
    handleDone(payload) {
        this.commitActiveCode();
        this.commitActiveThought();

        const hasStreamedAssistant = Boolean(
            this.activeAssistantTextNode &&
            this.activeAssistantTextNode.nodeValue &&
            this.activeAssistantTextNode.nodeValue.trim().length > 0
        );
        if (!hasStreamedAssistant && payload && payload.final_answer) {
            const lastItem = this.chatHistory[this.chatHistory.length - 1];
            if (!lastItem || lastItem.type !== 'assistant' || lastItem.content !== payload.final_answer) {
                this.appendToken(payload.final_answer, this.currentSpeaker || 'Assistant');
            }
        }
        this.commitActiveAssistant();
    }

    /**
     * Appends a user prompt message to the dialogue.
     * @param {string} prompt - User query text.
     */
    addUserMessage(prompt) {
        const userEl = document.createElement('div');
        userEl.className = 'message user-message';
        userEl.textContent = prompt;
        this.chatContainer.appendChild(userEl);
        scrollToBottomIfNearEnd(this.chatContainer);
        this.chatHistory.push({ type: 'user', content: prompt });
    }

    /**
     * Clears all rendered messages and resets history.
     * @param {string} noticeText - System notice to show upon clear.
     */
    clear(noticeText = 'Output cleared. Ready for new query.') {
        this.chatContainer.innerHTML = '';
        this.chatHistory = [];
        this.resetStreamingState();
        showSystemNotice(this.chatContainer, noticeText, false);
    }

    /**
     * Rehydrates chat dialogue from an array of history items.
     * @param {Array<Object>} history - Array of serialized history items.
     */
    setHistory(history) {
        this.chatContainer.innerHTML = '';
        this.resetStreamingState();
        this.chatHistory = Array.isArray(history) ? history : [];
        for (const item of this.chatHistory) {
            renderHistoryItem(this.chatContainer, item);
        }
    }

    /**
     * Returns the current array of chat history items.
     * @returns {Array<Object>} Chat history items.
     */
    getHistory() {
        return this.chatHistory;
    }
}
