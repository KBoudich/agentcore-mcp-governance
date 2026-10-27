# MCP servers

One directory per MCP server: `servers/<name>/`. Whatever the system behind it (ERP, LIMS, MES, PLM, CRM, ITSM, a data platform or a SaaS API), every server follows the same layout:

```
servers/<name>/
  mcp-spec.yaml          single source of truth (owners, consumers, systems, tools, tiers)
  adr-0001-<name>.md     governance decision (decide.py), accepted by the Design Authority
  infra/                 scaffold_deploy.py output, hardened by the team: policies/, config/, lambda/, lib/, tests/
```

To add a server, ask your coding agent to run the `design-mcp` skill, or run the scripts in `vendor/agentcore-mcp-governance/scripts/` yourself. Add a CODEOWNERS line for the directory, regenerate the catalogue (`check_repo.py --catalog CATALOG.md`) and open a pull request. CI checks every changed server and fails on governance errors.
