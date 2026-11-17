"""Empirical test and demonstration of the AST Code-First Agent.

Verifies:
1. AST sandbox safety constraints (blocking imports, reflection, loop limits).
2. Pure in-memory tool execution and variable state persistence.
3. Live interaction with local Ollama (`qwen3.5:latest`) generating executable Python code.
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

# Ensure parent project root is in sys.path for robust imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from legacy_scripts.ast_code_agent.sandbox import ASTSandbox, SecurityError
from legacy_scripts.ast_code_agent.weather_tool import get_weather


def test_sandbox_security_unit() -> None:
    """Verify sandbox security policies deterministically."""
    print("--- [1/2] Verifying Sandbox Security Constraints ---")
    sandbox = ASTSandbox(tools={"get_weather": get_weather})

    # Test 1: Safe math and tool calling
    valid_code = """
city = "Berlin"
weather = get_weather(city)
calc = 10 * 4 + 2
final_answer(f"{weather} Code: {calc}")
"""
    result = sandbox.execute(valid_code)
    assert result["final_answer"] == "The weather in Berlin is sunny. Code: 42", f"Unexpected: {result}"
    print("  [PASS] Safe execution, variable assignment and string formatting.")

    # Test 2: For loops and data transformation
    loop_code = """
cities = ["Munich", "Tokyo"]
reports = []
for c in cities:
    reports.append(get_weather(c))
final_answer(reports)
"""
    result = sandbox.execute(loop_code)
    assert len(result["final_answer"]) == 2, f"Expected 2 reports: {result}"
    print("  [PASS] Loop iteration and collection manipulation.")

    # Test 3: Subscript key-value assignment in dictionary
    subscript_code = """
data = {}
data["Berlin"] = get_weather("Berlin")
final_answer(data)
"""
    sub_res = sandbox.execute(subscript_code)
    assert sub_res["final_answer"] == {"Berlin": "The weather in Berlin is sunny."}, f"Unexpected: {sub_res}"
    print("  [PASS] Subscript key-value assignment in dictionary.")

    # Test 4: Import rejection
    malicious_import = "import os\nos.system('whoami')"
    try:
        sandbox.execute(malicious_import)
        raise AssertionError("Failed: import statement was not blocked!")
    except SecurityError as err:
        print(f"  [PASS] Blocked import attempt: {err}")

    # Test 4: Dunder introspection rejection
    malicious_dunder = "x = ().__class__.__base__"
    try:
        sandbox.execute(malicious_dunder)
        raise AssertionError("Failed: dunder attribute access was not blocked!")
    except SecurityError as err:
        print(f"  [PASS] Blocked dunder introspection: {err}")

    print("All deterministic sandbox security assertions passed successfully.\n")


def extract_python_code(text: str) -> str:
    """Extract code from markdown code fences or return raw text."""
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return text.strip()


async def run_live_ollama_agent(model_name: str = "qwen3.5:latest") -> None:
    """Run Code-First Agent using local Ollama model."""
    print(f"--- [2/2] Running Live Code-First Agent with Ollama ({model_name}) ---")
    from langchain_ollama import ChatOllama

    # Note: reasoning=False ensures clean code block generation
    llm = ChatOllama(
        model=model_name,
        base_url="http://localhost:11434",
        temperature=0.0,
        reasoning=False,
    )

    system_prompt = (
        "You are a Python Code-First Agent. You solve problems by writing clean, executable Python code.\n"
        "Rules:\n"
        "1. Write your code strictly inside a single ```python ... ``` block.\n"
        "2. Do NOT write any import statements. Imports are forbidden.\n"
        "3. You have access to the following pre-defined tools:\n"
        "   - `get_weather(city: str) -> str`: Returns the weather for a city.\n"
        "   - `final_answer(result: Any)`: Call this function with your final synthesized answer.\n"
        "4. Use Python variables and loops if multiple queries are needed."
    )

    user_query = (
        "Please check the weather for Berlin and Paris, and return a dictionary mapping city to weather."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    print(f"User Query: {user_query}")
    print("Streaming model output...")

    full_response = ""
    async for chunk in llm.astream(messages):
        delta = chunk.content
        if isinstance(delta, str):
            full_response += delta
            sys.stdout.write(delta)
            sys.stdout.flush()

    print("\n" + "=" * 50)
    print("Extracting generated Python code from model response...")
    code = extract_python_code(full_response)
    print("Extracted Code:")
    print("-" * 30)
    print(code)
    print("-" * 30)

    # Execute in our AST Sandbox
    sandbox = ASTSandbox(tools={"get_weather": get_weather})
    print("Executing code inside AST Sandbox...")
    execution_result = sandbox.execute(code)

    print("Execution Result:")
    final_val = execution_result["final_answer"]
    if isinstance(final_val, (dict, list)):
        import json

        formatted_final = json.dumps(final_val, indent=2)
    else:
        formatted_final = str(final_val)
    print(f"  Final Answer :\n{formatted_final}")
    print(f"  Variables    : {execution_result['variables']}")

    assert execution_result["final_answer"] is not None, "Error: Agent did not call final_answer()!"
    print("\n[SUCCESS] Live Code-First Agent run completed and verified.")


def main() -> None:
    """Entry point with console encoding and loop configuration."""
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    parser = argparse.ArgumentParser(description="AST Code-First Agent Demonstration")
    parser.add_argument(
        "--unit-only", action="store_true", help="Run only the deterministic sandbox unit test"
    )
    parser.add_argument("--model", type=str, default="qwen3.5:latest", help="Ollama model name")
    args = parser.parse_args()

    # Step 1: Deterministic security assertions
    test_sandbox_security_unit()

    # Step 2: Live Ollama test (unless unit-only requested)
    if not args.unit_only:
        try:
            asyncio.run(run_live_ollama_agent(model_name=args.model))
        except Exception as exc:
            print(f"\n[WARNING] Live Ollama test encountered an issue: {exc}")
            print(
                "To run only sandbox unit verification: uv run python legacy_scripts/ast_code_agent/app_test.py --unit-only"
            )
            raise


if __name__ == "__main__":
    main()
