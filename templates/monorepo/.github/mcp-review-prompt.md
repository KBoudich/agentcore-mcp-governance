You are reviewing a pull request in the central MCP monorepo. Your review is advisory: the deterministic `checks` job is the gate, and it has already passed.

1. `changed-servers.txt` lists the server directories this pull request touches. If it is empty, reply only "No MCP server changed." and stop.
2. For each listed directory, follow `vendor/agentcore-mcp-governance/skills/mcp-governance-review/SKILL.md`, reading `<plugin>` as `vendor/agentcore-mcp-governance`. Review the whole server directory, with extra attention to what changed: `review-diff.patch` holds this pull request's diff under `servers/`.
3. Do not modify any file in the repository.
4. Produce one Markdown review: a heading per server with its verdict (GO, CONDITIONAL or NO-GO), blocking findings with file and line, open verification gates, and at most three non-blocking suggestions. Start the review with "MCP governance review (AI, advisory)".
