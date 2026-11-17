"""Deterministic unit tests for the AST execution sandbox."""

import pytest

from src.core.patterns.ast_code_agent import ASTSandbox, SecurityError


def test_sandbox_safe_math_and_builtins() -> None:
    sandbox = ASTSandbox()
    code = """
x = 10 * 4 + 2
items = [1, 2, 3, 4]
total = sum(items)
final_answer(f"Calculated: {x}, Total: {total}")
"""
    result = sandbox.execute(code)
    assert result["final_answer"] == "Calculated: 42, Total: 10"
    assert result["variables"]["x"] == 42
    assert result["variables"]["total"] == 10


def test_sandbox_registered_tool_invocation() -> None:
    def fake_weather(city: str) -> str:
        return f"The weather in {city} is sunny, 22°C"

    sandbox = ASTSandbox(tools={"get_weather": fake_weather})
    code = """
city = "Berlin"
report = get_weather(city)
final_answer({"city": city, "report": report})
"""
    result = sandbox.execute(code)
    assert result["final_answer"] == {"city": "Berlin", "report": "The weather in Berlin is sunny, 22°C"}


def test_sandbox_loop_and_collections() -> None:
    def fake_weather(city: str) -> str:
        return f"{city}: Sunny"

    sandbox = ASTSandbox(tools={"get_weather": fake_weather})
    code = """
cities = ["Munich", "Tokyo", "Paris"]
reports = {}
for c in cities:
    reports[c] = get_weather(c)
final_answer(reports)
"""
    result = sandbox.execute(code)
    assert result["final_answer"] == {
        "Munich": "Munich: Sunny",
        "Tokyo": "Tokyo: Sunny",
        "Paris": "Paris: Sunny",
    }


def test_sandbox_blocks_imports() -> None:
    sandbox = ASTSandbox()
    with pytest.raises(SecurityError, match="imports .* are strictly forbidden"):
        sandbox.execute("import os\nos.system('whoami')")

    with pytest.raises(SecurityError, match="imports .* are strictly forbidden"):
        sandbox.execute("from sys import exit\nexit(0)")


def test_sandbox_blocks_dunder_introspection() -> None:
    sandbox = ASTSandbox()
    with pytest.raises(SecurityError, match="access to private/dunder attribute"):
        sandbox.execute("x = ().__class__.__base__")

    with pytest.raises(SecurityError, match="access to private/dunder attribute"):
        sandbox.execute("__secret__ = 42")


def test_sandbox_loop_iteration_limit() -> None:
    sandbox = ASTSandbox(max_loop_iterations=50)
    code = """
count = 0
for i in range(1000):
    count += 1
final_answer(count)
"""
    with pytest.raises(SecurityError, match="Loop iteration limit .* exceeded"):
        sandbox.execute(code)


def test_sandbox_syntax_error() -> None:
    sandbox = ASTSandbox()
    with pytest.raises(ValueError, match="Syntax error in agent code"):
        sandbox.execute("def unclosed_syntax(")
