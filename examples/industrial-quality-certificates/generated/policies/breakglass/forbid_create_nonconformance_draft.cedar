// BREAK-GLASS - emergency shutdown of create_nonconformance_draft. Promote via the fast-track pipeline only.
forbid(
  principal,
  action == AgentCore::Action::"QualityCertificatesTools___create_nonconformance_draft",
  resource == AgentCore::Gateway::"${GatewayArn}"
);
