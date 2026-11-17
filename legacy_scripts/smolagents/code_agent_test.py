"""Empirical demonstration of Hugging Face smolagents with local Ollama.

Demonstrates:
1. Single CodeAgent executing Python code in smolagents' LocalPythonExecutor.
2. Hierarchical ManagedAgent pattern: Supervisor delegates to a specialized
   weather subagent via Python function calling.
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from smolagents import CodeAgent, OpenAIServerModel

from legacy_scripts.smolagents.weather_tool import get_weather


def create_local_model(model_id: str = "qwen3.5:latest") -> OpenAIServerModel:
    """Instantiate OpenAIServerModel pointed at local Ollama endpoint."""
    return OpenAIServerModel(
        model_id=model_id,
        api_base="http://localhost:11434/v1",
        api_key="ollama",
        extra_body={"reasoning_effort": "none"},
    )


def test_single_code_agent(model: OpenAIServerModel) -> None:
    """Test standard CodeAgent with weather tool."""
    print("\n" + "=" * 60)
    print("--- [1/2] Testing Single CodeAgent with smolagents ---")
    print("=" * 60)

    agent = CodeAgent(
        tools=[get_weather],
        model=model,
        verbosity_level=1,
    )

    query = "Check the weather for Berlin and Paris, and return a dictionary mapping city to weather."
    print(f"Task: {query}\n")

    result = agent.run(query)

    print("\nResult from Single CodeAgent:")
    print(f"  Type   : {type(result).__name__}")
    print(f"  Content: {result}")
    assert result is not None, "Error: Single CodeAgent returned None!"
    print("  [PASS] Single CodeAgent execution successful.")


def test_hierarchical_managed_agent(model: OpenAIServerModel) -> None:
    """Test hierarchical supervisor delegating to a managed subagent."""
    print("\n" + "=" * 60)
    print("--- [2/2] Testing Hierarchical ManagedAgent (Subagent) ---")
    print("=" * 60)

    # 1. Specialized Subagent with domain tool
    weather_specialist = CodeAgent(
        tools=[get_weather],
        model=model,
        name="weather_specialist",
        description="A specialized meteorological agent that looks up weather reports for given cities.",
        verbosity_level=1,
    )

    # 2. Supervisor with no domain tools, only the managed subagent
    supervisor = CodeAgent(
        tools=[],
        model=model,
        managed_agents=[weather_specialist],
        verbosity_level=1,
    )

    query = (
        "Ask the weather specialist to check the weather in Tokyo and Sydney, then provide a concise summary."
    )
    print(f"Supervisor Task: {query}\n")

    result = supervisor.run(query)

    print("\nResult from Supervisor:")
    print(f"  Type   : {type(result).__name__}")
    print(f"  Content: {result}")
    assert result is not None, "Error: Supervisor returned None!"
    print("  [PASS] Hierarchical ManagedAgent delegation successful.")


def main() -> None:
    """Main CLI entry point with console UTF-8 encoding."""
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="smolagents Local Ollama Test Suite")
    parser.add_argument(
        "--mode",
        choices=["single", "subagent", "all"],
        default="all",
        help="Run single CodeAgent, hierarchical subagent, or all",
    )
    parser.add_argument("--model", type=str, default="qwen3.5:latest", help="Ollama model name")
    args = parser.parse_args()

    model = create_local_model(model_id=args.model)

    if args.mode in ("single", "all"):
        test_single_code_agent(model)

    if args.mode in ("subagent", "all"):
        test_hierarchical_managed_agent(model)

    print("\n" + "=" * 60)
    print("[SUCCESS] All smolagents verification steps completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
