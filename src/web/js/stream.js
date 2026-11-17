/**
 * SSE Streaming client with explicit AbortController lifecycle control.
 */

let currentAbortController = null;

/**
 * Initiates an SSE stream request to the backend.
 *
 * @param {string} url - API endpoint URL
 * @param {object} requestData - StreamRequest payload
 * @param {function} onEvent - Callback for each AgentStreamEvent
 * @param {function} onError - Callback on network or execution failure
 * @param {function} onComplete - Callback when stream finishes cleanly
 */
export async function startStream(url, requestData, onEvent, onError, onComplete) {
    if (currentAbortController) {
        currentAbortController.abort();
    }
    currentAbortController = new AbortController();

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            },
            body: JSON.stringify(requestData),
            signal: currentAbortController.signal
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            let errMsg;
            if (typeof errData.detail === 'string') {
                errMsg = errData.detail;
            } else if (Array.isArray(errData.detail)) {
                errMsg = errData.detail.map((e) => e.msg || JSON.stringify(e)).join('; ');
            } else if (errData.detail) {
                errMsg = JSON.stringify(errData.detail);
            } else {
                errMsg = `Server responded with HTTP ${response.status}`;
            }
            throw new Error(errMsg);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Retain remainder in buffer

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('data: ')) {
                    try {
                        const parsed = JSON.parse(trimmed.slice(6));
                        onEvent(parsed);
                    } catch (err) {
                        console.error('Failed to parse SSE line:', trimmed, err);
                    }
                }
            }
        }

        onComplete();
    } catch (err) {
        if (err.name === 'AbortError') {
            onEvent({
                event_type: 'stage',
                payload: { stage: 'stream_aborted', agent: 'client' },
                timestamp: Date.now() / 1000
            });
            onComplete();
        } else {
            onError(err);
        }
    } finally {
        currentAbortController = null;
    }
}

/**
 * Cancels any active SSE stream task immediately.
 */
export function abortStream() {
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }
}
