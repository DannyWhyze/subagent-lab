import os
from pathlib import Path
from langchain_core.tools import tool

# Auto-load .env from project root if present
_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k = _k.strip()
                _v = _v.strip().strip("'\"")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v

# Mock search database for offline/local determinism
MOCK_SEARCH_DATABASE = {
    "mcp": (
        "The Model Context Protocol (MCP) is an open standard introduced by Anthropic "
        "that standardizes how AI applications interface with data sources and tools. "
        "It acts like a USB-C port for AI apps, enabling models to query files, databases, "
        "and APIs securely without custom integrations."
    ),
    "default": (
        "Model Context Protocol (MCP) is an open protocol providing standardized access "
        "to contextual data, tools, and prompts for LLM agents."
    ),
}


@tool
def think_tool(reflection: str) -> str:
    """Reflect on progress, analyze current findings, and plan the next step.

    Args:
        reflection: Your internal analysis and reasoning on current findings.

    Returns:
        Confirmation that your reflection was registered.
    """
    return f"Reflection noted: {reflection}"


@tool(parse_docstring=True)
def web_search(query: str) -> str:
    """Search the web for technical information and documentation.

    Args:
        query: The search terms or query string.

    Returns:
        Search results relevant to the query.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            results = client.search(query, max_results=2)
            snippets = [r.get("content", "") for r in results.get("results", [])]
            if snippets:
                return "\n\n".join(snippets)
        except Exception as e:
            # Fallback to local mock on network or auth errors
            pass

    # Offline / local mock response
    query_lower = query.lower()
    for key, text in MOCK_SEARCH_DATABASE.items():
        if key in query_lower:
            return f"[Search Result for '{query}']:\n{text}"

    return f"[Search Result for '{query}']:\n{MOCK_SEARCH_DATABASE['default']}"
