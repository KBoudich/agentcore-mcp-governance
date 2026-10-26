// BREAK-GLASS - emergency shutdown of list_open_nonconformances. Promote via the fast-track pipeline only.
forbid(
  principal,
  action == AgentCore::Action::"QualityCertificatesTools___list_open_nonconformances",
  resource == AgentCore::Gateway::"${GatewayArn}"
);
