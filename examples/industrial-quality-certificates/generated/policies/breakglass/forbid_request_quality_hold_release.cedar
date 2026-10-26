// BREAK-GLASS - emergency shutdown of request_quality_hold_release. Promote via the fast-track pipeline only.
forbid(
  principal,
  action == AgentCore::Action::"QualityCertificatesTools___request_quality_hold_release",
  resource == AgentCore::Gateway::"${GatewayArn}"
);
