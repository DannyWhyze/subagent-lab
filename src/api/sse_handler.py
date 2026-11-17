"""Server-Sent Events (SSE) streaming handler with client disconnect cancellation."""

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import Request

from src.core.base import BaseAgentRunner
from src.core.models import AgentStreamEvent, ErrorPayload, StreamRequest

logger = logging.getLogger(__name__)


async def sse_event_generator(
    runner: BaseAgentRunner,
    request: Request,
    req_data: StreamRequest,
) -> AsyncGenerator[str, None]:
    """Stream agent events as SSE with real-time disconnect cancellation (Rules 36 & 44)."""
    runner_queue: asyncio.Queue = asyncio.Queue()

    async def run_task() -> None:
        try:
            async for event in runner.run_stream(
                req_data.prompt,
                req_data.session_id,
                thinking=req_data.thinking,
            ):
                await runner_queue.put(event)
                await asyncio.sleep(0)
            await runner_queue.put(None)  # Sentinel indicating normal completion
        except asyncio.CancelledError:
            logger.info("Agent execution task cancelled due to client disconnect.")
            raise
        except Exception as exc:
            logger.exception("Error encountered during agent streaming.")
            await runner_queue.put(exc)

    task = asyncio.create_task(run_task())

    try:
        while True:
            # Check client disconnection
            if await request.is_disconnected():
                logger.info(f"Client disconnected for session {req_data.session_id}. Cancelling task.")
                task.cancel()
                break

            try:
                # Wait briefly for next event
                item = await asyncio.wait_for(runner_queue.get(), timeout=0.1)
            except TimeoutError:
                continue

            if item is None:
                # Normal completion sentinel
                break

            if isinstance(item, Exception):
                err_event = AgentStreamEvent(
                    event_type="error",
                    payload=ErrorPayload(message=str(item), code="STREAM_EXCEPTION").model_dump(),
                )
                yield f"data: {err_event.model_dump_json()}\n\n"
                break

            if isinstance(item, AgentStreamEvent):
                yield f"data: {item.model_dump_json()}\n\n"

    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
