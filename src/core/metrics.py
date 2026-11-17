"""Runtime execution metrics tracker for agent workflows."""

import time

from src.core.models import MetricsPayload


class MetricsTracker:
    """Tracks TTFT, total latency, token count, and tool invocations."""

    def __init__(self) -> None:
        self._start_time: float = time.perf_counter()
        self._first_token_time: float | None = None
        self._token_count: int = 0
        self._tool_calls: int = 0

    def start(self) -> None:
        """Reset or restart the tracking clock."""
        self._start_time = time.perf_counter()
        self._first_token_time = None
        self._token_count = 0
        self._tool_calls = 0

    def record_first_token(self) -> float:
        """Record the timestamp of the first generated token and return TTFT in ms."""
        if self._first_token_time is None:
            self._first_token_time = time.perf_counter()
        return self.get_ttft_ms()

    def record_token(self, count: int = 1) -> None:
        """Record one or more generated tokens."""
        if self._first_token_time is None:
            self.record_first_token()
        self._token_count += count

    def record_tool_call(self) -> None:
        """Record a tool invocation."""
        self._tool_calls += 1

    def get_ttft_ms(self) -> float:
        """Calculate Time to First Token (TTFT) in milliseconds."""
        if self._first_token_time is None:
            return 0.0
        return round((self._first_token_time - self._start_time) * 1000.0, 2)

    def get_total_duration_ms(self) -> float:
        """Calculate total elapsed execution time in milliseconds."""
        return round((time.perf_counter() - self._start_time) * 1000.0, 2)

    @property
    def token_count(self) -> int:
        return self._token_count

    @property
    def tool_calls(self) -> int:
        return self._tool_calls

    def finish(self) -> MetricsPayload:
        """Produce the final MetricsPayload snapshot."""
        return MetricsPayload(
            ttft_ms=self.get_ttft_ms(),
            total_duration_ms=self.get_total_duration_ms(),
            token_count=self._token_count,
            tool_calls=self._tool_calls,
        )
