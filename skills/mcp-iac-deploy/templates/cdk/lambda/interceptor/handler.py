"""AgentCore Gateway REQUEST interceptor: bind trusted context to tool calls.

For tools/call it:
  1. verifies the bearer token (defence in depth; the Gateway already validated it),
  2. removes any caller-supplied `_trusted_context` and identity-looking fields,
  3. injects `_trusted_context` built only from validated claims.

The adapter reads identity and partition exclusively from `_trusted_context`.
Fails closed: any verification error short-circuits with a JSON-RPC error.
Never log headers or tokens.

Payload contract: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-types.html
"""

import json
import os
import urllib.request

try:
    import jwt  # PyJWT, vendored by CI from requirements.txt
except ImportError:  # pragma: no cover - deployment error, fail closed
    jwt = None

DISCOVERY_URL = os.environ["DISCOVERY_URL"]
AUDIENCE = [a for a in os.environ.get("ALLOWED_AUDIENCE", "").split(",") if a]
PARTITION_CLAIM = os.environ.get("PARTITION_CLAIM", "none")
FORBIDDEN_ARGS = {"_trusted_context", "user_id", "tenant_id", "entity_id", "legal_entity", "sub", "role", "roles"}

_jwks_client = None
_issuer = None


def _jwks():
    global _jwks_client, _issuer
    if _jwks_client is None:
        with urllib.request.urlopen(DISCOVERY_URL, timeout=3) as resp:  # noqa: S310 - fixed https URL
            meta = json.load(resp)
        _issuer = meta["issuer"]
        _jwks_client = jwt.PyJWKClient(meta["jwks_uri"], cache_keys=True)
    return _jwks_client


def _deny(body, message):
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 200,
                "body": {"jsonrpc": "2.0", "id": body.get("id"),
                         "error": {"code": -32001, "message": message}},
            }
        },
    }


def _pass(body):
    return {"interceptorOutputVersion": "1.0", "mcp": {"transformedGatewayRequest": {"body": body}}}


def lambda_handler(event, _context):
    request = event["mcp"]["gatewayRequest"]
    body = request.get("body") or {}
    if body.get("method") != "tools/call":
        return _pass(body)  # tools/list, initialize, ping: Cedar filters discovery

    if jwt is None:
        return _deny(body, "interceptor misconfigured")
    headers = {k.lower(): v for k, v in (request.get("headers") or {}).items()}
    auth = headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return _deny(body, "missing bearer token")
    token = auth.split(" ", 1)[1]
    try:
        key = _jwks().get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=AUDIENCE or None, issuer=_issuer)
    except Exception:  # noqa: BLE001 - any failure is a denial
        return _deny(body, "token verification failed")

    partition = claims.get(PARTITION_CLAIM) if PARTITION_CLAIM != "none" else None
    if PARTITION_CLAIM != "none" and not partition:
        return _deny(body, f"missing {PARTITION_CLAIM} claim")

    params = body.setdefault("params", {})
    args = {k: v for k, v in (params.get("arguments") or {}).items() if k not in FORBIDDEN_ARGS}
    args["_trusted_context"] = {
        "sub": claims.get("sub") or claims.get("oid"),
        "partition": partition,
        "scope": claims.get("scp") or claims.get("scope"),
        "issuer": claims.get("iss"),
        "token_id": claims.get("jti") or claims.get("uti"),
    }
    params["arguments"] = args
    return _pass(body)
