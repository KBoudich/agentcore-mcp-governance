#!/usr/bin/env node
import { App } from "aws-cdk-lib";
import * as cfg from "../config/mcp.json";
import { McpGatewayStack, Stage } from "../lib/mcp-gateway-stack";

const app = new App();
const stage = (app.node.tryGetContext("stage") ?? "dev") as Stage;

// Policy engine mode per stage. Production never runs LOG_ONLY at engine level:
// new or changed policies are shadowed individually (shadowPolicies) instead.
const engineMode = stage === "prod" ? "ENFORCE" : (app.node.tryGetContext("engineMode") ?? "LOG_ONLY");
const shadow = (app.node.tryGetContext("shadowPolicies") ?? "")
  .split(",")
  .map((s: string) => s.trim())
  .filter(Boolean);

new McpGatewayStack(app, `mcp-${cfg.name}-${stage}`, {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: cfg.region },
  stage,
  engineMode,
  shadowPolicies: shadow,
  vpcId: app.node.tryGetContext("vpcId"),
});
