#!/usr/bin/env python3
"""Post-deploy smoke test for an AgentCore Gateway MCP endpoint.

    TOKEN_ALLOWED=... TOKEN_DENIED=... smoke.py outputs.json

Asserts: initialize works; tools/list differs between an allowed and a denied
principal (discovery filtering); a denied tools/call is rejected. Tokens come
from short-lived test identities in the IdP, never from a real user.
"""

import json
import os
import sys
import urllib.request


def rpc(url, token, method, params=None, rid=1):
    body = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - gateway URL from stack outputs
        raw = resp.read().decode()
    if raw.startswith("event:") or "\ndata:" in raw or raw.startswith("data:"):
        raw = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")][-1]
    return json.loads(raw)


def main():
    outputs = json.load(open(sys.argv[1]))
    stack = next(iter(outputs.values()))
    url = stack["GatewayUrl"]
    allowed, denied = os.environ["TOKEN_ALLOWED"], os.environ["TOKEN_DENIED"]

    init = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}}
    assert "result" in rpc(url, allowed, "initialize", init), "initialize failed"

    tools_a = {t["name"] for t in rpc(url, allowed, "tools/list")["result"]["tools"]}
    tools_d = {t["name"] for t in rpc(url, denied, "tools/list")["result"].get("tools", [])}
    assert tools_a, "allowed principal sees no tools"
    assert tools_d < tools_a, f"discovery not filtered: denied sees {sorted(tools_d - tools_a) or sorted(tools_d)}"

    hidden = sorted(tools_a - tools_d)[0]
    res = rpc(url, denied, "tools/call", {"name": hidden, "arguments": {}})
    result = res.get("result", {})
    assert res.get("error") or result.get("isError"), f"denied principal could call {hidden}"
    print(f"smoke OK: {len(tools_a)} tools visible to allowed, {len(tools_d)} to denied; {hidden} call denied")


if __name__ == "__main__":
    main()
