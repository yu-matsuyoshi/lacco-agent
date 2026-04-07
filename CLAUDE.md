# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kintai Agent - an AI agent that converts natural language (Japanese) into OA Lacco APP work-hours commands. Deployed on AWS Bedrock AgentCore Runtime using A2A protocol, with a local Streamlit frontend.

## Architecture

```
[Streamlit UI] ─[Cognito auth]→ [AgentCore Runtime (A2A)]
                                        │
                                  [AgentCore Memory]
                                        │
                                  [AgentCore Gateway (MCP)]
                                   /       |       \
                          [Lambda]   [Lambda]   [Lambda]
                        get_projects get_categories validate_percentage
                              └──────→ [S3 CSV] ←──────┘
```

Authentication: User→Runtime (Cognito USER_PASSWORD_AUTH), Runtime→Gateway (M2M OAuth2 via AgentCore Identity), Gateway→Lambda (IAM).

## Key Directories

- `cdk/` - AWS CDK infrastructure (TypeScript). Stack in `lib/kintai-agent-stack.ts`
- `cdk/lambda/` - Lambda function handlers (TypeScript, Node.js 20.x)
- `kintai_agent/` - Python agent code. Main entry: `agent_a2a.py` (A2A server on port 9000)
- `kintai_agent/core.py` - `KintaiAgentCore` class: token management, MCP client, system prompt
- `frontend_a2a/` - Streamlit A2A client. Config in `config.py`, env in `.env`
- `data/` - Master CSV files (projects.csv, categories.csv) uploaded to S3
- `.kiro/steering/` - Detailed architecture guides (agentcore-cdk, a2a-platform, strands-agents, testing)

## Common Commands

### CDK (from `cdk/` directory)

```bash
npm install
npm run build                    # compile TypeScript

# Always specify region explicitly (AWS profile default may override)
CDK_DEFAULT_REGION=ap-northeast-1 CDK_DEFAULT_ACCOUNT=<account> npx cdk diff --profile <profile>
CDK_DEFAULT_REGION=ap-northeast-1 CDK_DEFAULT_ACCOUNT=<account> npx cdk deploy --profile <profile>
CDK_DEFAULT_REGION=ap-northeast-1 npx cdk synth
```

### Agent (from `kintai_agent/` directory)

```bash
pip install -r requirements.txt
uvicorn agent_a2a:app --host 0.0.0.0 --port 9000   # A2A server
python -m kintai_agent                                # HTTP server (legacy)
```

### Frontend (from `frontend_a2a/` directory)

```bash
pip install -r requirements.txt
streamlit run app.py                # standard A2A client
streamlit run app_orchestrator.py   # multi-agent orchestrator
```

### Tests

```bash
cd tests && python -m pytest test_*.py -v
```

### Post-deploy setup

```bash
# Required after CDK deploy - sets up M2M OAuth2 Credential Provider
cd cdk/scripts && ./setup-m2m-credential-provider.sh --profile <profile>
```

## Important Constraints

- **CDK region**: Must pass `CDK_DEFAULT_REGION` explicitly; AWS profile region takes precedence otherwise
- **Model ID format**: Use `jp.anthropic.*` prefix for ap-northeast-1 (e.g., `jp.anthropic.claude-sonnet-4-6`)
- **Parallel stacks**: us-east-1 uses `KintaiAgentStack`, ap-northeast-1 uses `KintaiAgentStackApne1`
- **context_id / session_id**: Must be 33+ characters for A2A protocol and AgentCore Memory
- **Per-request Agent**: Each A2A request creates a new Agent with fresh MCP tools (containers recycle after 15min idle)
- **DynamoDB token cache**: M2M tokens are cached in DynamoDB (not in-memory) because containers are ephemeral
- **Gateway tool names**: Prefixed with target name (e.g., `get-projects___get_projects`)
- **AgentCore Identity**: No CDK L2 Construct available; must run setup script after deploy
- **Dockerfile.a2a**: ARM64 platform (AgentCore Runtime requirement)
- **Streamlit**: Local-only; not deployed to AWS

## Language

The codebase uses Japanese for comments, prompts, user-facing text, and commit messages. Follow this convention.
