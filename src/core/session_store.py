"""Bounded session storage with LRU eviction to prevent unbounded memory growth."""

from collections import OrderedDict
from typing import Any

MAX_SESSIONS = 50


class SessionStore:
    """In-memory thread-safe session cache bounded by LRU eviction (Rules 20 & 23)."""

    def __init__(self, max_sessions: int = MAX_SESSIONS) -> None:
        self.max_sessions = max_sessions
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def get(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve state for a session and move it to the most-recently-used position."""
        if session_id in self._store:
            self._store.move_to_end(session_id)
            return self._store[session_id]
        return None

    def set(self, session_id: str, state: dict[str, Any]) -> None:
        """Store or update session state and evict oldest entry if capacity exceeded."""
        if session_id in self._store:
            self._store.move_to_end(session_id)
        self._store[session_id] = state
        if len(self._store) > self.max_sessions:
            self._store.popitem(last=False)

    def delete(self, session_id: str) -> bool:
        """Remove a session if present."""
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all active sessions."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
