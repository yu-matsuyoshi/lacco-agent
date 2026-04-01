#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { KintaiAgentStack } from '../lib/kintai-agent-stack';

const app = new cdk.App();

new KintaiAgentStack(app, 'KintaiAgentStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'ap-northeast-1',
  },
  description: 'Kintai Agent infrastructure with AgentCore Runtime',
});
