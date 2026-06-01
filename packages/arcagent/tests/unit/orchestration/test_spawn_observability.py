"""Spawn identity + lineage observability (SPEC-028 FR-3).

A spawned child must record under its OWN operational identity:
- its run_events spool under the child actor_did (F5, task 3.1),
- its llm_calls carry the child agent_did/agent_label via a task-local contextvar
  (F4 / C2, tasks 3.2/3.2b),
- a spawn_event captures the parent→child lineage edge (task 3.3),
- and the path degrades (run_events still tagged) rather than breaks (task 3.5).

arcrun stays a pure loop — all spawn logic is arcagent (task 3.6).
"""

from __future__ import annotations

import sys
from unittest.mock import patch

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

import pytest
from arcrun.events import EventBus
from arcrun.registry import ToolRegistry
from arcrun.state import RunState
from arcrun.types import Tool
from arctrust import derive_child_identity

from arcagent.orchestration.spawn import spawn, spawn_many
from arcagent.orchestration.spawn_handle import SpawnSpec

from ._mock_llm import LLMResponse, MockModel

_PARENT_DID = "did:arc:acme:agent:parent/aabbccdd"


async def _echo(params: dict, ctx: object) -> str:
    return f"echo: {params.get('input', '')}"


ECHO_TOOL = Tool(
    name="echo",
    description="Echo",
    input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
    execute=_echo,
)


def _parent_state(*, actor_did: str | None = _PARENT_DID, depth: int = 0) -> RunState:
    bus = EventBus(run_id="parent-run", spool_actor_did=actor_did)
    reg = ToolRegistry(tools=[ECHO_TOOL], event_bus=bus)
    return RunState(
        messages=[], registry=reg, event_bus=bus, run_id="parent-run", depth=depth, max_depth=3
    )


def _identity(n: int = 0):
    return derive_child_identity(parent_sk_bytes=b"\xcd" * 32, spawn_id=f"obs-{n}", wallclock_timeout_s=30)


def _telemetry_model() -> object:
    """A real TelemetryModule wrapping a stub provider, so it spools llm_call records."""
    from unittest.mock import AsyncMock, MagicMock

    from arcllm.modules.telemetry import TelemetryModule
    from arcllm.types import LLMProvider
    from arcllm.types import LLMResponse as RealResponse
    from arcllm.types import Usage as RealUsage

    inner = MagicMock(spec=LLMProvider)
    inner.name = "stub"
    inner.invoke = AsyncMock(
        return_value=RealResponse(
            content="done",
            tool_calls=[],
            stop_reason="end_turn",
            model="stub-model",
            usage=RealUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )
    )
    # Configured with the PARENT identity — children must override it via contextvar.
    return TelemetryModule({"agent_did": _PARENT_DID, "agent_label": "parent"}, inner)


def _capture():
    """Patch every producer's spool binding into one shared list."""
    records: list = []
    patches = [
        patch("arcagent.orchestration.spawn._spool_record", records.append),
        patch("arcrun.events._spool_record", records.append),
        patch("arcllm.modules.telemetry._spool_record", records.append),
    ]
    return records, patches


@pytest.mark.asyncio
async def test_child_run_events_tagged() -> None:
    """Task 3.1 (F5) — the child's run_events spool under the child actor_did."""
    state = _parent_state()
    identity = _identity(1)
    records, patches = _capture()
    model = MockModel([LLMResponse(content="ok", stop_reason="end_turn")])
    with patches[0], patches[1], patches[2]:
        await spawn(parent_state=state, task="t", tools=[ECHO_TOOL], system_prompt="s",
                    identity=identity, model=model)
    child_run_events = [r for r in records if r.kind == "run_event"]
    assert child_run_events, "child run_events must spool"
    assert all(r.actor_did == identity.did for r in child_run_events)
    assert all(r.actor_did != _PARENT_DID for r in child_run_events)


@pytest.mark.asyncio
async def test_child_llm_calls_separated() -> None:
    """Task 3.2 (F4) — the child's llm_calls carry the child identity, not the parent's."""
    state = _parent_state()
    identity = _identity(2)
    records, patches = _capture()
    with patches[0], patches[1], patches[2]:
        await spawn(parent_state=state, task="t", tools=[ECHO_TOOL], system_prompt="s",
                    identity=identity, model=_telemetry_model(), role="researcher")
    llm_calls = [r for r in records if r.kind == "llm_call"]
    assert llm_calls, "child llm_call must spool"
    assert all(r.actor_did == identity.did for r in llm_calls)
    assert all(r.actor_did != _PARENT_DID for r in llm_calls)
    assert all(r.agent_label and r.agent_label != "parent" for r in llm_calls)


@pytest.mark.asyncio
async def test_concurrent_children_not_cross_attributed() -> None:
    """Task 3.2b (C2) — concurrent spawn_many children never cross-attribute llm_calls."""
    parent = _parent_state()
    model = _telemetry_model()  # shared model across both children
    specs = [
        SpawnSpec(
            task=f"t{i}", tools=[ECHO_TOOL], system_prompt="s", parent_state=parent,
            child_did=_identity(10 + i).did, child_sk_bytes=_identity(10 + i).sk_bytes,
            wallclock_timeout_s=30, model=model,
        )
        for i in range(2)
    ]
    child_dids = {s.child_did for s in specs}
    records, patches = _capture()
    with patches[0], patches[1], patches[2]:
        await spawn_many(specs, max_concurrent=2)
    llm_calls = [r for r in records if r.kind == "llm_call"]
    assert llm_calls
    # Every llm_call is attributed to one of the two children — and only those.
    assert {r.actor_did for r in llm_calls} <= child_dids
    assert _PARENT_DID not in {r.actor_did for r in llm_calls}


@pytest.mark.asyncio
async def test_spawn_lineage_recorded() -> None:
    """Task 3.3 — a spawn_event records the parent→child edge (parent/child/role/depth)."""
    state = _parent_state()
    identity = _identity(3)
    records, patches = _capture()
    model = MockModel([LLMResponse(content="ok", stop_reason="end_turn")])
    with patches[0], patches[1], patches[2]:
        await spawn(parent_state=state, task="t", tools=[ECHO_TOOL], system_prompt="s",
                    identity=identity, model=model, role="researcher")
    spawn_events = [r for r in records if r.kind == "spawn_event"]
    assert len(spawn_events) == 1
    ev = spawn_events[0]
    assert ev.parent_did == _PARENT_DID
    assert ev.child_did == identity.did
    assert ev.role == "researcher"
    assert ev.depth == 1  # parent depth 0 → child depth 1


@pytest.mark.asyncio
async def test_child_identity_degrades_safely() -> None:
    """Task 3.5 — a non-telemetry model still tags run_events; it degrades, not breaks."""
    state = _parent_state()
    identity = _identity(4)
    records, patches = _capture()
    model = MockModel([LLMResponse(content="ok", stop_reason="end_turn")])  # no telemetry
    with patches[0], patches[1], patches[2]:
        result = await spawn(parent_state=state, task="t", tools=[ECHO_TOOL], system_prompt="s",
                             identity=identity, model=model)
    assert result.status in ("completed", "max_iterations")
    # run_events still spool under the child identity even with no llm_call separation.
    run_events = [r for r in records if r.kind == "run_event"]
    assert run_events and all(r.actor_did == identity.did for r in run_events)


def test_arcstore_off_silences_child() -> None:
    """Posture preserved: parent not recording (actor_did=None) → child spools nothing."""

    async def _run() -> list:
        state = _parent_state(actor_did=None)
        records, patches = _capture()
        model = MockModel([LLMResponse(content="ok", stop_reason="end_turn")])
        with patches[0], patches[1], patches[2]:
            await spawn(parent_state=state, task="t", tools=[ECHO_TOOL], system_prompt="s",
                        identity=_identity(5), model=model)
        return records

    import asyncio

    records = asyncio.run(_run())
    assert [r for r in records if r.kind in ("run_event", "spawn_event")] == []
