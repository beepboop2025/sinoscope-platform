"""camelCase↔snake_case conversion for JSON API.

Provides:
1. CamelCaseResponse — JSONResponse subclass that converts snake_case keys to camelCase
2. convert_request_body — dependency that converts incoming camelCase body to snake_case
3. CaseConverterMiddleware — request-only middleware for camelCase→snake_case conversion

The response conversion is done via a custom default_response_class on the FastAPI app,
which avoids all middleware ordering conflicts with GZip.
"""

import json
import re
from typing import Any

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


_CAMEL_RE = re.compile(r"([A-Z])")
_SNAKE_RE = re.compile(r"_([a-z])")

# Paths whose response should NOT be converted
_SKIP_RESPONSE_PREFIXES = ("/api/data/", "/metrics")


def to_snake_case(name: str) -> str:
    return _CAMEL_RE.sub(lambda m: "_" + m.group(1).lower(), name).lstrip("_")


def to_camel_case(name: str) -> str:
    return _SNAKE_RE.sub(lambda m: m.group(1).upper(), name)


def convert_keys(obj: Any, converter) -> Any:
    if isinstance(obj, dict):
        return {converter(k): convert_keys(v, converter) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_keys(item, converter) for item in obj]
    return obj


class CamelCaseResponse(JSONResponse):
    """JSONResponse that auto-converts snake_case keys to camelCase."""

    def render(self, content: Any) -> bytes:
        converted = convert_keys(content, to_camel_case)
        return json.dumps(
            converted,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


class RawJSONResponse(JSONResponse):
    """Standard JSONResponse with no key conversion (for /api/data/*)."""
    pass


class CaseConverterMiddleware:
    """Request-only ASGI middleware: converts incoming JSON body camelCase→snake_case."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        if method not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return

        body_chunks: list[bytes] = []
        body_complete = False

        async def receive_wrapper() -> Message:
            nonlocal body_complete
            message = await receive()

            if message.get("type") == "http.request":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                body_chunks.append(body)

                if not more_body and not body_complete:
                    body_complete = True
                    full_body = b"".join(body_chunks)
                    if full_body:
                        try:
                            data = json.loads(full_body)
                            converted = convert_keys(data, to_snake_case)
                            new_body = json.dumps(converted).encode("utf-8")
                            return {
                                "type": "http.request",
                                "body": new_body,
                                "more_body": False,
                            }
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass
            return message

        await self.app(scope, receive_wrapper, send)
