---
name: design-mcp
description: Run the full mcp-architect lifecycle for a governed MCP server on AWS (Bedrock AgentCore Gateway) — requirements → governance ADR → tool contracts → Cedar policy → AWS architecture (draw.io) → CDK deployment → operations, with a gate after every stage. Use when someone wants to design, build or govern a new MCP server end to end, or passes an existing mcp-spec.yaml to take through the gates.
---

# Design a governed MCP server (stages 1–7)

`<plugin>` is the mcp-architect root: the plugin directory when installed as a Claude Code plugin, or `tools/mcp-architect/` when vendored into a repository with `scripts/install.py`.

Work through the stages in order. At each stage, use the named skill, produce its artifact, show the user a short summary with open questions, and do not move past a gate that has errors.

1. **mcp-requirements** → `mcp-spec.yaml`; run `<plugin>/scripts/validate_spec.py` (gate G0). If the user gave a path to an existing spec, validate it and continue.
2. **mcp-governance-decision** → `docs/adr-NNNN-<name>-governance.md` via `<plugin>/scripts/decide.py`, then critique and complete it (gate G1).
3. **mcp-tool-design** → refine tools in the spec; re-validate (gate G2).
4. **mcp-security-policy** → threat model notes, generated + hardened Cedar, decision matrix (gate G3).
5. **mcp-aws-architecture** → `docs/architecture.drawio` + `.svg` via `<plugin>/scripts/gen_architecture.py` and `<plugin>/scripts/export_drawio.sh`; cost via `<plugin>/scripts/cost_model.py` (gate G4).
6. **mcp-iac-deploy** → `infra/` via `<plugin>/scripts/scaffold_deploy.py`; typecheck and synth (gate G5).
7. **mcp-operations** → go-live checklist, runbooks, acceptance tests (gate G6).

Keep `mcp-spec.yaml` as the single source of truth: change the spec, then regenerate. Label every statement about AWS behaviour that you have not verified in current AWS documentation as a verification gate.

Finish with an independent review using the **mcp-governance-review** skill, and summarise its verdict. Where the agent can run a separate reviewer (a Claude Code subagent, a fresh Codex or Copilot session), run the review there so the author does not grade their own design.
