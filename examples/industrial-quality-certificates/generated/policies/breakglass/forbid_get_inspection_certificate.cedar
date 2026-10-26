// BREAK-GLASS - emergency shutdown of get_inspection_certificate. Promote via the fast-track pipeline only.
forbid(
  principal,
  action == AgentCore::Action::"QualityCertificatesTools___get_inspection_certificate",
  resource == AgentCore::Gateway::"${GatewayArn}"
);
