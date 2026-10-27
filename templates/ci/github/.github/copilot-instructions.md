This repository is the central registry of MCP servers. Each server lives in `servers/<name>/` with an `mcp-spec.yaml`, its governance ADR, Cedar policies and infrastructure.

When reviewing a pull request that changes a server, apply `vendor/agentcore-mcp-governance/skills/mcp-governance-review/SKILL.md` to that server (read `<plugin>` as `vendor/agentcore-mcp-governance`) and flag as blocking:
- identity or partition values taken from tool arguments instead of the validated token context;
- a write without an idempotency key, or a consequential (T3) action without a bound approval;
- partition (entity, plant, business unit, customer) scope enforced only in Cedar and not in the backend query;
- a Cedar permit that is not limited to one tool, or a tool without a break-glass forbid.
