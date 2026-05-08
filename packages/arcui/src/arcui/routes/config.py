"""Config routes — /api/config (GET/PATCH)."""

from __future__ import annotations

import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from arcui.schemas import ErrorResponse

logger = logging.getLogger(__name__)


async def get_config(request: Request) -> JSONResponse:
    """GET /api/config — return current config snapshot."""
    ctrl = request.app.state.config_controller
    if ctrl is None:
        return JSONResponse(
            ErrorResponse(error="No config controller configured").model_dump(mode="json"),
            status_code=404,
        )

    snapshot = ctrl.get_snapshot()
    return JSONResponse(snapshot.model_dump())


async def patch_config(request: Request) -> JSONResponse:
    """PATCH /api/config — update config (operator only)."""
    if request.state.role != "operator":
        return JSONResponse(
            ErrorResponse(error="Operator role required").model_dump(mode="json"),
            status_code=403,
        )

    ctrl = request.app.state.config_controller
    if ctrl is None:
        return JSONResponse(
            ErrorResponse(error="No config controller configured").model_dump(mode="json"),
            status_code=404,
        )

    body = await request.body()
    try:
        updates = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse(
            ErrorResponse(error="Invalid JSON body").model_dump(mode="json"),
            status_code=400,
        )

    try:
        new_snapshot = ctrl.patch(updates, actor=request.state.role)
    except (ValueError, KeyError) as e:
        return JSONResponse(
            ErrorResponse(error=str(e)).model_dump(mode="json"),
            status_code=400,
        )
    except Exception:  # reason: fail-open — log + continue
        logger.exception("Unexpected error during config patch")
        return JSONResponse(
            ErrorResponse(error="Internal error processing config update").model_dump(mode="json"),
            status_code=500,
        )

    return JSONResponse(new_snapshot.model_dump())


routes = [
    Route("/api/config", get_config, methods=["GET"]),
    Route("/api/config", patch_config, methods=["PATCH"]),
]
