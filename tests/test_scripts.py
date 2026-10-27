"""Regression tests for the mcp-architect scripts.

    python3 -m unittest discover -s plugins/mcp-architect/tests
"""

import contextlib
import copy
import io
import shutil
import subprocess
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import decide  # noqa: E402
import check_repo  # noqa: E402
import gen_architecture  # noqa: E402
import install  # noqa: E402
import scaffold_deploy  # noqa: E402
from spec_io import load_spec  # noqa: E402
from validate_spec import validate  # noqa: E402

EXAMPLE = os.path.join(ROOT, "examples", "industrial-quality-certificates", "mcp-spec.yaml")


class ValidateSpecTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)

    def errors(self, spec):
        return validate(spec)[0]

    def test_example_is_clean(self):
        self.assertEqual(self.errors(self.spec), [])

    def test_generic_verb_rejected(self):
        self.spec["tools"][0]["name"] = "run_sql"
        self.assertTrue(any("generic capability verb" in e for e in self.errors(self.spec)))

    def test_identity_input_rejected(self):
        self.spec["tools"][0]["inputs"].append({"name": "entity_id", "type": "string", "constraints": "x"})
        self.assertTrue(any("entity_id" in e for e in self.errors(self.spec)))

    def test_consequential_needs_t3_and_approval(self):
        tool = self.spec["tools"][3]
        tool["tier"] = "T2"
        tool["approval"] = "none"
        errs = self.errors(self.spec)
        self.assertTrue(any("requires tier >= T3" in e for e in errs))

    def test_write_needs_idempotency(self):
        tool = self.spec["tools"][2]
        tool["idempotency"] = "none"
        tool["inputs"] = [i for i in tool["inputs"] if i["name"] != "idempotency_key"]
        errs = self.errors(self.spec)
        self.assertEqual(len([e for e in errs if "idempotency" in e]), 2)

    def test_region_without_policy_rejected(self):
        self.spec["context"]["primary_region"] = "eu-west-3"
        self.assertTrue(any("without AgentCore Policy" in e for e in self.errors(self.spec)))

    def test_private_system_via_api_gateway_rejected(self):
        self.spec["tools"][0]["target_type"] = "api_gateway"
        self.assertTrue(any("cannot reach private systems" in e for e in self.errors(self.spec)))

    def test_sensitive_t0_rejected(self):
        self.spec["tools"][0]["tier"] = "T0"
        self.assertTrue(any("cannot be T0" in e for e in self.errors(self.spec)))


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)

    def test_example_selects_agentcore_partitioned(self):
        d = decide.decide(self.spec)
        self.assertEqual(d["plane"], "AgentCore Gateway")
        self.assertTrue(d["partition"].startswith("Partitioned"))
        self.assertEqual(d["inbound"], "CUSTOM_JWT")
        self.assertEqual(d["max_tier"], "T3")

    def test_portability_knockout(self):
        self.spec["context"]["portability_required"] = True
        self.assertEqual(decide.decide(self.spec)["plane"], "Self-managed MCP gateway")

    def test_small_t0_server_goes_direct(self):
        s = copy.deepcopy(self.spec)
        s["consumers"] = s["consumers"][:1]
        s["context"]["other_mcp_servers_on_platform"] = 1
        s["tools"] = [dict(s["tools"][0], tier="T0", data_classes=["public"])]
        self.assertEqual(decide.decide(s)["plane"], "Direct MCP (no gateway)")

    def test_single_consumer_single_tool_is_not_mcp(self):
        s = copy.deepcopy(self.spec)
        s["consumers"] = s["consumers"][:1]
        s["context"]["other_mcp_servers_on_platform"] = 0
        s["tools"] = s["tools"][:1]
        self.assertEqual(decide.decide(s)["plane"], "App-managed endpoints (no MCP)")

    def test_markdown_renders(self):
        md = decide.to_markdown(self.spec, decide.decide(self.spec))
        self.assertIn("## Open verification gates", md)


class GeneratorsTest(unittest.TestCase):
    def test_scaffold_writes_policies_and_schemas(self):
        spec = load_spec(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "infra")
            sys.argv = ["scaffold_deploy.py", EXAMPLE, "-o", out]
            self.assertEqual(scaffold_deploy.main(), 0)
            for t in spec["tools"]:
                with open(os.path.join(out, "policies", f"{t['name']}.cedar")) as fh:
                    cedar = fh.read()
                self.assertIn(f'"QualityCertificatesTools___{t["name"]}"', cedar)
                self.assertIn("${GatewayArn}", cedar)
                self.assertIn('getTag("scp")', cedar)
                self.assertTrue(os.path.exists(os.path.join(out, "policies", "breakglass", f"forbid_{t['name']}.cedar")))
            self.assertTrue(os.path.exists(os.path.join(out, "lib", "mcp-gateway-stack.ts")))

    def test_architecture_diagram_has_unique_ids(self):
        d = gen_architecture.build(load_spec(EXAMPLE))
        self.assertGreater(len(d.cells), 20)
        self.assertEqual(len(d.ids), len(set(d.ids)))


class InstallTest(unittest.TestCase):
    def test_installs_portable_skills_for_codex_and_copilot(self):
        with tempfile.TemporaryDirectory() as repo:
            written = install.install(repo, ["codex", "copilot"])
            self.assertIn(os.path.join(".agents", "skills", "design-mcp"), written)
            self.assertFalse(os.path.exists(os.path.join(repo, ".claude")))
            vendored = os.path.join(repo, "tools", "mcp-architect")
            self.assertTrue(os.path.exists(os.path.join(vendored, "scripts", "validate_spec.py")))
            self.assertTrue(os.path.exists(os.path.join(vendored, "reference", "agentcore-facts.json")))
            for skill in os.listdir(os.path.join(repo, ".agents", "skills")):
                with open(os.path.join(repo, ".agents", "skills", skill, "SKILL.md")) as fh:
                    text = fh.read()
                self.assertTrue(text.startswith(f"---\nname: {skill}\n"), skill)
                self.assertNotIn("<plugin>", text, skill)
            with open(os.path.join(repo, ".agents", "skills", "mcp-requirements", "SKILL.md")) as fh:
                self.assertIn("python3 tools/mcp-architect/scripts/validate_spec.py", fh.read())

    def test_claude_target_and_unknown_agent(self):
        with tempfile.TemporaryDirectory() as repo:
            install.install(repo, ["claude"])
            self.assertTrue(os.path.exists(os.path.join(repo, ".claude", "skills", "mcp-governance-review", "SKILL.md")))
            with self.assertRaises(ValueError):
                install.install(repo, ["cursor"])

    def test_monorepo_with_submodule_path(self):
        with tempfile.TemporaryDirectory() as repo:
            written = install.install(repo, ["codex"], plugin_path="vendor/agentcore-mcp-governance", monorepo=True)
            self.assertFalse(os.path.exists(os.path.join(repo, "tools")))
            for f in (".github/workflows/mcp-governance.yml", ".github/mcp-review-prompt.md", "CODEOWNERS", "servers/README.md"):
                self.assertIn(f, written)
            with open(os.path.join(repo, ".agents", "skills", "mcp-repo-compliance", "SKILL.md")) as fh:
                self.assertIn("python3 vendor/agentcore-mcp-governance/scripts/check_repo.py", fh.read())
            open(os.path.join(repo, "CODEOWNERS"), "w").write("mine\n")
            install.install(repo, ["codex"], plugin_path="vendor/agentcore-mcp-governance", monorepo=True)
            self.assertEqual(open(os.path.join(repo, "CODEOWNERS")).read(), "mine\n")


class CheckRepoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "servers")
        self.server = os.path.join(self.root, "quality-certificates")
        shutil.copytree(os.path.dirname(EXAMPLE), self.server)

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, *args):
        return check_repo.main(["--root", self.root, *args])

    def errors(self):
        return check_repo.check_server(self.server)["errors"]

    def set_status(self, status):
        path = os.path.join(self.server, "mcp-spec.yaml")
        text = open(path).read().replace("status: draft", f"status: {status}")
        open(path, "w").write(text)

    def test_example_passes_and_catalogue_lists_every_tool(self):
        cat = os.path.join(self.tmp.name, "CATALOG.md")
        self.assertEqual(self.run_check("--catalog", cat), 0)
        text = open(cat).read()
        for tool in ("get_inspection_certificate", "request_quality_hold_release"):
            self.assertIn(tool, text)
        self.assertEqual(self.run_check("--check-catalog", cat), 0)

    def test_stale_catalogue_fails(self):
        cat = os.path.join(self.tmp.name, "CATALOG.md")
        open(cat, "w").write("old")
        self.assertEqual(self.run_check("--check-catalog", cat), 1)

    def test_broad_permit_rejected(self):
        pol = os.path.join(self.server, "generated", "policies", "get_inspection_certificate.cedar")
        open(pol, "w").write("permit(principal, action, resource);\n")
        self.assertTrue(any("covers every action" in e for e in self.errors()))

    def test_policy_for_unknown_tool_rejected(self):
        src = os.path.join(self.server, "generated", "policies", "get_inspection_certificate.cedar")
        dst = os.path.join(self.server, "generated", "policies", "old_tool.cedar")
        open(dst, "w").write(open(src).read().replace("___get_inspection_certificate", "___old_tool"))
        self.assertTrue(any("unknown tool 'old_tool'" in e for e in self.errors()))

    def test_missing_breakglass_is_warning_in_draft_and_error_in_pilot(self):
        os.remove(os.path.join(self.server, "generated", "policies", "breakglass", "forbid_get_inspection_certificate.cedar"))
        self.assertEqual(self.errors(), [])
        self.set_status("pilot")
        self.assertTrue(any("break-glass" in e for e in self.errors()))

    def test_duplicate_server_names_rejected(self):
        shutil.copytree(self.server, os.path.join(self.root, "copy"))
        results = [check_repo.check_server(s) for s in check_repo.find_servers(self.root)]
        check_repo.cross_checks(results)
        self.assertTrue(any("also used by" in e for r in results for e in r["errors"]))

    def test_base_ref_checks_only_changed_servers(self):
        git = lambda *a: subprocess.run(["git", "-C", self.tmp.name, *a], check=True, capture_output=True)
        shutil.copytree(self.server, os.path.join(self.root, "other"))
        path = os.path.join(self.root, "other", "mcp-spec.yaml")
        text = open(path).read().replace("name: quality-certificates", "name: other-server", 1)
        open(path, "w").write(text)
        git("init", "-q", "-b", "main"); git("add", "-A")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        with open(path, "a") as fh:
            fh.write("\n")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "change")
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                check_repo.main(["--root", "servers", "--base", "HEAD~1"])
        finally:
            os.chdir(cwd)
        self.assertIn("other-server", out.getvalue())
        self.assertNotIn("(servers/quality-certificates)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
