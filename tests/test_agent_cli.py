"""Tests for the agent-agnostic invocation layer (agent_cli).

Uses `echo` as a stand-in agent CLI so the override/invocation path is
exercised without any real coding agent installed.
"""

from __future__ import annotations

import pytest

from linkedin_agent import agent_cli


@pytest.mark.unit
def test_custom_cmd_override_appends_prompt(monkeypatch):
    # DRAFTER_AGENT_CMD is a command prefix; the prompt is appended as one arg.
    monkeypatch.setenv("DRAFTER_AGENT_CMD", "echo")
    out = agent_cli.invoke("hello world")
    assert out.strip() == "hello world"


@pytest.mark.unit
def test_custom_cmd_takes_precedence_over_forced_agent(monkeypatch):
    monkeypatch.setenv("DRAFTER_AGENT", "claude")      # would normally require claude on PATH
    monkeypatch.setenv("DRAFTER_AGENT_CMD", "echo")    # but the explicit cmd wins
    assert agent_cli.invoke("ping").strip() == "ping"


@pytest.mark.unit
def test_unknown_forced_agent_raises(monkeypatch):
    monkeypatch.delenv("DRAFTER_AGENT_CMD", raising=False)
    monkeypatch.setenv("DRAFTER_AGENT", "no-such-agent")
    with pytest.raises(agent_cli.AgentError, match="not recognized"):
        agent_cli.resolve_agent()


@pytest.mark.unit
def test_warmup_succeeds_with_echo(monkeypatch):
    monkeypatch.setenv("DRAFTER_AGENT_CMD", "echo")
    assert agent_cli.warmup() is True


@pytest.mark.unit
def test_warmup_false_when_no_agent(monkeypatch):
    monkeypatch.delenv("DRAFTER_AGENT", raising=False)
    monkeypatch.delenv("DRAFTER_AGENT_CMD", raising=False)
    # Point at a definitely-absent binary so detection finds nothing.
    monkeypatch.setattr(agent_cli, "_DETECT_ORDER", ())
    assert agent_cli.warmup() is False
