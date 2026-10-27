---
name: mcp-repo-compliance
description: Check the MCP servers in a central monorepo against the governance gates before committing, fix what fails, and keep the server catalogue current. Use when changing anything under servers/, before opening a pull request in the MCP monorepo, when CI's mcp-governance check fails, or when asked which MCP servers exist and who owns them.
---

# MCP repository compliance

`<plugin>` is the mcp-architect root: the plugin directory in Claude Code, or `tools/mcp-architect/` when vendored with `scripts/install.py`. In a monorepo that pins the pack as a submodule, it is `vendor/agentcore-mcp-governance`.

1. Run `python3 <plugin>/scripts/check_repo.py --root servers --base origin/main` from the repository root. It checks only servers changed since `main` (all of them if the governance tooling changed).
2. Fix every `ERROR` at its source: change `mcp-spec.yaml` first, then regenerate (`decide.py` for the ADR, `scaffold_deploy.py` for policies) and re-apply any hand hardening. Never delete a break-glass forbid or widen a permit to make a check pass.
3. List every `VERIFY` item in the pull request description as an open question.
4. Regenerate the catalogue: `python3 <plugin>/scripts/check_repo.py --root servers --catalog CATALOG.md`, and commit it with the change.
5. To answer "which servers exist / who owns X / which tools are T3", read `CATALOG.md`.
