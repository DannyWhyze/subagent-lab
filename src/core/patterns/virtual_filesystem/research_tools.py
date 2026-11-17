"""Research and reflection tools with deterministic offline fallbacks."""

import os

from langchain_core.tools import tool as lc_tool

# Deterministic mock database for offline searches
MOCK_SEARCH_DATABASE = {
    "mcp": (
        "The Model Context Protocol (MCP) is an open standard introduced by Anthropic "
        "that standardizes how AI applications interface with data sources and tools. "
        "It acts like a universal port for AI apps, enabling models to query files, databases, "
        "and APIs securely without custom integrations."
    ),
    "subagent": (
        "Subagent architectures divide complex reasoning workflows into specialized child agents. "
        "Context isolation ensures child agents do not suffer from context pollution or token leakage."
    ),
    "default": (
        "Model Context Protocol (MCP) and Subagent delegation enable scalable and reliable multi-agent systems."
    ),
}


@lc_tool
def think_tool(reflection: str) -> str:
    """Reflect on progress, analyze current findings, and plan the next step.

    Args:
        reflection: Your internal analysis and reasoning on current findings.

    Returns:
        Confirmation that your reflection was registered.
    """
    return f"Reflection noted: {reflection}"


@lc_tool(parse_docstring=True)
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
        except Exception:
            pass

    # Deterministic offline fallback
    query_lower = query.lower()
    for key, text in MOCK_SEARCH_DATABASE.items():
        if key in query_lower:
            return f"[Search Result for '{query}']:\n{text}"

    return f"[Search Result for '{query}']:\n{MOCK_SEARCH_DATABASE['default']}"
