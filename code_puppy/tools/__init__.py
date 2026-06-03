from code_puppy.callbacks import on_register_agent_tools, on_register_tools
from code_puppy.messaging import emit_warning
from code_puppy.tools.agent_tools import register_invoke_agent, register_list_agents
from code_puppy.tools.command_runner import (
    register_agent_run_shell_command,
    register_agent_share_your_reasoning,
)
from code_puppy.tools.display import (
    display_non_streamed_result as display_non_streamed_result,
)
from code_puppy.tools.file_modifications import (
    register_create_file,
    register_delete_file,
    register_delete_snippet,
    register_edit_file,
    register_replace_in_file,
)
from code_puppy.tools.file_operations import (
    register_grep,
    register_list_files,
    register_read_file,
)

# Map of tool names to their individual registration functions
TOOL_REGISTRY = {
    # Agent Tools
    "list_agents": register_list_agents,
    "invoke_agent": register_invoke_agent,
    # File Operations
    "list_files": register_list_files,
    "read_file": register_read_file,
    "grep": register_grep,
    # File Modifications
    "edit_file": register_edit_file,  # DEPRECATED: auto-expanded to create_file, replace_in_file, delete_snippet
    "create_file": register_create_file,
    "replace_in_file": register_replace_in_file,
    "delete_snippet": register_delete_snippet,
    "delete_file": register_delete_file,
    # Command Runner
    "agent_run_shell_command": register_agent_run_shell_command,
    "agent_share_your_reasoning": register_agent_share_your_reasoning,
    # Skills tools are injected at runtime by the agent_skills plugin via
    # the `register_tools` callback. We keep lightweight placeholders here
    # so legacy callers that enumerate TOOL_REGISTRY still see the names.
    "activate_skill": None,  # registered by agent_skills plugin
    "list_or_search_skills": None,  # registered by agent_skills plugin
}

# Tools that expand into multiple tools for backward compatibility.
# When an agent requests a tool listed here, all the expansion tools
# are registered instead (the original tool is NOT registered).
TOOL_EXPANSIONS: dict[str, list[str]] = {
    "edit_file": ["create_file", "replace_in_file", "delete_snippet"],
}

# Legacy tool names we silently ignore instead of warning about.
# Keep this for truly removed tools only; backward-compatible tool aliases
# that still work should stay in TOOL_REGISTRY.
REMOVED_LEGACY_TOOLS: set[str] = set()


def _load_plugin_tools() -> None:
    """Load tools registered by plugins via the register_tools callback.

    This merges plugin-provided tools into the TOOL_REGISTRY.
    Called lazily when tools are first accessed.
    """
    try:
        results = on_register_tools()
        for result in results:
            if result is None:
                continue
            # Each result should be a list of tool definitions
            tools_list = result if isinstance(result, list) else [result]
            for tool_def in tools_list:
                if (
                    isinstance(tool_def, dict)
                    and "name" in tool_def
                    and "register_func" in tool_def
                ):
                    tool_name = tool_def["name"]
                    register_func = tool_def["register_func"]
                    if callable(register_func):
                        TOOL_REGISTRY[tool_name] = register_func
    except Exception:
        # Don't let plugin failures break core functionality
        pass


# Appended to the system prompt when extended thinking is active and
# the share_your_reasoning tool is removed.  Encourages the model to
# use its native thinking blocks between tool calls instead.
EXTENDED_THINKING_PROMPT_NOTE = (
    "\n\nIMPORTANT: You have extended thinking enabled. "
    "Always think between tool calls or waves of tool calls "
    "(if running parallel tools). Use your thinking blocks to reason "
    "about the results before deciding on next steps."
)


def has_extended_thinking_active(model_name: str | None = None) -> bool:
    """Check if an Anthropic model has extended thinking enabled or adaptive.

    When extended thinking is active, the model already exposes its reasoning
    via thinking blocks, making the share_your_reasoning tool redundant.

    Args:
        model_name: The model name to check. If None, uses the current global model.

    Returns:
        True if the model is an Anthropic model with extended_thinking set to
        "enabled" or "adaptive".
    """
    from code_puppy.config import get_effective_model_settings, get_global_model_name

    if model_name is None:
        model_name = get_global_model_name()

    if model_name is None:
        return False

    # Only applies to Anthropic/Claude models
    if not (model_name.startswith("claude-") or model_name.startswith("anthropic-")):
        return False

    from code_puppy.model_utils import get_default_extended_thinking

    settings = get_effective_model_settings(model_name)
    default_thinking = get_default_extended_thinking(model_name)
    extended_thinking = settings.get("extended_thinking", default_thinking)

    # Handle legacy boolean values
    if extended_thinking is True:
        extended_thinking = "enabled"
    elif extended_thinking is False:
        return False

    return extended_thinking in ("enabled", "adaptive")


def register_tools_for_agent(
    agent,
    tool_names: list[str],
    model_name: str | None = None,
    agent_name: str | None = None,
):
    """Register specific tools for an agent based on tool names.

    Args:
        agent: The agent to register tools to.
        tool_names: List of tool names to register.
        model_name: Optional model name. Used to determine if certain tools
            (like agent_share_your_reasoning) should be skipped. If None,
            falls back to the current global model.
        agent_name: Optional logical agent name (e.g. ``"code-puppy"``).
            Passed to the ``register_agent_tools`` callback so plugins can
            advertise tools per-agent if they want.
    """
    _load_plugin_tools()

    # Plugin-advertised tools get unioned into the requested list. This is
    # the companion to the ``register_tools`` hook that defines them — this
    # one decides which agent gets which. Keeping it here means every
    # ``register_tools_for_agent`` call site benefits without duplication.
    plugin_extras = on_register_agent_tools(agent_name)
    if plugin_extras:
        seen = set(tool_names)
        merged = list(tool_names)
        for extra in plugin_extras:
            if extra not in seen:
                merged.append(extra)
                seen.add(extra)
        tool_names = merged

    # Expand compound tools (e.g. "edit_file" → three individual tools)
    expanded_tools: list[str] = []
    seen: set[str] = set()
    for tool_name in tool_names:
        if tool_name in TOOL_EXPANSIONS:
            for expanded in TOOL_EXPANSIONS[tool_name]:
                if expanded not in seen:
                    expanded_tools.append(expanded)
                    seen.add(expanded)
        else:
            if tool_name not in seen:
                expanded_tools.append(tool_name)
                seen.add(tool_name)
    tool_names = expanded_tools

    for tool_name in tool_names:
        if tool_name in REMOVED_LEGACY_TOOLS:
            continue

        if tool_name not in TOOL_REGISTRY:
            # Skip unknown tools with a warning instead of failing
            emit_warning(f"Warning: Unknown tool '{tool_name}' requested, skipping...")
            continue

        # Register the individual tool
        register_func = TOOL_REGISTRY[tool_name]
        if register_func is None:
            # Tool is injected by a plugin callback (e.g. agent_skills); skip here.
            continue
        register_func(agent)


def register_all_tools(agent, model_name: str | None = None):
    """Register all available tools to the provided agent.

    Args:
        agent: The agent to register tools to.
        model_name: Optional model name for conditional tool filtering.
    """
    all_tools = list(TOOL_REGISTRY.keys())
    register_tools_for_agent(agent, all_tools, model_name=model_name)


def get_available_tool_names() -> list[str]:
    """Get list of all available tool names.

    Returns:
        List of all tool names that can be registered.
    """
    _load_plugin_tools()
    return list(TOOL_REGISTRY.keys())
