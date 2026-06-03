# agent_tools.py
import asyncio
from typing import List, Set

from pydantic import BaseModel
from pydantic_ai import RunContext

from code_puppy.messaging import emit_error, emit_info

from code_puppy.tools.common import generate_group_id

# Always empty after Phase 12B (nothing adds to it now that invoke_agent is gone).
# Still imported by code_puppy/agents/_run_signals.py for the Ctrl+C subagent-cancel
# path, which is now a no-op. Safe to remove only together with that import.
_active_subagent_tasks: Set[asyncio.Task] = set()


class AgentInfo(BaseModel):
    """Information about an available agent."""

    name: str
    display_name: str
    description: str


class ListAgentsOutput(BaseModel):
    """Output for the list_agents tool."""

    agents: List[AgentInfo]
    error: str | None = None


def register_list_agents(agent):
    """Register the list_agents tool with the provided agent."""

    @agent.tool
    def list_agents(context: RunContext) -> ListAgentsOutput:
        """List all available sub-agents that can be invoked."""
        group_id = generate_group_id("list_agents")
        from rich.text import Text
        from code_puppy.config import get_banner_color

        list_agents_color = get_banner_color("list_agents")
        try:
            from code_puppy.agents import get_agent_descriptions, get_available_agents

            agents_dict = get_available_agents()
            descriptions_dict = get_agent_descriptions()
            agents = [
                AgentInfo(
                    name=name,
                    display_name=display_name,
                    description=descriptions_dict.get(name, "No description available"),
                )
                for name, display_name in agents_dict.items()
            ]
            agent_count = len(agents)
            emit_info(
                Text.from_markup(
                    f"[bold white on {list_agents_color}] LIST AGENTS [/bold white on {list_agents_color}] "
                    f"[dim]Found {agent_count} agent(s).[/dim]"
                ),
                message_group=group_id,
            )
            return ListAgentsOutput(agents=agents)
        except Exception as e:
            error_msg = f"Error listing agents: {str(e)}"
            emit_error(error_msg, message_group=group_id)
            return ListAgentsOutput(agents=[], error=error_msg)

    return list_agents


# NOTE: register_invoke_agent removed — sub-agent delegation removed (Phase 12B).
# The invoke_agent tool no longer exists.
