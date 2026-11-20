/**
 * Pattern metadata and controls controller for Subagent Lab Explorer.
 * Manages pattern fetching, example prompt chips, and pattern-specific UI gating.
 */

/**
 * Controller for architecture patterns dropdown, telemetry cards, and thinking controls.
 */
export class PatternsController {
    /**
     * @param {Object} elements - UI DOM elements required by patterns controller.
     * @param {Object} callbacks - Interaction callbacks.
     */
    constructor(elements, callbacks = {}) {
        this.patternSelect = elements.patternSelect;
        this.thinkingSelect = elements.thinkingSelect;
        this.statusBadge = elements.statusBadge;
        this.metaFramework = elements.metaFramework;
        this.metaIsolation = elements.metaIsolation;
        this.metaDesc = elements.metaDesc;
        this.examplesWrapper = elements.examplesWrapper;
        this.examplesChips = elements.examplesChips;
        this.chessPanel = elements.chessPanel;

        this.onSelectPrompt = callbacks.onSelectPrompt || (() => {});
        this.onPatternChange = callbacks.onPatternChange || (() => {});
        this.onSaveState = callbacks.onSaveState || (() => {});
        this.fetchChessState = callbacks.fetchChessState || (async () => null);

        this.patternsData = [];
    }

    /**
     * Resolves the effective thinking effort parameter for backend requests.
     * Always returns a valid Literal ("off", "low", "medium", "high") even when UI dropdown is disabled.
     * @returns {string} Effective thinking mode.
     */
    getEffectiveThinking() {
        if (!this.thinkingSelect || this.thinkingSelect.value === 'disabled_na') {
            return 'off';
        }
        return this.thinkingSelect.value;
    }

    /**
     * Fetches pattern metadata from backend API.
     * @param {string|null} savedPatternId - Previously saved pattern ID to restore.
     */
    async loadPatterns(savedPatternId = null) {
        try {
            const res = await fetch('/api/patterns');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            this.patternsData = await res.json();

            if (this.patternSelect) {
                this.patternSelect.innerHTML = '';
                for (const p of this.patternsData) {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.name;
                    this.patternSelect.appendChild(opt);
                }

                if (savedPatternId && this.patternsData.some((p) => p.id === savedPatternId)) {
                    this.patternSelect.value = savedPatternId;
                }
            }

            this.updatePatternDetails();
            if (this.statusBadge) {
                this.statusBadge.className = 'status-badge connected';
                this.statusBadge.textContent = 'Status: Connected';
            }
        } catch (err) {
            if (this.statusBadge) {
                this.statusBadge.className = 'status-badge error';
                this.statusBadge.textContent = 'Status: Disconnected';
            }
            console.error('Failed to load patterns', err);
        }
    }

    /**
     * Renders clickable example prompt chips for the active pattern.
     * @param {Object} pattern - Pattern metadata object.
     */
    renderExamplePrompts(pattern) {
        if (!this.examplesChips) return;
        this.examplesChips.innerHTML = '';
        const prompts = pattern?.example_prompts || [];

        if (prompts.length === 0) {
            if (this.examplesWrapper) this.examplesWrapper.style.display = 'none';
            return;
        }

        if (this.examplesWrapper) this.examplesWrapper.style.display = 'flex';
        for (const promptText of prompts) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'example-chip';
            btn.textContent = promptText;
            btn.addEventListener('click', () => {
                this.onSelectPrompt(promptText);
            });
            this.examplesChips.appendChild(btn);
        }
    }

    /**
     * Updates pattern details card based on current dropdown selection.
     * @param {string} [currentSessionId] - Current active session ID.
     * @param {Object} [chessBoard] - ChessBoardComponent instance.
     * @param {HTMLElement} [chessTurnBadge] - Turn badge element for chess.
     */
    updatePatternDetails(currentSessionId = null, chessBoard = null, chessTurnBadge = null) {
        if (!this.patternSelect) return;
        const selectedId = this.patternSelect.value;
        const pattern = this.patternsData.find((p) => p.id === selectedId);
        if (!pattern) return;

        if (this.metaFramework) this.metaFramework.textContent = pattern.framework;
        if (this.metaIsolation) this.metaIsolation.textContent = pattern.isolation_type;
        if (this.metaDesc) this.metaDesc.textContent = pattern.description;

        this.renderExamplePrompts(pattern);

        if (this.thinkingSelect) {
            if (selectedId === 'ms_chess') {
                if (!this.thinkingSelect.dataset.prevValue && this.thinkingSelect.value !== 'disabled_na') {
                    this.thinkingSelect.dataset.prevValue = this.thinkingSelect.value;
                }
                let naOption = this.thinkingSelect.querySelector('option[value="disabled_na"]');
                if (!naOption) {
                    naOption = document.createElement('option');
                    naOption.value = 'disabled_na';
                    naOption.textContent = 'Disabled (N/A)';
                    this.thinkingSelect.appendChild(naOption);
                }
                this.thinkingSelect.value = 'disabled_na';
                this.thinkingSelect.disabled = true;
                this.thinkingSelect.title = 'Thinking mode not applicable for Chess (uses tactical prompt evaluation)';
            } else {
                const naOption = this.thinkingSelect.querySelector('option[value="disabled_na"]');
                if (naOption) {
                    naOption.remove();
                }
                if (this.thinkingSelect.dataset.prevValue) {
                    this.thinkingSelect.value = this.thinkingSelect.dataset.prevValue;
                    delete this.thinkingSelect.dataset.prevValue;
                }
                this.thinkingSelect.disabled = false;
                this.thinkingSelect.title = 'Select thinking effort for supported patterns';
            }
        }

        if (this.chessPanel) {
            const isChess = selectedId === 'ms_chess';
            this.chessPanel.classList.toggle('hidden', !isChess);
            if (isChess && chessBoard && currentSessionId) {
                this.fetchChessState(currentSessionId, chessBoard, chessTurnBadge);
            }
        }

        this.onSaveState();
    }

    /**
     * Returns currently selected pattern ID.
     * @returns {string} Selected pattern ID.
     */
    getSelectedPatternId() {
        return this.patternSelect ? this.patternSelect.value : '';
    }

    /**
     * Sets selected pattern ID.
     * @param {string} id - Pattern ID to select.
     */
    setSelectedPatternId(id) {
        if (this.patternSelect) {
            this.patternSelect.value = id;
            this.updatePatternDetails();
        }
    }
}
