# Strip Code Puppy to Its Spine — Notes

Branch: `strip-to-spine`. Goal: minimal still-runnable fork (interactive loop -> model -> file/shell tools -> final answer), keeping the `agent_skills` signature feature. Disable-at-chokepoint, then delete, verify after every batch, one subsystem per phase, commit each green phase.

## Verification gates (run after every phase)
- Import: `python -c "import code_puppy.cli_runner"` (exit 0)
- Smoke: launch `python -m code_puppy -i`; prompt "list the files in the current directory, read README.md, and tell me in one sentence what this project is." -> must call list_files, read_file, loop, render a final answer.
- Tripwire: `pytest -q` at phase boundaries (deleted-subsystem tests fail/are removed with their subsystem; kept-code tests stay green).

## Verified coupling map (HEAD)
| Subsystem | Chokepoint to disable | Spine files needing import surgery |
|---|---|---|
| Plugins (~40 dirs) | `plugins/__init__.py::_load_builtin_plugins` -> allowlist | `tools/__init__.py`, `tools/common.py`, `tools/file_modifications.py`, `model_factory.py` |
| MCP (19 files) | `agents/_builder.py::load_mcp_servers` -> `[]` | `_builder.py`, `agents/base_agent.py`, `tools/agent_tools.py` |
| Browser (9 files) | `tools/__init__.py` registration | `tools/__init__.py` |
| Extra providers | `model_factory.py` registration | `model_factory.py` |
| CLI menus / support | n/a (delete leaves) | `cli_runner.py` (onboarding/autosave/keymap/terminal_utils/version_checker/session_storage import-time deps) |

## CRITICAL findings (do not break these)
1. **`file_permission_handler` is load-bearing**: `tools/file_modifications.py` (lines 51, 180) and `tools/common.py` (lines 1173, 1370) hard-import `from code_puppy.plugins.file_permission_handler.register_callbacks import (...)`. KEEP it in the Phase 1 allowlist (or inline its helpers). DO NOT delete it as a plugin.
2. **`tools/ask_user_question/handler.py:12`** imports `plugins.wiggum.state` -> dropping `ask_user_question` (Phase 4) severs the `wiggum` coupling cleanly.
3. **`model_factory.py` hard-imports provider clients** at module scope: `gemini_model` (L22), `claude_cache_client` (L26), `provider_identity` (L29), `round_robin_model` (L34). Must edit model_factory before deleting these (Phase 5). Verify `claude_cache_client` is not on the Anthropic path before deleting it.
4. **`cli_runner.py` import-time deps**: `keymap`, `terminal_utils`, `version_checker`, `session_storage`, autosave fns from `config` — delete these support files only AFTER Phase 6 slims cli_runner.
5. **Extra agent personas** (`agent_helios`->UC, `agent_qa_kitten`->browser) couple to deleted tools — delete with their tools in Phase 4. Keep `agent_code_puppy`, `agent_manager`, `json_agent` infra.
6. **`callbacks.py` stays** — load-bearing hook bus, called by `_builder`, `_runtime`, `base_agent`, `tools/__init__`, `agent_code_puppy`. Removing it is a rewrite (out of scope).

## Allowlist for Phase 1 plugin load
`agent_skills`, `file_permission_handler` (mandatory — see finding #1).

## pyproject deps to prune in Phase 7
Narrow `pydantic-ai-slim[openai,anthropic,mcp]` -> `[openai,anthropic]`; drop `playwright`, `Pillow`, `azure-identity`, `boto3`, `mcp`; drop `bedrock` + `durable` extras.

## Phase log (append a line per phase with the commit SHA)
- Phase 0: baseline + coupling map — b85da4388cf6954573cd1ccbfca223cd76279b64
