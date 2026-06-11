from __future__ import annotations

# Agent-agnostic invocation for autonomous drafting.
#
# The autonomous drafter (used by the unattended `daily`/`poll` cron) generates
# message text by shelling out to a *coding agent CLI* in one-shot headless
# mode — NOT by calling any LLM API with a key. It uses whatever agent you
# already have authenticated on the machine: Claude Code, Codex, Cursor, or
# Gemini. This keeps the "by agent only, no API keys" property.
#
# When a human drives an agent interactively (Claude Code, Codex, Cursor),
# the agent itself writes the draft and calls `linkedin connect/dm` to send —
# this module isn't involved at all. It only matters for unattended runs.
#
# Selection order:
#   1. DRAFTER_AGENT_CMD  — a custom command prefix; the prompt is appended as
#                           one argument (e.g. "my-agent --headless").
#   2. DRAFTER_AGENT      — force a known preset: claude | codex | cursor | gemini.
#   3. auto-detect        — first of claude, codex, cursor-agent, gemini on PATH.

import os
import shlex
import shutil
import subprocess


class AgentError(RuntimeError):
    pass


# name -> (binary, argv-builder). Each builder returns the full argv for a
# one-shot "prompt in → final text out" call. Flags are best-effort defaults
# for each CLI's non-interactive/print mode; override with DRAFTER_AGENT_CMD if
# a given version differs.
_PRESETS: dict[str, tuple[str, callable]] = {
    "claude": ("claude", lambda b, p: [b, "-p", p, "--output-format", "text"]),
    "codex": ("codex", lambda b, p: [b, "exec", p]),
    "cursor": ("cursor-agent", lambda b, p: [b, "-p", p]),
    "gemini": ("gemini", lambda b, p: [b, "-p", p]),
}
_DETECT_ORDER = ("claude", "codex", "cursor", "gemini")


def resolve_agent() -> tuple[str, str] | None:
    """Return (agent_name, binary_path) for the configured/available agent, or
    None if none is found. Raises AgentError only when DRAFTER_AGENT names an
    agent whose binary isn't on PATH (an explicit misconfiguration)."""
    forced = (os.getenv("DRAFTER_AGENT") or "").strip().lower()
    if forced:
        if forced not in _PRESETS:
            raise AgentError(
                f"DRAFTER_AGENT={forced!r} not recognized; known: {', '.join(_PRESETS)}"
            )
        path = shutil.which(_PRESETS[forced][0])
        if not path:
            raise AgentError(
                f"DRAFTER_AGENT={forced!r} but '{_PRESETS[forced][0]}' is not on PATH"
            )
        return forced, path
    for name in _DETECT_ORDER:
        path = shutil.which(_PRESETS[name][0])
        if path:
            return name, path
    return None


def _build_argv(prompt: str) -> list[str]:
    custom = os.getenv("DRAFTER_AGENT_CMD")
    if custom:
        # Split the command prefix safely; append the (possibly multi-line)
        # prompt as a single argv element so quoting/newlines can't break it.
        return shlex.split(custom) + [prompt]
    resolved = resolve_agent()
    if not resolved:
        raise AgentError(
            "no coding-agent CLI found on PATH (looked for: claude, codex, "
            "cursor-agent, gemini). Install one, set DRAFTER_AGENT, or set "
            "DRAFTER_AGENT_CMD to a custom command."
        )
    name, path = resolved
    return _PRESETS[name][1](path, prompt)


def invoke(prompt: str, timeout: int = 90) -> str:
    """Run the agent one-shot and return stdout. Raises AgentError on a missing
    agent, a non-zero exit, or timeout.

    stdin is closed via DEVNULL: in non-TTY contexts (cron, launchd) some agent
    CLIs otherwise block waiting on stdin and then exit non-zero."""
    argv = _build_argv(prompt)
    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout,
        check=False, stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise AgentError(
            f"agent '{argv[0]}' exited {proc.returncode}\nstderr:\n{proc.stderr[:500]}"
        )
    return proc.stdout


def warmup(timeout: int = 20) -> bool:
    """Best-effort trivial call to serialize any pending auth refresh before a
    burst of agent calls. Never raises; returns True iff the call returned 0."""
    try:
        argv = _build_argv("ok")
    except AgentError:
        return False
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            check=False, stdin=subprocess.DEVNULL,
        )
        return proc.returncode == 0
    except Exception:
        return False
