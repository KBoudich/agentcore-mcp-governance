# Cedar patterns for AgentCore Gateway

Entity names follow the AgentCore Policy documentation: principals are `AgentCore::OAuthUser` (JWT inbound; claims are tags) or `AgentCore::IamEntity` (SigV4; `principal.id` is the caller ARN). Actions are `AgentCore::Action::"<TargetName>___<tool>"` for MCP targets. Resources are `AgentCore::Gateway::"<gateway-arn>"`. There are no wildcard actions. Always validate against the schema AgentCore generates from your deployed tools.

`${GatewayArn}` below is substituted by the CDK stack at deploy time.

## Read tool, scope + partition claim present

```cedar
permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"QualityCertificatesTools___get_inspection_certificate",
  resource == AgentCore::Gateway::"${GatewayArn}"
)
when {
  principal.hasTag("scp") &&
  principal.getTag("scp") like "*quality/read*" &&
  principal.hasTag("legal_entity")
};
```

## Write tool with argument limits

```cedar
permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"PurchasingTools___create_po_draft",
  resource == AgentCore::Gateway::"${GatewayArn}"
)
when {
  principal.hasTag("scp") &&
  principal.getTag("scp") like "*purchasing/write*" &&
  context.input.amount > 0 &&
  context.input.amount <= 50000
};
```

## Machine agent (SigV4) restricted to one role

```cedar
permit(
  principal == AgentCore::IamEntity::"arn:aws:sts::111122223333:assumed-role/quality-batch-agent",
  action == AgentCore::Action::"QualityCertificatesTools___list_open_nonconformances",
  resource == AgentCore::Gateway::"${GatewayArn}"
);
```

## Non-negotiable prohibition (forbid wins)

```cedar
forbid(
  principal,
  action == AgentCore::Action::"QualityCertificatesTools___request_quality_hold_release",
  resource == AgentCore::Gateway::"${GatewayArn}"
)
unless {
  principal.hasTag("scp") && principal.getTag("scp") like "*quality/propose*"
};
```

## Break-glass (pre-authored, deployed only in an incident)

```cedar
forbid(
  principal,
  action == AgentCore::Action::"QualityCertificatesTools___create_nonconformance_draft",
  resource == AgentCore::Gateway::"${GatewayArn}"
);
```

## Rollout semantics

| Lever | Values | Use |
| --- | --- | --- |
| Gateway `policyEngineConfiguration.mode` | `LOG_ONLY` \| `ENFORCE` | engine-wide; LOG_ONLY only in dev/stage |
| Policy `enforcementMode` | `ACTIVE` \| `LOG_ONLY` | shadow a new/changed policy in prod without removing protection |
| Policy `validationMode` | `FAIL_ON_ANY_FINDINGS` \| `IGNORE_ALL_FINDINGS` | keep FAIL_ON_ANY_FINDINGS in CI and prod |

## Pitfalls

- `like "*a/read*"` also matches `a/readall` — keep scope names non-overlapping.
- Discovery uses partial context: a tool can be listed and still be denied on call with real arguments. Test both.
- Temporal policies require the client to send `x-amzn-bedrock-agentcore-policy-session-id`; calls without it fail validation when the engine contains a temporal policy.
- Quotas: 1,000 policies per engine, 10 KB per policy, 400 KB Cedar schema per engine, 20 temporal policies.
