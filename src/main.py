"""FastAPI application entrypoint for Subagent Lab Explorer."""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env (e.g. LangSmith tracing, API keys)
load_dotenv()

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Cross-Platform Event Loop configuration (Rule 28 & AGENTS.md)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from src.api.routes import router as api_router

WEB_DIR = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fast startup (<20ms per Rule 36)
    yield


app = FastAPI(
    title="Subagent Lab API",
    description="Unified API & SSE streaming server for benchmarking subagent architectures.",
    version="0.1.0",
    lifespan=lifespan,
)

# Strict CORS configuration without wildcards (Rule 9)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Mount static web directory if it exists
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Subagent Lab API running. Web frontend assets not yet initialized."}


@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    return Response(status_code=204)


def start():
    """CLI runner helper for local dev server."""
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    start()
