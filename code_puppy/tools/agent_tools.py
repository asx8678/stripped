# agent_tools.py
import asyncio
import hashlib
import json
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import List, Set

from pydantic import BaseModel
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage

from code_puppy.config import DATA_DIR

from code_puppy.messaging import emit_error, emit_info

from code_puppy.tools.common import atomic_write_text, generate_group_id

# Always empty after Phase 12B (nothing adds to it now that invoke_agent is gone).
# Still imported by code_puppy/agents/_run_signals.py for the Ctrl+C subagent-cancel
# path, which is now a no-op. Safe to remove only together with that import.
_active_subagent_tasks: Set[asyncio.Task] = set()


def _generate_session_hash_suffix() -> str:
    """Generate a short SHA1 hash suffix based on current timestamp for uniqueness."""
    timestamp = str(datetime.now().timestamp())
    return hashlib.sha1(timestamp.encode()).hexdigest()[:6]


def _sanitize_for_session_id(value: str) -> str:
    """Coerce an arbitrary string into kebab-case suitable for a session_id."""
    lowered = value.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-")


SESSION_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SESSION_ID_MAX_LENGTH = 128


def _validate_session_id(session_id: str) -> None:
    """Validate that a session ID follows kebab-case naming conventions."""
    if not session_id:
        raise ValueError("session_id cannot be empty")
    if len(session_id) > SESSION_ID_MAX_LENGTH:
        raise ValueError(
            f"Invalid session_id '{session_id}': must be {SESSION_ID_MAX_LENGTH} characters or less"
        )
    if not SESSION_ID_PATTERN.match(session_id):
        raise ValueError(
            f"Invalid session_id '{session_id}': must be kebab-case "
            "(lowercase letters, numbers, and hyphens only). "
            "Examples: 'my-session', 'agent-session-1', 'discussion-about-code'"
        )


def _get_subagent_sessions_dir() -> Path:
    """Get the directory for storing subagent session data."""
    sessions_dir = Path(DATA_DIR) / "subagent_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return sessions_dir


def _save_session_history(
    session_id: str,
    message_history: List[ModelMessage],
    agent_name: str,
    initial_prompt: str | None = None,
) -> None:
    """Save session history to filesystem."""
    _validate_session_id(session_id)
    sessions_dir = _get_subagent_sessions_dir()
    pkl_path = sessions_dir / f"{session_id}.pkl"
    tmp_pkl = pkl_path.with_suffix(".tmp")
    with open(tmp_pkl, "wb") as f:
        pickle.dump(message_history, f)
    tmp_pkl.replace(pkl_path)

    txt_path = sessions_dir / f"{session_id}.txt"
    if not txt_path.exists() and initial_prompt:
        metadata = {
            "session_id": session_id,
            "agent_name": agent_name,
            "initial_prompt": initial_prompt,
            "created_at": datetime.now().isoformat(),
            "message_count": len(message_history),
        }
        atomic_write_text(str(txt_path), json.dumps(metadata, indent=2))
    elif txt_path.exists():
        try:
            with open(txt_path, "r") as f:
                metadata = json.load(f)
            metadata["message_count"] = len(message_history)
            metadata["last_updated"] = datetime.now().isoformat()
            atomic_write_text(str(txt_path), json.dumps(metadata, indent=2))
        except Exception:
            pass


def _load_session_history(session_id: str) -> List[ModelMessage]:
    """Load session history from filesystem."""
    _validate_session_id(session_id)
    sessions_dir = _get_subagent_sessions_dir()
    pkl_path = sessions_dir / f"{session_id}.pkl"
    if not pkl_path.exists():
        return []
    try:
        with open(pkl_path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return []


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
