"""Frontend UI assets and Rule 22 emoji compliance tests."""

import re

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import WEB_DIR, app


def test_ui_files_exist():
    assert (WEB_DIR / "index.html").exists()
    assert (WEB_DIR / "css" / "style.css").exists()
    assert (WEB_DIR / "js" / "app.js").exists()
    assert (WEB_DIR / "js" / "stream.js").exists()
    assert (WEB_DIR / "js" / "chess_board.js").exists()
    assert (WEB_DIR / "js" / "marked.min.js").exists()


@pytest.mark.asyncio
async def test_ui_routes_serve_static():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Index route
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Subagent Lab Explorer" in resp.text
        assert "text/html" in resp.headers.get("content-type", "")

        # Static CSS
        resp_css = await client.get("/static/css/style.css")
        assert resp_css.status_code == 200
        assert "text/css" in resp_css.headers.get("content-type", "")

        # Static JS
        resp_js = await client.get("/static/js/app.js")
        assert resp_js.status_code == 200
        assert "javascript" in resp_js.headers.get("content-type", "").lower()


def test_rule_22_no_decorative_emojis():
    """Verify Rule 22: Strictly NO decorative emojis in UI assets."""
    # Regex range for common emojis
    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]")

    files_to_check = [
        WEB_DIR / "index.html",
        WEB_DIR / "css" / "style.css",
        WEB_DIR / "js" / "app.js",
        WEB_DIR / "js" / "stream.js",
    ]

    for file_path in files_to_check:
        content = file_path.read_text(encoding="utf-8")
        matches = emoji_pattern.findall(content)
        assert len(matches) == 0, f"Found decorative emojis in {file_path.name}: {matches}"


def test_rule_47_session_storage_and_abort():
    """Verify Rule 47: sessionStorage schema and AbortController implementation."""
    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    stream_js = (WEB_DIR / "js" / "stream.js").read_text(encoding="utf-8")

    # sessionStorage persistence
    assert "sessionStorage.setItem" in app_js
    assert "sessionStorage.getItem" in app_js
    assert "last_pattern_id" in app_js
    assert "chat_history" in app_js

    # AbortController handling
    assert "AbortController" in stream_js
    assert "abortStream" in stream_js
    assert "currentAbortController.abort()" in stream_js

    # Dynamic example prompts handling
    assert "renderExamplePrompts" in app_js
    assert "example-chip" in app_js

    # Persona speaker distinction (Rule 22 compliant)
    assert "speaker-badge" in app_js
    style_css = (WEB_DIR / "css" / "style.css").read_text(encoding="utf-8")
    assert ".speaker-badge" in style_css


def test_ui_contains_chess_elements():
    """Verify chessboard UI container and controls exist in index.html."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="chess-panel"' in html or 'id="chess-board-view"' in html
    assert "Play as White" in html or "Spectator" in html
    assert "chess_board.js" in html


def test_thinking_mode_ui_elements():
    """Verify thinking select control, collapsible thought styles, and session persistence."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="thinkingSelect"' in html
    assert 'value="off"' in html
    assert 'value="low"' in html
    assert 'value="medium"' in html
    assert 'value="high"' in html

    css = (WEB_DIR / "css" / "style.css").read_text(encoding="utf-8")
    assert ".thought-box" in css
    assert ".thought-summary" in css
    assert ".thought-content" in css
    assert "select:disabled" in css

    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert "thinkingSelect" in app_js
    assert "thinkingSelect.disabled" in app_js
    assert "disabled_na" in app_js
    assert "Disabled (N/A)" in app_js
    assert "appendThought" in app_js
    assert "thought" in app_js
    assert "getEffectiveThinking" in app_js


def test_code_box_ui_elements():
    """Verify collapsible execution code styles and app.js handlers exist without emojis."""
    css = (WEB_DIR / "css" / "style.css").read_text(encoding="utf-8")
    assert ".code-box" in css
    assert ".code-summary" in css
    assert ".code-content" in css

    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert "appendCode" in app_js
    assert "code-box" in app_js
    assert "Generated Execution Code" in app_js


def test_persistent_thought_and_compact_tool_containers():
    """Verify unified thought box continuation, collapsible details, and flex-shrink protection."""
    css = (WEB_DIR / "css" / "style.css").read_text(encoding="utf-8")
    assert ".tool-event" in css
    assert ".tool-summary" in css
    assert ".tool-content" in css
    assert ".subagent-summary" in css
    assert ".subagent-content" in css
    assert "flex-shrink: 0" in css

    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert "commitActiveThought" in app_js
    assert "hadInterveningToolCall" in app_js
    assert "tool-summary" in app_js
    assert "subagent-summary" in app_js
    assert "details.open = true" not in app_js


def test_done_event_streaming_duplicate_protection():
    """Verify that app.js does not duplicate streamed tokens upon receiving final_answer in done event."""
    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert "hasStreamedAssistant" in app_js
    assert "!hasStreamedAssistant && payload && payload.final_answer" in app_js


def test_js_modules_valid_syntax():
    """Verify ES module syntax validity for all frontend JS files via node --check."""
    import shutil
    import subprocess

    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js binary not available on PATH")

    js_files = [
        WEB_DIR / "js" / "chess_board.js",
        WEB_DIR / "js" / "stream.js",
        WEB_DIR / "js" / "app.js",
    ]

    for js_path in js_files:
        code = js_path.read_text(encoding="utf-8")
        res = subprocess.run(
            [node_bin, "--input-type=module", "--check"],
            input=code,
            text=True,
            capture_output=True,
            check=False,
        )
        assert res.returncode == 0, f"Syntax error in {js_path.name}:\n{res.stderr}"


def test_ui_security_and_accessibility():
    """Verify XSS sanitization, accessibility ARIA attributes, responsive layout, and zero alert calls."""
    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    chess_board_js = (WEB_DIR / "js" / "chess_board.js").read_text(encoding="utf-8")
    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    style_css = (WEB_DIR / "css" / "style.css").read_text(encoding="utf-8")

    # Security: safe markdown rendering and zero raw alert() calls
    assert "renderSafeMarkdown" in app_js
    assert "alert(" not in app_js
    assert "showSystemNotice" in app_js

    # Accessibility (a11y)
    assert 'aria-live="polite"' in index_html
    assert 'setAttribute("role", "button")' in chess_board_js
    assert "aria-label" in chess_board_js
    assert "tabIndex = 0" in chess_board_js

    # CSS classes and responsive layout
    assert ".hidden" in style_css
    assert ".error-message" in style_css
    assert "@media (max-width: 960px)" in style_css
    assert 'class="chess-card hidden"' in index_html
