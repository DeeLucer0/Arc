"""`/api/agents/{id}/{stats,traces,audit}` route handlers."""

from __future__ import annotations

from collections import deque
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from arcui.routes.agent_detail._common import _agent_root


async def get_stats(request: Request) -> JSONResponse:
    """Per-agent stats — delegates to per-agent or global aggregator.

    Mirrors the behaviour of the existing ``/api/stats?agent_id=`` route but
    uses the path-param style for symmetry with the agent-detail screen.
    """
    agent_id = request.path_params["id"]
    agent_root = _agent_root(request, agent_id)
    if agent_root is None:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    registry = request.app.state.agent_registry
    entry = registry.get(agent_id)
    aggregator = entry.aggregator if entry and entry.aggregator else getattr(
        request.app.state, "aggregator", None
    )
    if aggregator is None:
        return JSONResponse({"stats": {}, "window": "24h"})
    window = request.query_params.get("window", "24h")
    if window not in {"1h", "24h", "7d"}:
        return JSONResponse({"error": "Invalid window"}, status_code=400)
    return JSONResponse({"stats": aggregator.stats(window), "window": window})


async def get_traces(request: Request) -> JSONResponse:
    agent_id = request.path_params["id"]
    agent_root = _agent_root(request, agent_id)
    if agent_root is None:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    store = request.app.state.trace_store
    if store is None:
        return JSONResponse({"traces": [], "cursor": None})

    try:
        limit = max(1, min(500, int(request.query_params.get("limit", "50"))))
    except ValueError:
        return JSONResponse({"error": "Invalid limit"}, status_code=400)

    records, cursor = await store.query(limit=limit, agent=agent_id)
    return JSONResponse(
        {
            "traces": [r.model_dump() for r in records],
            "cursor": cursor,
        }
    )


async def get_audit(request: Request) -> JSONResponse:
    agent_id = request.path_params["id"]
    agent_root = _agent_root(request, agent_id)
    if agent_root is None:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    buffer: deque[dict[str, Any]] = getattr(request.app.state, "audit_buffer", None) or deque()
    try:
        limit = max(1, min(1000, int(request.query_params.get("limit", "100"))))
    except ValueError:
        return JSONResponse({"error": "Invalid limit"}, status_code=400)

    events = [e for e in buffer if e.get("agent_id") == agent_id][-limit:]
    return JSONResponse({"events": events})
