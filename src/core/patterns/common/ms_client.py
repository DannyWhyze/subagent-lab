"""Ollama-compatible OpenAIChatClient for Microsoft Agent Framework.

Addresses a known upstream limitation when running Microsoft GroupChat orchestrations on Ollama:
In multi-agent group chats, agent turns are accumulated with role='assistant'.
When serialized to the OpenAI '/v1/responses' endpoint, Ollama's model chat template
treats an input ending with role='assistant' as already completed, resulting in zero output tokens
for subsequent speakers.

By converting previous speakers' turns into incoming dialogue turns (role='user' with author prefix),
local models (e.g. Qwen, Llama) seamlessly participate across all debate rounds.
"""

from collections.abc import Mapping
from typing import Any

from agent_framework import Message
from agent_framework.openai import OpenAIChatClient


class OllamaCompatibleOpenAIChatClient(OpenAIChatClient):
    """OpenAIChatClient customized for multi-agent local Ollama inference."""

    def _prepare_message_for_openai(
        self,
        message: Message,
        *,
        request_uses_service_side_storage: bool = True,
        reasoning_items: Mapping[str, dict[str, Any]] | None = None,
        serialized_reasoning_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Format previous assistant turns as incoming dialogue turns for Ollama compatibility."""
        if message.role == "assistant":
            author = getattr(message, "author_name", None)
            text = message.text or ""
            return [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"[{author}]: {text}" if author else text,
                        }
                    ],
                }
            ]
        return super()._prepare_message_for_openai(
            message,
            request_uses_service_side_storage=request_uses_service_side_storage,
            reasoning_items=reasoning_items,
            serialized_reasoning_ids=serialized_reasoning_ids,
        )
