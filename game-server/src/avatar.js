// avatar.js
const { LambdaClient, InvokeCommand } = require('@aws-sdk/client-lambda');

const lambda = new LambdaClient({
  region: process.env.COGNITO_REGION,
  timeout: 300000, // 5 min — avatar gen can take ~60s
});

async function generateAvatar(playerId, characterDescription) {
  const response = await lambda.send(new InvokeCommand({
    FunctionName: process.env.AVATAR_LAMBDA_ARN,
    InvocationType: 'RequestResponse',
    Payload: JSON.stringify({ playerId, description: characterDescription }),
  }));

  const result = JSON.parse(Buffer.from(response.Payload));
  if (result.errorMessage) {
    throw new Error(`Avatar Lambda failed: ${result.errorMessage}`);
  }
  if (result.error) {
    throw new Error(`Avatar generation failed: ${result.error}`);
  }
  if (!result.avatarUrl) {
    throw new Error('Avatar Lambda returned no avatarUrl');
  }
  return result.avatarUrl;
}

module.exports = { generateAvatar };
