import * as fs from "fs";
import * as path from "path";
import { CfnOutput, Duration, Fn, RemovalPolicy, Stack, StackProps, Tags } from "aws-cdk-lib";
import * as agentcore from "aws-cdk-lib/aws-bedrockagentcore";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";
import * as cfg from "../config/mcp.json";

export type Stage = "dev" | "stage" | "prod";

export interface McpGatewayStackProps extends StackProps {
  stage: Stage;
  /** Engine-level mode. prod is always ENFORCE (see bin/app.ts). */
  engineMode: "LOG_ONLY" | "ENFORCE";
  /** Policy file basenames (without .cedar) deployed with enforcementMode LOG_ONLY. */
  shadowPolicies: string[];
  /** Optional VPC for the adapter (needed to reach on-prem systems via TGW/DX). */
  vpcId?: string;
}

/**
 * One domain MCP server behind its own AgentCore Gateway and policy engine.
 *
 * Trust path: CUSTOM_JWT inbound -> Cedar (default deny) -> REQUEST interceptor
 * (injects trusted context from validated claims) -> Lambda adapter (re-checks
 * partition scope, idempotency, approvals) -> system of record.
 *
 * Property names follow aws-cdk-lib aws-bedrockagentcore L1 constructs
 * (verified against 2.274.0). Re-verify IAM actions for policy evaluation
 * against the current AgentCore Policy permissions page.
 */
export class McpGatewayStack extends Stack {
  constructor(scope: Construct, id: string, props: McpGatewayStackProps) {
    super(scope, id, props);
    const { stage } = props;
    const base = `mcp-${cfg.name}-${stage}`;
    for (const [k, v] of Object.entries(cfg.tags)) Tags.of(this).add(k, v);
    Tags.of(this).add("mcp:stage", stage);

    const key = new kms.Key(this, "Key", {
      alias: `alias/${base}`,
      enableKeyRotation: true,
      removalPolicy: stage === "prod" ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
    });

    // --- Business state owned by the domain: idempotency + approvals -------
    const state = new dynamodb.Table(this, "State", {
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "sk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: key,
      timeToLiveAttribute: "expiresAt",
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: stage === "prod" ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
    });

    const vpc = props.vpcId ? ec2.Vpc.fromLookup(this, "Vpc", { vpcId: props.vpcId }) : undefined;

    const logGroup = (name: string) =>
      new logs.LogGroup(this, `${name}Logs`, {
        retention: stage === "prod" ? logs.RetentionDays.THIRTEEN_MONTHS : logs.RetentionDays.ONE_MONTH,
        encryptionKey: key,
        removalPolicy: RemovalPolicy.DESTROY,
      });

    const adapter = new lambda.Function(this, "Adapter", {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: "handler.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "..", "lambda", "adapter")),
      timeout: Duration.seconds(30),
      memorySize: 512,
      tracing: lambda.Tracing.ACTIVE,
      logGroup: logGroup("Adapter"),
      vpc,
      vpcSubnets: vpc ? { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS } : undefined,
      environment: {
        STATE_TABLE: state.tableName,
        PARTITION_CLAIM: cfg.partitionClaim,
        TARGET_NAME: cfg.targetName,
        STAGE: stage,
      },
    });
    state.grantReadWriteData(adapter);

    const interceptor = new lambda.Function(this, "Interceptor", {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: "handler.lambda_handler",
      // CI vendors requirements.txt into this folder before synth (see workflow).
      code: lambda.Code.fromAsset(path.join(__dirname, "..", "lambda", "interceptor")),
      timeout: Duration.seconds(5),
      memorySize: 256,
      tracing: lambda.Tracing.ACTIVE,
      logGroup: logGroup("Interceptor"),
      environment: {
        DISCOVERY_URL: cfg.discoveryUrl,
        ALLOWED_AUDIENCE: cfg.allowedAudience.join(","),
        PARTITION_CLAIM: cfg.partitionClaim,
      },
    });

    // --- Gateway execution role: invoke only these two functions ----------
    const role = new iam.Role(this, "GatewayRole", {
      assumedBy: new iam.ServicePrincipal("bedrock-agentcore.amazonaws.com", {
        conditions: { StringEquals: { "aws:SourceAccount": this.account } },
      }),
      description: `Execution role for ${base} AgentCore Gateway`,
    });
    adapter.grantInvoke(role);
    interceptor.grantInvoke(role);
    key.grantEncryptDecrypt(role);

    const engine = new agentcore.CfnPolicyEngine(this, "PolicyEngine", {
      name: `${cfg.domain}_${cfg.name}_${stage}`.replace(/[^A-Za-z0-9_]/g, "_").slice(0, 48),
      description: `Cedar policies for ${base}`,
      encryptionKeyArn: key.keyArn,
    });
    role.addToPolicy(
      new iam.PolicyStatement({
        // VERIFY: action names against the AgentCore Policy IAM documentation.
        actions: [
          "bedrock-agentcore:AuthorizeAction",
          "bedrock-agentcore:PartiallyAuthorizeActions",
          "bedrock-agentcore:GetPolicyEngine",
        ],
        resources: [engine.attrPolicyEngineArn, `${engine.attrPolicyEngineArn}/*`],
      }),
    );

    const gateway = new agentcore.CfnGateway(this, "Gateway", {
      name: base,
      description: `${cfg.domain} MCP gateway (${stage})`,
      roleArn: role.roleArn,
      protocolType: "MCP",
      authorizerType: "CUSTOM_JWT",
      authorizerConfiguration: {
        customJwtAuthorizer: { discoveryUrl: cfg.discoveryUrl, allowedAudience: cfg.allowedAudience },
      },
      protocolConfiguration: { mcp: { searchType: "SEMANTIC" } },
      kmsKeyArn: key.keyArn,
      exceptionLevel: stage === "dev" ? "DEBUG" : undefined,
      policyEngineConfiguration: { arn: engine.attrPolicyEngineArn, mode: props.engineMode },
      interceptorConfigurations: [
        {
          interceptionPoints: ["REQUEST"],
          interceptor: { lambda: { arn: interceptor.functionArn } },
          // Needed to read the bearer token; the interceptor never logs headers.
          inputConfiguration: { passRequestHeaders: true },
        },
      ],
      tags: cfg.tags,
    });
    gateway.node.addDependency(role);

    const tools = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "tools.json"), "utf8"));
    const target = new agentcore.CfnGatewayTarget(this, "Target", {
      gatewayIdentifier: gateway.attrGatewayIdentifier,
      name: cfg.targetName,
      description: `Lambda adapter for ${cfg.name}`,
      targetConfiguration: { mcp: { lambda: { lambdaArn: adapter.functionArn, toolSchema: { inlinePayload: tools } } } },
      credentialProviderConfigurations: [{ credentialProviderType: "GATEWAY_IAM_ROLE" }],
    });

    // --- Cedar policies (break-glass forbids live in policies/breakglass and
    //     are deployed only through the fast-track pipeline) ----------------
    const policyDir = path.join(__dirname, "..", "policies");
    for (const file of fs.readdirSync(policyDir).filter(f => f.endsWith(".cedar")).sort()) {
      const basename = file.replace(/\.cedar$/, "");
      const statement = Fn.sub(fs.readFileSync(path.join(policyDir, file), "utf8"), {
        GatewayArn: gateway.attrGatewayArn,
      });
      const policy = new agentcore.CfnPolicy(this, `Policy-${basename}`, {
        name: basename.replace(/[^A-Za-z0-9_]/g, "_").slice(0, 48),
        policyEngineId: engine.attrPolicyEngineId,
        definition: { cedar: { statement } },
        enforcementMode: props.shadowPolicies.includes(basename) ? "LOG_ONLY" : "ACTIVE",
        validationMode: "FAIL_ON_ANY_FINDINGS",
        description: `Generated from policies/${file}`,
      });
      // The Cedar schema is generated from deployed tools: create targets first.
      policy.node.addDependency(target);
    }

    new CfnOutput(this, "GatewayUrl", { value: gateway.attrGatewayUrl });
    new CfnOutput(this, "GatewayArn", { value: gateway.attrGatewayArn });
    new CfnOutput(this, "PolicyEngineArn", { value: engine.attrPolicyEngineArn });
  }
}
