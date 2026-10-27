#!/usr/bin/env python3
"""Check every MCP server in a central monorepo and build its catalogue.

    check_repo.py [--root servers] [--base REF] [--catalog CATALOG.md | --check-catalog CATALOG.md]
                  [--summary FILE]

A server is any directory under --root that holds an mcp-spec.yaml (or .json).
For each server, the checks are the deterministic part of the gates:

  G0–G2  validate_spec.py rules (tiers, identity inputs, idempotency, approvals, Regions)
  G1     a governance ADR (adr-*.md) exists next to the spec
  G3     one permit and one break-glass forbid per tool, no permit for an unknown
         tool, no permit that covers every action, a decision matrix exists
  repo   server names are unique (they become gateway target names)

Missing artefacts are warnings while a server is `draft` and errors from `pilot` on.
With --base, only servers whose files changed since REF are checked; a change to the
governance tooling itself (scripts/, skills/, reference/, vendor/) checks every server.
The catalogue always lists every server, so the repository stays the single place
that shows what MCP servers exist, who owns them and how risky their tools are.
Exit code 1 if any server has errors, or if --check-catalog finds a stale catalogue.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys

from decide import max_tier
from spec_io import load_spec
from validate_spec import validate

SPEC_NAMES = ("mcp-spec.yaml", "mcp-spec.yml", "mcp-spec.json")
TOOLING_PATHS = ("scripts/", "skills/", "reference/", "vendor/", ".github/")
POLICY_DIRS = ("infra/policies", "generated/policies", "policies")
MATRIX_PATHS = ("infra/tests/decision-matrix.md", "generated/tests/decision-matrix.md", "tests/decision-matrix.md")
# A permit whose action slot is a bare `action` applies to every tool behind the gateway.
BROAD_PERMIT = re.compile(r"permit\s*\(\s*principal[^,]*,\s*action\s*,", re.S)
ACTION_REF = re.compile(r'Action::"[^"]*___([A-Za-z0-9_]+)"')


def find_servers(root: str) -> list[str]:
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in ("node_modules", "cdk.out", ".git"))
        if any(n in files for n in SPEC_NAMES):
            found.append(base)
            dirs[:] = []  # a server's own subfolders are not servers
    return sorted(found)


def spec_path(server: str) -> str:
    return next(os.path.join(server, n) for n in SPEC_NAMES if os.path.exists(os.path.join(server, n)))


def changed_files(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                         capture_output=True, text=True, check=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def check_policies(server: str, tools: list[str]) -> tuple[list[str], list[str]]:
    """Return (errors, missing) for the Cedar artefacts of one server."""
    pol_dir = next((os.path.join(server, d) for d in POLICY_DIRS if os.path.isdir(os.path.join(server, d))), None)
    if pol_dir is None:
        return [], ["no Cedar policies (run scaffold_deploy.py)"]
    errors, missing = [], []
    permitted = set()
    for path in sorted(glob.glob(os.path.join(pol_dir, "*.cedar"))):
        text = open(path, encoding="utf-8").read()
        rel = os.path.relpath(path, server)
        if BROAD_PERMIT.search(text):
            errors.append(f"G3 {rel}: permit covers every action; scope it to one tool")
        for tool in ACTION_REF.findall(text):
            if "permit" in text:
                permitted.add(tool)
            if tool not in tools:
                errors.append(f"G3 {rel}: policy for unknown tool '{tool}' (removed or renamed in the spec?)")
    forbidden = {os.path.basename(p)[len("forbid_"):-len(".cedar")]
                 for p in glob.glob(os.path.join(pol_dir, "breakglass", "forbid_*.cedar"))}
    for tool in tools:
        if tool not in permitted:
            missing.append(f"no permit for tool '{tool}'")
        if tool not in forbidden:
            missing.append(f"no break-glass forbid for tool '{tool}'")
    if not any(os.path.exists(os.path.join(server, m)) for m in MATRIX_PATHS):
        missing.append("no decision matrix (tests/decision-matrix.md)")
    return errors, missing


def check_server(server: str) -> dict:
    spec = load_spec(spec_path(server))
    mcp = spec.get("mcp") or {}
    errors, warnings = validate(spec)
    lambda_tools = [t.get("name", "") for t in spec.get("tools") or [] if t.get("target_type", "lambda") == "lambda"]
    pol_errors, missing = check_policies(server, lambda_tools)
    errors += pol_errors
    if not glob.glob(os.path.join(server, "**", "adr-*.md"), recursive=True):
        missing.append("no governance ADR (adr-*.md; run decide.py)")
    status = mcp.get("status", "draft")
    if status == "draft":
        warnings += [f"draft: {m}" for m in missing]
    else:
        errors += [f"{status}: {m}" for m in missing]
    tools = spec.get("tools") or []
    return {
        "path": server, "name": mcp.get("name", "?"), "domain": mcp.get("domain", "?"),
        "status": status, "business_owner": mcp.get("business_owner", ""),
        "technical_owner": mcp.get("technical_owner", ""), "max_tier": max_tier(spec),
        "systems": sorted({s.get("name", "") for s in spec.get("systems_of_record") or []}),
        "region": (spec.get("context") or {}).get("primary_region", ""),
        "partition": (spec.get("context") or {}).get("partition_dimension", "none"),
        "tools": [{"name": t.get("name", ""), "tier": t.get("tier", ""), "side_effect": t.get("side_effect", ""),
                   "approval": t.get("approval", "none"), "system": t.get("system_of_record", "")} for t in tools],
        "errors": errors, "warnings": warnings,
    }


def cross_checks(results: list[dict]) -> None:
    seen: dict[str, str] = {}
    for r in results:
        if r["name"] in seen:
            r["errors"].append(f"repo: server name '{r['name']}' also used by {seen[r['name']]}")
        seen.setdefault(r["name"], r["path"])


def catalogue(results: list[dict], root: str) -> str:
    lines = [
        "# MCP server catalogue", "",
        f"Generated by `check_repo.py` from every `mcp-spec.yaml` under `{root}/`. Do not edit by hand.", "",
        f"{len(results)} server(s), {sum(len(r['tools']) for r in results)} tool(s).", "",
        "| Server | Domain | Status | Highest tier | Owners (business / technical) | Systems | Partition | Region | Checks |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        check = "❌ " + str(len(r["errors"])) if r["errors"] else "✅"
        lines.append(f"| [{r['name']}]({r['path']}/) | {r['domain']} | {r['status']} | {r['max_tier']} | "
                     f"{r['business_owner'] or '—'} / {r['technical_owner'] or '—'} | {', '.join(r['systems']) or '—'} | "
                     f"{r['partition']} | {r['region'] or '—'} | {check} |")
    lines += ["", "## Tools", "", "| Tool | Server | Tier | Side effect | Approval | System of record |",
              "| --- | --- | --- | --- | --- | --- |"]
    for r in results:
        for t in r["tools"]:
            lines.append(f"| `{t['name']}` | {r['name']} | {t['tier']} | {t['side_effect']} | {t['approval']} | {t['system'] or '—'} |")
    return "\n".join(lines) + "\n"


def report(checked: list[dict]) -> str:
    if not checked:
        return "## MCP governance checks\n\nNo MCP server changed.\n"
    lines = ["## MCP governance checks", ""]
    for r in checked:
        mark = "❌" if r["errors"] else "✅"
        lines.append(f"### {mark} {r['name']} ({r['path']}) — {r['status']}, highest tier {r['max_tier']}")
        lines += [f"- ERROR {e}" for e in r["errors"]] + [f"- VERIFY {w}" for w in r["warnings"]]
        if not r["errors"] and not r["warnings"]:
            lines.append("- all checks pass")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="servers")
    ap.add_argument("--base", help="git ref; check only servers changed since it")
    ap.add_argument("--catalog", help="write the catalogue to this file")
    ap.add_argument("--check-catalog", help="fail if this committed catalogue is out of date")
    ap.add_argument("--summary", help="append the Markdown report to this file (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args(argv)

    servers = find_servers(a.root)
    results = [check_server(s) for s in servers]
    cross_checks(results)

    checked = results
    if a.base:
        changed = changed_files(a.base)
        if not any(f.startswith(TOOLING_PATHS) for f in changed):
            checked = [r for r in results if any(f.startswith(r["path"].rstrip("/") + "/") for f in changed)]

    text = report(checked)
    print(text)
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")

    failed = any(r["errors"] for r in checked)
    cat = catalogue(results, a.root)
    if a.catalog:
        with open(a.catalog, "w", encoding="utf-8") as fh:
            fh.write(cat)
    if a.check_catalog:
        current = open(a.check_catalog, encoding="utf-8").read() if os.path.exists(a.check_catalog) else ""
        if current != cat:
            print(f"ERROR {a.check_catalog} is out of date: run check_repo.py --catalog {a.check_catalog} and commit it")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
