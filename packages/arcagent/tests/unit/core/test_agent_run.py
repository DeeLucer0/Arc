"""Phase A — the single streaming, session-bound agent.run (SPEC-027 FR-1).

agent.run is the only execution entry: always session-bound, always streaming.
These tests pin the contract — it streams arcrun StreamEvents, ends on
TurnEndEvent, requires a session, and preserves history parity with the old
chat() (user + assistant turns land in the session's SessionManager).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from arcrun import StreamEvent, TokenEvent, TurnEndEvent

from arcagent.core.agent import ArcAgent
from arcagent.core.config import (
    AgentConfig,
    ArcAgentConfig,
    ContextConfig,
    IdentityConfig,
    LLMConfig,
    TelemetryConfig,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture()
def agent_config(tmp_path: Path, workspace: Path) -> ArcAgentConfig:
    return ArcAgentConfig(
        agent=AgentConfig(
            name="run-test-agent",
            org="testorg",
            type="executor",
            workspace=str(workspace),
        ),
        llm=LLMConfig(model="test/model"),
        identity=IdentityConfig(did="", key_dir=str(tmp_path / "keys"), vault_path=""),
        telemetry=TelemetryConfig(enabled=False),
        context=ContextConfig(max_tokens=10000),
    )


async def _fake_stream(*tokens: str) -> AsyncIterator[StreamEvent]:
    for t in tokens:
        yield TokenEvent(text=t)
    yield TurnEndEvent(final_text="".join(tokens))


def _patch_stream(*tokens: str) -> Any:
    async def _factory(*args: Any, **kwargs: Any) -> AsyncIterator[StreamEvent]:
        return _fake_stream(*tokens)

    return patch("arcagent.core.agent_dispatch.arcrun_run_stream", side_effect=_factory)


@pytest.mark.asyncio
@patch("arcagent.core.model_manager.load_eval_model")
async def test_run_streams_and_requires_session(
    mock_load_model: MagicMock,
    agent_config: ArcAgentConfig,
) -> None:
    """run() yields >=2 StreamEvents ending in TurnEndEvent; needs a session."""
    mock_load_model.return_value = MagicMock(close=AsyncMock())
    agent = ArcAgent(config=agent_config)

    with _patch_stream("hello", " world"):
        await agent.startup()
        try:
            session = await agent.session("unit:test")
            events = [ev async for ev in agent.run("hi", session=session)]

            # Calling without a session is a type error (keyword-only, required).
            with pytest.raises(TypeError):
                agent.run("hi")  # type: ignore[call-arg]
        finally:
            await agent.shutdown()

    assert len(events) >= 2
    assert isinstance(events[-1], TurnEndEvent)
    assert any(isinstance(e, TokenEvent) for e in events)


@pytest.mark.asyncio
@patch("arcagent.core.model_manager.load_eval_model")
async def test_run_appends_user_and_assistant_to_session(
    mock_load_model: MagicMock,
    agent_config: ArcAgentConfig,
) -> None:
    """History parity: a turn via run appends user+assistant to the session (AC-1.4)."""
    mock_load_model.return_value = MagicMock(close=AsyncMock())
    agent = ArcAgent(config=agent_config)

    with _patch_stream("answer"):
        await agent.startup()
        try:
            session = await agent.session("unit:parity")
            async for _ in agent.run("question", session=session):
                pass
            messages = session.get_messages()
        finally:
            await agent.shutdown()

    user_turn, assistant_turn = messages[-2], messages[-1]
    assert (user_turn["role"], user_turn["content"]) == ("user", "question")
    assert (assistant_turn["role"], assistant_turn["content"]) == ("assistant", "answer")


@pytest.mark.asyncio
@patch("arcagent.core.model_manager.load_eval_model")
async def test_session_local_resumes_by_key(
    mock_load_model: MagicMock,
    agent_config: ArcAgentConfig,
) -> None:
    """agent.session(key) is open-or-resume: same key reloads prior history (A.6)."""
    mock_load_model.return_value = MagicMock(close=AsyncMock())
    agent = ArcAgent(config=agent_config)

    with _patch_stream("first"):
        await agent.startup()
        try:
            session = await agent.session("cli:run")
            async for _ in agent.run("turn one", session=session):
                pass

            # Same key from the pool returns the same live manager.
            again = await agent.session("cli:run")
            assert again is session
            assert again.session_id == "cli:run"
            assert any(m["content"] == "turn one" for m in again.get_messages())
        finally:
            await agent.shutdown()


@pytest.mark.asyncio
@patch("arcagent.core.model_manager.load_eval_model")
async def test_run_collected_returns_result_for_callbacks(
    mock_load_model: MagicMock,
    agent_config: ArcAgentConfig,
) -> None:
    """run_collected drives a keyed session and returns the final result."""
    mock_load_model.return_value = MagicMock(close=AsyncMock())
    agent = ArcAgent(config=agent_config)

    with _patch_stream("done"):
        await agent.startup()
        try:
            result = await agent.run_collected("go", session_key="scheduler:cron-1")
        finally:
            await agent.shutdown()

    assert result.content == "done"


@pytest.mark.asyncio
@patch("arcagent.core.model_manager.load_eval_model")
async def test_old_entry_methods_are_gone(
    mock_load_model: MagicMock,
    agent_config: ArcAgentConfig,
) -> None:
    """chat/run_async/run_stream/chat_async/chat_stream no longer exist (AC-1.1)."""
    mock_load_model.return_value = MagicMock(close=AsyncMock())
    agent = ArcAgent(config=agent_config)
    for name in ("chat", "run_async", "run_stream", "chat_async", "chat_stream"):
        assert not hasattr(agent, name), f"{name} must be deleted"
