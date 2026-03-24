import * as cdk from 'aws-cdk-lib';
import { PixelSocialStack } from '../lib/pixel-social-stack';

const app = new cdk.App();

new PixelSocialStack(app, 'PixelSocialStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
