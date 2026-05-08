"""Manifest membership policy for verified backend loads.

After ``_verifier.verify_allowed_backends_signature`` returns the verified
mapping, ``enforce_manifest_contains`` checks that the requested backend
name is actually listed and emits the deny audit event when it isn't.
Kept in a separate module so the policy enforcement is independent of the
crypto primitives.
"""

from __future__ import annotations

from typing import Any

from arcrun.backends._audit import emit_denied
from arcrun.backends._verifier import BackendSignatureError


def enforce_manifest_contains(
    name: str,
    verified: dict[str, dict[str, Any]],
    *,
    tier: str = "unknown",
    sink: Any | None = None,
) -> None:
    """Raise BackendSignatureError if ``name`` is not in the verified mapping."""
    if name in verified:
        return
    emit_denied(name, tier=tier, reason="not in signed manifest", sink=sink)
    raise BackendSignatureError(f"Backend '{name}' is not in the signed allowed_backends manifest.")
