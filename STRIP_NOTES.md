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
- Phase 1: allowlist plugin load (agent_skills + file_permission_handler) — 3acc7e732925d701e8129beec5e6547dc23c7679
- Phase 2: remove unused plugins — f85fc9a02986aa3680e401615014b0beb0002b98

- Phase 3: remove MCP subsystem — On branch strip-to-spine
Changes not staged for commit:
  (use "git add/rm <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   STRIP_NOTES.md
	modified:   code_puppy/agents/_builder.py
	modified:   code_puppy/agents/base_agent.py
	modified:   code_puppy/command_line/agent_menu.py
	modified:   code_puppy/command_line/core_commands.py
	deleted:    code_puppy/command_line/mcp/__init__.py
	deleted:    code_puppy/command_line/mcp/base.py
	deleted:    code_puppy/command_line/mcp/catalog_server_installer.py
	deleted:    code_puppy/command_line/mcp/custom_server_form.py
	deleted:    code_puppy/command_line/mcp/custom_server_installer.py
	deleted:    code_puppy/command_line/mcp/edit_command.py
	deleted:    code_puppy/command_line/mcp/handler.py
	deleted:    code_puppy/command_line/mcp/help_command.py
	deleted:    code_puppy/command_line/mcp/install_command.py
	deleted:    code_puppy/command_line/mcp/install_menu.py
	deleted:    code_puppy/command_line/mcp/list_command.py
	deleted:    code_puppy/command_line/mcp/logs_command.py
	deleted:    code_puppy/command_line/mcp/remove_command.py
	deleted:    code_puppy/command_line/mcp/restart_command.py
	deleted:    code_puppy/command_line/mcp/search_command.py
	deleted:    code_puppy/command_line/mcp/silence_warning_command.py
	deleted:    code_puppy/command_line/mcp/start_all_command.py
	deleted:    code_puppy/command_line/mcp/start_command.py
	deleted:    code_puppy/command_line/mcp/status_command.py
	deleted:    code_puppy/command_line/mcp/stop_all_command.py
	deleted:    code_puppy/command_line/mcp/stop_command.py
	deleted:    code_puppy/command_line/mcp/utils.py
	deleted:    code_puppy/command_line/mcp/wizard_utils.py
	deleted:    code_puppy/command_line/mcp_binding_menu.py
	deleted:    code_puppy/command_line/mcp_completion.py
	deleted:    code_puppy/mcp_/__init__.py
	deleted:    code_puppy/mcp_/agent_bindings.py
	deleted:    code_puppy/mcp_/async_lifecycle.py
	deleted:    code_puppy/mcp_/blocking_startup.py
	deleted:    code_puppy/mcp_/captured_stdio_server.py
	deleted:    code_puppy/mcp_/circuit_breaker.py
	deleted:    code_puppy/mcp_/config_wizard.py
	deleted:    code_puppy/mcp_/dashboard.py
	deleted:    code_puppy/mcp_/error_isolation.py
	deleted:    code_puppy/mcp_/examples/retry_example.py
	deleted:    code_puppy/mcp_/health_monitor.py
	deleted:    code_puppy/mcp_/managed_server.py
	deleted:    code_puppy/mcp_/manager.py
	deleted:    code_puppy/mcp_/mcp_logs.py
	deleted:    code_puppy/mcp_/registry.py
	deleted:    code_puppy/mcp_/retry_manager.py
	deleted:    code_puppy/mcp_/server_registry_catalog.py
	deleted:    code_puppy/mcp_/status_tracker.py
	deleted:    code_puppy/mcp_/system_tools.py
	deleted:    code_puppy/mcp_prompts/__init__.py
	deleted:    code_puppy/mcp_prompts/hook_creator.py
	deleted:    tests/agents/test_base_agent_run_mcp.py
	deleted:    tests/agents/test_builder_autostart_mcp.py
	deleted:    tests/agents/test_json_agent_mcp_servers.py
	deleted:    tests/command_line/mcp/__init__.py
	deleted:    tests/command_line/mcp/test_catalog_server_installer.py
	deleted:    tests/command_line/mcp/test_custom_server_form.py
	deleted:    tests/command_line/mcp/test_custom_server_installer.py
	deleted:    tests/command_line/mcp/test_edit_command.py
	deleted:    tests/command_line/mcp/test_handler.py
	deleted:    tests/command_line/mcp/test_help_command.py
	deleted:    tests/command_line/mcp/test_install_command.py
	deleted:    tests/command_line/mcp/test_install_menu.py
	deleted:    tests/command_line/mcp/test_list_command.py
	deleted:    tests/command_line/mcp/test_logs_command.py
	deleted:    tests/command_line/mcp/test_mcp_utils.py
	deleted:    tests/command_line/mcp/test_remove_command.py
	deleted:    tests/command_line/mcp/test_restart_command.py
	deleted:    tests/command_line/mcp/test_search_command.py
	deleted:    tests/command_line/mcp/test_start_all_command.py
	deleted:    tests/command_line/mcp/test_start_command.py
	deleted:    tests/command_line/mcp/test_status_command.py
	deleted:    tests/command_line/mcp/test_stop_all_command.py
	deleted:    tests/command_line/mcp/test_stop_command.py
	deleted:    tests/command_line/mcp/test_wizard_utils.py
	deleted:    tests/command_line/test_mcp_completion.py
	deleted:    tests/mcp/conftest.py
	deleted:    tests/mcp/test_agent_bindings.py
	deleted:    tests/mcp/test_agent_bindings_json_merge.py
	deleted:    tests/mcp/test_async_lifecycle.py
	deleted:    tests/mcp/test_blocking_startup.py
	deleted:    tests/mcp/test_blocking_startup_coverage.py
	deleted:    tests/mcp/test_captured_stdio_full_coverage.py
	deleted:    tests/mcp/test_captured_stdio_server.py
	deleted:    tests/mcp/test_circuit_breaker_comprehensive.py
	deleted:    tests/mcp/test_circuit_breaker_half_open_race.py
	deleted:    tests/mcp/test_config_wizard.py
	deleted:    tests/mcp/test_dashboard.py
	deleted:    tests/mcp/test_error_isolation.py
	deleted:    tests/mcp/test_health_monitor.py
	deleted:    tests/mcp/test_managed_server.py
	deleted:    tests/mcp/test_managed_server_coverage.py
	deleted:    tests/mcp/test_manager_extended.py
	deleted:    tests/mcp/test_mcp_list_search_commands.py
	deleted:    tests/mcp/test_mcp_logs.py
	deleted:    tests/mcp/test_mcp_start_stop_commands.py
	deleted:    tests/mcp/test_mcp_status_command.py
	deleted:    tests/mcp/test_registry_comprehensive.py
	deleted:    tests/mcp/test_registry_coverage.py
	deleted:    tests/mcp/test_retry_manager.py
	deleted:    tests/mcp/test_server_registry_catalog.py
	deleted:    tests/mcp/test_silence_warning_command.py
	deleted:    tests/mcp/test_status_tracker_full_coverage.py
	deleted:    tests/mcp/test_system_tools.py
	deleted:    tests/test_mcp_init.py

no changes added to commit (use "git add" and/or "git commit -a")

- Phase 7: ruff F-sweep + prune pyproject deps — b567ce301518d9367413691ca503008c34493648

- Phase 8: fix critical runtime breaks (C1-C4) + cleanups (H2,M1) — 51d4ad5f0d82366da23fe9c92f8ccc0a961c8b75


## Final summary
- Baseline `.py` count: 333
- Final `.py` count: 111
- Subsystems removed: plugins ecosystem, MCP (19 files), browser (9 files), extra providers, menus/support (autosave, version_checker, keymap residuals, onboarding/tutorial, wiggum/judges)
- Dependencies dropped: `mcp`, `playwright`, `Pillow`, `azure-identity`, `boto3`, `bedrock` extra, `durable`/dbos extra
- Kept spine: interactive loop (`cli_runner.py`), model factory, file/shell tools, messaging, agent skills plugin (signature feature)
- Independent review: GO — all 4 critical runtime breaks fixed and verified
- Non-blocking follow-ups (optional):
  - Remove dead messaging types `UniversalConstructorMessage` / `VersionCheckMessage` and their renderers
  - Clean agent_creator stale UC system-prompt text
  - `model_factory.py:660` `claude_code` model type has no handler and falls through to `ValueError`

- config.py ensure_config_exists() does interactive input() on first run (pre-existing main behavior); a non-TTY guard would let -p/CI fail cleanly instead of hanging — optional, out of strip scope.

## Phase 2 (brain strip) — Phases 9-13
- Phase 9: CLI menus/completions severance — 744d5d8
- Phase 10: skills marketplace UI removal — 3c2ef61
- Phase 11: orphaned provider/session files removal — 1b40c0e
- Phase 12A: removed agent-creator + diagnostics/error-logging/run-stats (4 files) — 80dba7a. KEPT: sub-agents, json_agent, agent_planning, _non_streaming_render.
- Phase 13: cleanup & hygiene (ruff F-sweep, repo hygiene, dep prune) — <this commit>
- Phase 12B: removed sub-agent delegation (deleted subagent_stream_handler, tools/subagent_context, messaging/subagent_console; severed invoke_agent + is_subagent) — 1e4eff9. Single-agent only now.

### Final `.py` count: 76
- `agents/_runtime.py`: removed `_diagnostics` import; exception path replaced with `emit_error(str(exc), group_id=group_id)`
- `agents/__init__.py`: removed `run_stats` side-effect import
- `config.py`: no change needed — `AgentRunStats` was never referenced outside `__init__.py`

### Load-bearing — do NOT delete
- `claude_cache_client`: Anthropic path still uses `ClaudeCacheAsyncClient` in `model_factory.py`
- `http_utils` + `reopenable_async_client`: model HTTP client construction in `model_factory.py` / `http_utils.py`
- `provider_identity`: used 6x in `model_factory.py` for provider resolution
- `keymap` + `terminal_utils` + `uvx_detection`: cancellation/ctrl-c brain wired through `_runtime`, `cli_runner`, `keymap`
- `json_agent`: agent discovery/load-bearing in `agent_manager.py`

### Final `.py` count: 83