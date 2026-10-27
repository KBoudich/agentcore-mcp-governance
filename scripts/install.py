#!/usr/bin/env python3
"""Install mcp-architect into a repository for any Agent Skills client.

    install.py <repo> [--agents codex,copilot,claude] [--plugin-path PATH] [--monorepo [--ci github|gitlab]]

    --agents        which coding agents to install the skills for (default: codex,copilot)
    --plugin-path   the pack is already in the repo at PATH (e.g. a submodule at
                    vendor/agentcore-mcp-governance): do not vendor a copy, point the skills at PATH
    --monorepo      also lay out a central MCP monorepo: CODEOWNERS, servers/README.md and the
                    CI gate for --ci github (default: workflow, AI review prompt, Copilot
                    instructions) or --ci gitlab (.gitlab-ci.yml). Existing files are kept.

Vendors the plugin under <repo>/tools/mcp-architect/ (scripts, skills, reference)
and copies every skill to the directory each agent scans:

    codex, copilot  ->  <repo>/.agents/skills/<skill>/
    claude          ->  <repo>/.claude/skills/<skill>/

In the copies, `<plugin>` is rewritten to `tools/mcp-architect`, so script paths
resolve from the repository root. Claude Code users can install the plugin from the
marketplace instead and keep the /design-mcp command and reviewer subagent.
"""

from __future__ import annotations

import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VENDOR = os.path.join("tools", "mcp-architect")
VENDORED = ["scripts", "skills", "reference", "README.md"]
SKILL_DIRS = {"codex": ".agents/skills", "copilot": ".agents/skills", "claude": ".claude/skills"}
REWRITE_EXT = (".md", ".yaml", ".yml")
DEFINITION = "`<plugin>` is the mcp-architect root"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def _copy(src: str, dst: str) -> None:
    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def _rewrite_plugin_paths(skill_dir: str, plugin: str) -> None:
    for base, _, files in os.walk(skill_dir):
        for name in files:
            if not name.endswith(REWRITE_EXT):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "<plugin>" not in text:
                continue
            # Drop the line that explains the placeholder; the paths are concrete now.
            lines = [ln for ln in text.splitlines(keepends=True) if not ln.startswith(DEFINITION)]
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("".join(lines).replace("\n\n\n", "\n\n").replace("<plugin>", plugin))


def install(repo: str, agents: list[str], plugin_path: str | None = None, monorepo: bool = False,
            ci: str = "github") -> list[str]:
    unknown = [a for a in agents if a not in SKILL_DIRS]
    if unknown:
        raise ValueError(f"unknown agent(s): {', '.join(unknown)}; choose from {', '.join(SKILL_DIRS)}")
    repo = os.path.abspath(repo)
    plugin = (plugin_path or VENDOR).rstrip("/")
    if plugin_path is None:
        for item in VENDORED:
            _copy(os.path.join(ROOT, item), os.path.join(repo, VENDOR, item))
    written = []
    if monorepo:
        if ci not in ("github", "gitlab"):
            raise ValueError(f"unknown CI: {ci}; choose github or gitlab")
        for template in (os.path.join(ROOT, "templates", "monorepo"), os.path.join(ROOT, "templates", "ci", ci)):
            for base, _, files in os.walk(template):
                for name in files:
                    src = os.path.join(base, name)
                    dst = os.path.join(repo, os.path.relpath(src, template))
                    if not os.path.exists(dst):
                        _copy(src, dst)
                        written.append(os.path.relpath(dst, repo))
    targets = sorted({SKILL_DIRS[a] for a in agents})
    skills = sorted(d for d in os.listdir(os.path.join(ROOT, "skills"))
                    if os.path.isfile(os.path.join(ROOT, "skills", d, "SKILL.md")))
    for target in targets:
        for skill in skills:
            dst = os.path.join(repo, target, skill)
            _copy(os.path.join(ROOT, "skills", skill), dst)
            _rewrite_plugin_paths(dst, plugin)
            written.append(os.path.relpath(dst, repo))
    return written


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__.strip())
        return 2
    agents = ["codex", "copilot"]
    if "--agents" in argv:
        agents = [a.strip() for a in argv[argv.index("--agents") + 1].split(",") if a.strip()]
    plugin_path = argv[argv.index("--plugin-path") + 1] if "--plugin-path" in argv else None
    try:
        ci = argv[argv.index("--ci") + 1] if "--ci" in argv else "github"
        written = install(argv[0], agents, plugin_path=plugin_path, monorepo="--monorepo" in argv, ci=ci)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"skills point at {plugin_path or VENDOR + '/'}; wrote {len(written)} item(s):")
    for path in written:
        print(f"  {path}")
    if "copilot" in agents and "claude" in agents:
        print("note: Copilot also reads .claude/skills, so it will list each skill twice.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
