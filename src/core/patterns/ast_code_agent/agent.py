"""Agent prompt and Python code extraction helpers for AST Code-First Agent."""

import re

SYSTEM_PROMPT = (
    "You are a Python Code-First Agent. You solve problems by writing clean, executable Python code.\n"
    "Rules:\n"
    "1. Write your code strictly inside a single ```python ... ``` block.\n"
    "2. Do NOT write any import statements. Imports are forbidden.\n"
    "3. You have access to the following pre-defined tools:\n"
    "   - `get_weather(city: str) -> str`: Returns the weather for a city.\n"
    "   - `final_answer(result: Any)`: Call this function with your final synthesized answer.\n"
    "4. Use Python variables and loops if multiple queries or aggregations are needed."
)


def extract_python_code(text: str) -> str:
    """Extract code from markdown code fences or return raw text."""
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return text.strip()
