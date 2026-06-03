"""Pydantic-ai agent construction, extracted from ``BaseAgent``.

Collapses the previous duplicated build paths into a single ``build_pydantic_agent``
entry point. MCP subsystem has been removed; server-loading hooks now return
empty toolsets so the agent build path stays intact without any MCP wiring.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic_ai import Agent as PydanticAgent

from code_puppy.agents._compaction import make_history_processor
from code_puppy.agents._steer_processor import make_steer_history_processor
from code_puppy.agents.event_stream_handler import event_stream_handler
from code_puppy.callbacks import on_wrap_pydantic_agent
from code_puppy.config import CONFIG_DIR, get_global_model_name
from code_puppy.messaging import emit_error, emit_info, emit_warning
from code_puppy.model_factory import ModelFactory, make_model_settings

_AGENT_RULE_FILES = ("AGENTS.md", "AGENT.md", "agents.md", "agent.md")
_CODE_PUPPY_DIR = ".code_puppy"


def load_puppy_rules() -> Optional[str]:
    """Load AGENT(S).md from global config dir and/or the current project dir.

    Global rules (``~/.code_puppy/AGENTS.md``) come first; project-local rules
    are appended, allowing projects to override/extend global ones.

    **Search order for project rules:**

    1. ``.code_puppy/AGENTS.md`` (preferred — keeps root clean)
    2. ``./AGENTS.md`` (alternate location)

    Returns ``None`` if neither exists.
    """
    global_rules: Optional[str] = None
    for name in _AGENT_RULE_FILES:
        candidate = Path(CONFIG_DIR) / name
        if candidate.exists():
            global_rules = candidate.read_text(encoding="utf-8-sig")
            break

    project_rules: Optional[str] = None

    # Priority 1: Check .code_puppy/ directory (preferred location)
    code_puppy_dir = Path(_CODE_PUPPY_DIR)
    if code_puppy_dir.is_dir():
        for name in _AGENT_RULE_FILES:
            candidate = code_puppy_dir / name
            if candidate.exists():
                project_rules = candidate.read_text(encoding="utf-8-sig")
                break

    # Priority 2: Fallback to project root
    if project_rules is None:
        for name in _AGENT_RULE_FILES:
            candidate = Path(name)
            if candidate.exists():
                project_rules = candidate.read_text(encoding="utf-8-sig")
                break

    rules = [r for r in (global_rules, project_rules) if r]
    return "\n\n".join(rules) if rules else None


def load_mcp_servers(
    extra_headers: Optional[Dict[str, str]] = None,
    agent_name: Optional[str] = None,
) -> List[Any]:
    """Return pydantic-ai compatible MCP servers, or ``[]`` if disabled."""
    del extra_headers  # accepted for API compatibility; manager owns headers
    return []


def reload_mcp_servers(agent_name: Optional[str] = None) -> List[Any]:
    """Force re-sync from ``mcp_servers.json`` and return updated servers."""
    return []


async def autostart_bound_servers_async(manager: Any, agent_name: str) -> None:
    """Async autostart stub (MCP servers are auto-started elsewhere)."""
    return None


def _autostart_bound_servers(manager: Any, agent_name: str) -> None:
    """Sync autostart stub (MCP servers are auto-started elsewhere)."""
    return None


def _assemble_instructions(agent: Any, resolved_model_name: str) -> str:
    """Compose full system prompt + puppy rules + extended-thinking note."""
    from code_puppy.model_utils import prepare_prompt_for_model
    from code_puppy.tools import (
        EXTENDED_THINKING_PROMPT_NOTE,
        has_extended_thinking_active,
    )

    instructions = agent.get_full_system_prompt()
    puppy_rules = load_puppy_rules()
    if puppy_rules:
        instructions += f"\n\n{puppy_rules}"

    if has_extended_thinking_active(resolved_model_name):
        instructions += EXTENDED_THINKING_PROMPT_NOTE

    prepared = prepare_prompt_for_model(
        agent.get_model_name(), instructions, "", prepend_system_to_user=False
    )
    return prepared.instructions


def build_pydantic_agent(
    agent: Any,
    output_type: Any = str,
    message_group: Optional[str] = None,
) -> Any:
    """Build (and wire up) the pydantic-ai agent for ``agent``.

    Replaces the old ``reload_code_generation_agent`` + ``_create_agent_with_output_type``
    pair. Side effects on ``agent``:

    - ``agent._puppy_rules = None`` (invalidates any cached rules)
    - ``agent.cur_model``             ← resolved pydantic-ai model
    - ``agent._last_model_name``      ← resolved model name
    - ``agent.pydantic_agent``        ← the final (possibly plugin-wrapped) agent
    - ``agent._code_generation_agent`` ← same as ``pydantic_agent``
    - ``agent._mcp_servers``          ← MCP toolsets (empty after removal)
    """
    from code_puppy.tools import register_tools_for_agent

    agent._puppy_rules = None
    message_group = message_group or str(uuid.uuid4())

    models_config = ModelFactory.load_config()
    model, resolved_model_name = load_model_with_fallback(
        agent.get_model_name(), models_config, message_group
    )
    instructions = _assemble_instructions(agent, resolved_model_name)
    model_settings = make_model_settings(resolved_model_name)
    history_processor = make_history_processor(agent)
    steer_processor = make_steer_history_processor(agent)

    def _new_pydantic_agent(toolsets: List[Any]) -> PydanticAgent:
        return PydanticAgent(
            model=model,
            instructions=instructions,
            output_type=output_type,
            retries=3,
            toolsets=toolsets,
            # Order is critical: compaction first (may trim history to fit
            # context), THEN steer injection (the steer must NOT be subject
            # to compaction on this call — it just arrived).
            history_processors=[history_processor, steer_processor],
            model_settings=model_settings,
        )

    probe_agent = _new_pydantic_agent(toolsets=[])
    agent_tools = agent.get_available_tools()
    logical_agent_name = getattr(agent, "name", None) or agent.__class__.__name__
    register_tools_for_agent(
        probe_agent,
        agent_tools,
        model_name=resolved_model_name,
        agent_name=logical_agent_name,
    )

    filtered_mcp_servers: List[Any] = []

    # Pass 2: real build. MCP servers are always included in the constructor;
    # plugins (e.g. DBOS) may swap them out at run time via the
    # ``agent_run_context`` hook if their wrapper can't handle them directly.
    final_pydantic = _new_pydantic_agent(toolsets=filtered_mcp_servers)
    register_tools_for_agent(
        final_pydantic,
        agent_tools,
        model_name=resolved_model_name,
        agent_name=logical_agent_name,
    )

    agent.cur_model = model
    agent._last_model_name = resolved_model_name
    agent._mcp_servers = filtered_mcp_servers

    wrapped = on_wrap_pydantic_agent(
        agent,
        final_pydantic,
        event_stream_handler=event_stream_handler,
        message_group=message_group,
        kind="main",
    )
    agent.pydantic_agent = wrapped
    agent._code_generation_agent = wrapped
    return wrapped


def build_tool_probe_for_agent(agent: Any) -> Optional[Any]:
    """Build a stripped-down pydantic agent JUST for tool introspection.

    Used by token-overhead estimators that need to count tool docs/schemas
    *before* the real agent has been constructed. Skips MCP servers, history
    processors, instructions, and plugin wrapping — only the registered
    pydantic-ai tools matter here.

    Returns ``None`` if model resolution fails. The caller is responsible for
    caching the result; this is a non-trivial construction even with the
    shortcuts.
    """
    from code_puppy.tools import register_tools_for_agent

    try:
        models_config = ModelFactory.load_config()
        model, resolved_model_name = load_model_with_fallback(
            agent.get_model_name() or "",
            models_config,
            message_group=str(uuid.uuid4()),
        )
    except Exception:
        return None

    try:
        probe = PydanticAgent(
            model=model,
            instructions="",
            output_type=str,
            retries=1,
            toolsets=[],
        )
        register_tools_for_agent(
            probe, agent.get_available_tools(), model_name=resolved_model_name
        )
    except Exception:
        return None
    return probe


def load_model_with_fallback(
    requested_model_name: str,
    models_config: Dict[str, Any],
    message_group: str,
) -> Tuple[Any, str]:
    """Load the requested model, or fall back to a sensible alternative.

    Falls back in order: the globally configured model, then any other
    configured model. Raises ``ValueError`` only if nothing loads.
    """
    try:
        return ModelFactory.get_model(
            requested_model_name, models_config
        ), requested_model_name
    except ValueError as exc:
        available = list(models_config.keys())
        available_str = (
            ", ".join(sorted(available)) if available else "no configured models"
        )
        emit_warning(
            f"Model '{requested_model_name}' not found. Available models: {available_str}",
            message_group=message_group,
        )

        candidates: List[str] = []
        global_candidate = get_global_model_name()
        if global_candidate:
            candidates.append(global_candidate)
        for candidate in available:
            if candidate not in candidates:
                candidates.append(candidate)

        for candidate in candidates:
            if not candidate or candidate == requested_model_name:
                continue
            try:
                model = ModelFactory.get_model(candidate, models_config)
                emit_info(
                    f"Using fallback model: {candidate}", message_group=message_group
                )
                return model, candidate
            except ValueError:
                continue

        friendly = (
            "No valid model could be loaded. Update the model configuration or "
            "set a valid model with `config set`."
        )
        emit_error(friendly, message_group=message_group)
        raise ValueError(friendly) from exc


def filter_conflicting_mcp_tools(
    mcp_servers: List[Any],
    existing_tool_names: Set[str],
) -> List[Any]:
    """Strip any MCP tools whose names collide with already-registered tools."""
    return []
