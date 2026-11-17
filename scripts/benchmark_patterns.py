"""Benchmark script for comparing Subagent Lab architectures.

Runs standardized benchmark queries against all registered agent runners,
measures TTFT (Time to First Token), latency, token throughput, and generates
a Markdown comparison table for documentation and portfolio showcases.

Usage:
    uv run python scripts/benchmark_patterns.py [--offline]
"""

import argparse
import asyncio
import os
import pathlib
import sys
import time
from typing import Any

import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.models import MetricsPayload
from src.core.registry import registry

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def warmup_model(model_name: str, base_url: str = "http://localhost:11434") -> None:
    """Preload model weights into GPU VRAM to eliminate cold-start latency bias."""
    print(f"Pre-warming model '{model_name}' in GPU VRAM (eliminating cold-start bias)...")
    endpoint = base_url.rstrip("/") + "/api/generate"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(endpoint, json={"model": model_name, "keep_alive": "15m"})
            if resp.status_code == 200:
                print(f"  -> Model '{model_name}' preloaded successfully into VRAM.\n")
            else:
                print(f"  -> Warmup notice: status {resp.status_code}\n")
    except Exception as exc:
        print(f"  -> Warmup notice: {exc}\n")


async def benchmark_pattern(
    pattern_id: str,
    prompt: str,
    thinking: str = "off",
) -> dict[str, Any]:
    """Execute a single pattern run and collect performance metrics."""
    runner = registry.get_runner(pattern_id)
    if runner is None:
        raise ValueError(f"Runner '{pattern_id}' not found in registry.")

    session_id = f"bench_{pattern_id}_{int(time.time())}"
    tokens = 0
    thoughts = 0
    tool_calls = 0
    metrics: MetricsPayload | None = None
    final_answer = ""

    start_time = time.perf_counter()
    async for event in runner.run_stream(prompt, session_id, thinking=thinking):
        if event.event_type == "token":
            tokens += 1
        elif event.event_type == "thought":
            thoughts += 1
        elif event.event_type == "tool_call":
            tool_calls += 1
        elif event.event_type == "metrics":
            metrics = MetricsPayload.model_validate(event.payload)
        elif event.event_type == "done":
            final_answer = event.payload.get("final_answer", "")
        elif event.event_type == "error":
            final_answer = f"Error: {event.payload.get('message', '')}"

    wall_duration_ms = (time.perf_counter() - start_time) * 1000.0

    return {
        "pattern_id": pattern_id,
        "ttft_ms": metrics.ttft_ms if metrics else 0.0,
        "duration_ms": metrics.total_duration_ms if metrics else wall_duration_ms,
        "token_count": metrics.token_count if metrics else tokens,
        "thought_tokens": thoughts,
        "tool_calls": metrics.tool_calls if metrics else tool_calls,
        "final_snippet": (final_answer[:60] + "...") if len(final_answer) > 60 else final_answer,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Subagent Lab architectures.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run only offline mock benchmarks instead of invoking live local LLMs.",
    )
    parser.add_argument(
        "--thinking",
        choices=["off", "low", "medium", "high"],
        default="off",
        help="Reasoning/thinking mode effort (default: off).",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("SUBAGENT LAB ARCHITECTURAL BENCHMARK")
    print(f"Mode: {'Offline Mock' if args.offline else 'Live Local Ollama'} | Thinking: {args.thinking}")
    print("=" * 80)

    patterns = registry.get_metadata()
    if args.offline:
        patterns = [p for p in patterns if p.id == "mock_runner"]
    else:
        # Exclude mock_runner from live LLM benchmarks unless explicitly requested
        patterns = [p for p in patterns if p.id != "mock_runner"]
        model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        await warmup_model(model_name, base_url)

    results: list[dict[str, Any]] = []

    for meta in patterns:
        prompt = meta.example_prompts[0] if meta.example_prompts else "Analyze the task."
        print(f"\n[Benchmarking] {meta.name} ({meta.framework})...")
        print(f"Prompt: '{prompt}'")
        try:
            res = await benchmark_pattern(meta.id, prompt, thinking=args.thinking)
            res["name"] = meta.name
            res["framework"] = meta.framework
            res["isolation"] = meta.isolation_type
            results.append(res)
            print(
                f"  -> TTFT: {res['ttft_ms']:.1f} ms | Duration: {res['duration_ms']:.1f} ms | Tokens: {res['token_count']}"
            )
        except Exception as exc:
            print(f"  -> FAILED: {exc}")

    # Generate Markdown Table
    print("\n" + "=" * 80)
    print("MARKDOWN BENCHMARK TABLE")
    print("=" * 80 + "\n")

    headers = [
        "Architecture Pattern",
        "Framework",
        "Isolation Boundary",
        "TTFT (ms)",
        "Duration (s)",
        "Tokens",
        "Tool Calls",
    ]
    col_format = "| {:<32} | {:<22} | {:<34} | {:>9} | {:>12} | {:>6} | {:>10} |"

    print(col_format.format(*headers))
    print("| " + " | ".join(["-" * 32, "-" * 22, "-" * 34, "-" * 9, "-" * 12, "-" * 6, "-" * 10]) + " |")

    for r in results:
        dur_s = f"{r['duration_ms'] / 1000.0:.2f}s"
        ttft_str = f"{r['ttft_ms']:.1f}"
        print(
            col_format.format(
                r["name"][:32],
                r["framework"][:22],
                r["isolation"][:34],
                ttft_str,
                dur_s,
                r["token_count"],
                r["tool_calls"],
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
