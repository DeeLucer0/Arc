"""Dry-run result schema.

Lifted out of ``arcskill.hub.dry_run`` so the Firecracker and Docker
sibling modules can return ``DryRunResult`` without creating a circular
import (dry_run imports from each backend; each backend imports the
result type).

Re-exported through ``arcskill.hub.dry_run`` — callers continue to do
``from arcskill.hub.dry_run import DryRunResult``.
"""

from __future__ import annotations

from pydantic import BaseModel


class DryRunResult(BaseModel):
    """Output of the dry-run stage.

    Attributes
    ----------
    passed:
        True if the fixture ran to completion without error.
    stdout:
        Captured stdout from the sandbox (truncated to 4 KB).
    stderr:
        Captured stderr from the sandbox (truncated to 4 KB).
    exit_code:
        Process exit code (0 = success, None = timeout / unavailable).
    backend_used:
        ``"firecracker"``, ``"docker"``, or ``"skipped"`` (local/test mode).
    skipped:
        True when sandbox execution was skipped — set only when no backend
        was available and SandboxRequired wasn't raised (no caller path
        currently produces this in production; retained for typing).
    duration_s:
        Wall-clock seconds for the dry-run (0.0 when skipped).
    vm_id:
        Per-VM unique identifier (UUID string).  Empty string when not using
        Firecracker.
    """

    passed: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    backend_used: str = "skipped"
    skipped: bool = False
    duration_s: float = 0.0
    vm_id: str = ""
