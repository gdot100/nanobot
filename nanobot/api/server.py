"""OpenAI-compatible HTTP API server for a fixed nanobot session.

Provides /v1/chat/completions, /v1/models, and /webhook/apple-health endpoints.
All requests route to a single persistent API session.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from aiohttp import web
from loguru import logger

from nanobot.utils.runtime import EMPTY_FINAL_RESPONSE_MESSAGE

API_SESSION_KEY = "api:default"
API_CHAT_ID = "default"


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _error_json(status: int, message: str, err_type: str = "invalid_request_error") -> web.Response:
    return web.json_response(
        {"error": {"message": message, "type": err_type, "code": status}},
        status=status,
    )


def _chat_completion_response(content: str, model: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _response_text(value: Any) -> str:
    """Normalize process_direct output to plain assistant text."""
    if value is None:
        return ""
    if hasattr(value, "content"):
        return str(getattr(value, "content") or "")
    return str(value)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_chat_completions(request: web.Request) -> web.Response:
    """POST /v1/chat/completions"""

    # --- Parse body ---
    try:
        body = await request.json()
    except Exception:
        return _error_json(400, "Invalid JSON body")

    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 1:
        return _error_json(400, "Only a single user message is supported")

    # Stream not yet supported
    if body.get("stream", False):
        return _error_json(400, "stream=true is not supported yet. Set stream=false or omit it.")

    message = messages[0]
    if not isinstance(message, dict) or message.get("role") != "user":
        return _error_json(400, "Only a single user message is supported")
    user_content = message.get("content", "")
    if isinstance(user_content, list):
        # Multi-modal content array — extract text parts
        user_content = " ".join(
            part.get("text", "") for part in user_content if part.get("type") == "text"
        )

    agent_loop = request.app["agent_loop"]
    timeout_s: float = request.app.get("request_timeout", 120.0)
    model_name: str = request.app.get("model_name", "nanobot")
    if (requested_model := body.get("model")) and requested_model != model_name:
        return _error_json(400, f"Only configured model '{model_name}' is available")

    session_key = f"api:{body['session_id']}" if body.get("session_id") else API_SESSION_KEY
    session_locks: dict[str, asyncio.Lock] = request.app["session_locks"]
    session_lock = session_locks.setdefault(session_key, asyncio.Lock())

    logger.info("API request session_key={} content={}", session_key, user_content[:80])

    _FALLBACK = EMPTY_FINAL_RESPONSE_MESSAGE

    try:
        async with session_lock:
            try:
                response = await asyncio.wait_for(
                    agent_loop.process_direct(
                        content=user_content,
                        session_key=session_key,
                        channel="api",
                        chat_id=API_CHAT_ID,
                    ),
                    timeout=timeout_s,
                )
                response_text = _response_text(response)

                if not response_text or not response_text.strip():
                    logger.warning(
                        "Empty response for session {}, retrying",
                        session_key,
                    )
                    retry_response = await asyncio.wait_for(
                        agent_loop.process_direct(
                            content=user_content,
                            session_key=session_key,
                            channel="api",
                            chat_id=API_CHAT_ID,
                        ),
                        timeout=timeout_s,
                    )
                    response_text = _response_text(retry_response)
                    if not response_text or not response_text.strip():
                        logger.warning(
                            "Empty response after retry for session {}, using fallback",
                            session_key,
                        )
                        response_text = _FALLBACK

            except asyncio.TimeoutError:
                return _error_json(504, f"Request timed out after {timeout_s}s")
            except Exception:
                logger.exception("Error processing request for session {}", session_key)
                return _error_json(500, "Internal server error", err_type="server_error")
    except Exception:
        logger.exception("Unexpected API lock error for session {}", session_key)
        return _error_json(500, "Internal server error", err_type="server_error")

    return web.json_response(_chat_completion_response(response_text, model_name))


async def handle_models(request: web.Request) -> web.Response:
    """GET /v1/models"""
    model_name = request.app.get("model_name", "nanobot")
    return web.json_response({
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "created": 0,
                "owned_by": "nanobot",
            }
        ],
    })


async def handle_health(request: web.Request) -> web.Response:
    """GET /health"""
    return web.json_response({"status": "ok"})


async def handle_apple_health_webhook(request: web.Request) -> web.Response:
    """POST /webhook/apple-health — receives Apple Health data from iOS Shortcut."""
    try:
        body = await request.json()
    except Exception:
        return _error_json(400, "Invalid JSON body")

    data_type = body.get("type", "health_data")
    entries = body.get("entries", [])
    date = body.get("date", "")

    if not entries:
        return web.json_response({"status": "ok", "message": "No entries received"})

    agent_loop = request.app["agent_loop"]
    timeout_s: float = request.app.get("request_timeout", 120.0)
    session_key = "webhook:apple-health"
    session_locks: dict[str, asyncio.Lock] = request.app["session_locks"]
    session_lock = session_locks.setdefault(session_key, asyncio.Lock())

    health_entries = "\n".join(
        f"  {e.get('type', '?')}: {e.get('value', '?')} {e.get('unit', '')}"
        for e in entries
    )
    message = (
        f"Apple Health data for {date}:\n{health_entries}\n\n"
        f"Please process this health data: log any weight entries to the health tracker, "
        f"log any exercise/workout data to the exercise tracker, and give me a summary."
    )

    logger.info("Apple Health webhook received: {} entries for {}", len(entries), date)

    try:
        async with session_lock:
            response = await asyncio.wait_for(
                agent_loop.process_direct(
                    content=message,
                    session_key=session_key,
                    channel="api",
                    chat_id=API_CHAT_ID,
                ),
                timeout=timeout_s,
            )
            response_text = _response_text(response)
    except asyncio.TimeoutError:
        return _error_json(504, f"Request timed out after {timeout_s}s")
    except Exception:
        logger.exception("Error processing Apple Health webhook")
        return _error_json(500, "Internal server error", err_type="server_error")

    return web.json_response({"status": "ok", "response": response_text})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(agent_loop, model_name: str = "nanobot", request_timeout: float = 120.0) -> web.Application:
    """Create the aiohttp application.

    Args:
        agent_loop: An initialized AgentLoop instance.
        model_name: Model name reported in responses.
        request_timeout: Per-request timeout in seconds.
    """
    app = web.Application()
    app["agent_loop"] = agent_loop
    app["model_name"] = model_name
    app["request_timeout"] = request_timeout
    app["session_locks"] = {}  # per-user locks, keyed by session_key

    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_get("/v1/models", handle_models)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/webhook/apple-health", handle_apple_health_webhook)
    return app
