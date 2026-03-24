# Pixel Social Rooms — AI-Generated Multiplayer Game

A multiplayer social rooms game where every visual asset — characters, furniture, tiles — is AI-generated. Built on AWS with ECS Fargate, Cognito, DynamoDB, and a Python Lambda for avatar generation.

## Architecture

```
Browser Client (HTML/Canvas)
│
├── HTTPS GET → CloudFront → S3 (static assets + AI avatars)
└── WebSocket → ALB → ECS Fargate (game server)
                      │
                      ├── Cognito (JWT validation)
                      ├── DynamoDB (Rooms, Players, Interactions)
                      └── Lambda (avatar gen: AI API → post-process → S3)
```

## Repository Structure

```
pixel-social/
├── infra/                   # AWS CDK TypeScript — all cloud infrastructure
│   ├── lib/pixel-social-stack.ts   # Main stack
│   ├── bin/infra.ts          # Stack instantiation
│   └── package.json
│
├── lambda/                   # Avatar generation Lambda (Python 3.12)
│   ├── avatar_lambda.py      # Main handler: AI gen → grid split → flip → S3
│   └── requirements.txt       # Pillow, boto3, requests
│
├── scripts/                  # Dev-time AI asset generation
│   ├── generate_furniture.py # AI-generate furniture sprites (one-shot)
│   └── generate_tiles.py     # AI-generate floor/wall/door tiles (one-shot)
│
├── game-server/              # Node.js 20 WebSocket game server
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── index.js          # HTTP + WebSocketServer on /ws
│       ├── auth.js           # Cognito JWT validation
│       ├── avatar.js         # Lambda invocation
│       ├── prompt.js         # buildCharacterDescription()
│       ├── state.js          # In-memory room/connection state
│       ├── broadcast.js       # Room-scoped broadcast
│       ├── router.js         # Message type → handler dispatch
│       ├── handlers/
│       │   ├── character.js  # create_character → character_generating → character_created
│       │   ├── room.js       # join_room, leave_room, move
│       │   ├── furniture.js  # Stub to B's module
│       │   └── social.js     # sit, stand, chat (proxies to C's module)
│       └── modules/
│           ├── decorEngine.js   # Stub for B's furniture module
│           └── socialEngine.js  # Stub for C's social module
│
├── client/                   # Test client
│   ├── index.html            # Single-file HTML/Canvas client
│   └── manifest.json         # Asset manifest (sprites, tiles, character options)
│
├── tests/integration/         # Integration test scripts
│   ├── test0_smoke.sh        # Infrastructure smoke tests
│   ├── test1_single_player.sh
│   ├── test2_two_players.sh
│   └── test5_disconnect_cleanup.sh
│
├── DEPLOYMENT_CHECKLIST.md   # Full deployment checklist from spec
└── docs/
    └── pixel-social-AD-guide-v2.md  # Full technical specification
```

## Stacks & Services

### CDK Stack: `PixelSocialStack`
Deployed via `cdk deploy PixelSocialStack`.

| Service | CDK Resource | Purpose |
|---------|--------------|---------|
| VPC | `ec2.Vpc` | 10.0.0.0/16, 2 public + 2 private subnets, 1 NAT GW |
| DynamoDB — Rooms | `dynamodb.Table` | roomId → occupants mapping |
| DynamoDB — Players | `dynamodb.Table` | playerId → avatarUrl, displayName |
| DynamoDB — Interactions | `dynamodb.Table` | roomId + chairId → seat claims |
| Cognito User Pool | `cognito.UserPool` | Email sign-in, SRP auth, no client secret |
| Cognito App Client | `cognito.UserPoolClient` | Public SPA client for browser |
| S3 Bucket | `s3.Bucket` | pixel-social-assets, block public, OAC |
| CloudFront Distribution | `cloudfront.Distribution` | HTTPS, OAC → S3, 3 cache behaviors |
| ECS Cluster | `ecs.Cluster` | Fargate-only, pixel-social-cluster |
| ECS Task Definition | `ecs.FargateTaskDefinition` | 512 CPU / 1024 MB, port 3000 |
| ECS Service | `ecs.FargateService` | 1 desired task, no scaling (v1) |
| ALB | `elbv2.ApplicationLoadBalancer` | Internet-facing, HTTP 80, 3600s idle |
| Target Group | `elbv2.ApplicationTargetGroup` | /health HTTP 200, IP type |
| Avatar Lambda | `lambda.Function` | Python 3.12, 1024 MB, 60s, NOT in VPC |

### CloudFormation Outputs (use `aws cloudformation list-exports`)
- `pixel-social-vpc-id`
- `pixel-social-alb-dns` — WebSocket endpoint
- `pixel-social-cognito-pool-id`
- `pixel-social-cognito-client-id`
- `pixel-social-rooms-table`
- `pixel-social-players-table`
- `pixel-social-interactions-table`
- `pixel-social-avatar-lambda-arn`
- `pixel-social-cf-domain` — Asset CDN domain
- `pixel-social-s3-bucket`

## Setup

### 1. AWS Credentials

Best practice: use a named profile with MFA-required long-term credentials or SSO.

```ini
# ~/.aws/config
[profile pixel-social]
sso_start_url = https://your-sso-start-url.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = AdministratorAccess
region = us-east-1
```

```ini
# ~/.aws/credentials
[pixel-social]
# Credentials come from SSO — run `aws sso login --profile pixel-social`
```

Then set env:
```bash
export AWS_PROFILE=pixel-social
```

### 2. Bootstrap CDK (first time only, per account+region)

```bash
cd infra
npm install
npx cdk bootstrap --profile pixel-social
```

### 3. Deploy

```bash
npx cdk synth                         # Verify template
npx cdk deploy --all --profile pixel-social   # Deploy everything
```

### 4. Before first deploy — fill in these values

**ECS Container Image** — build and push the game server Docker image to ECR, then update `infra/lib/pixel-social-stack.ts`:

```typescript
// infra/lib/pixel-social-stack.ts line 201
image: ecs.ContainerImage.fromRegistry('YOUR_ECR_REPO_URL:latest'),
```

**Lambda API Key** — after deploy, set the Lambda env var:
```bash
aws lambda update-function-configuration \
  --function-name pixel-social-avatar-gen \
  --environment Variables={IMAGE_GEN_API_KEY=sk-...} \
  --profile pixel-social
```

## Character Sprite Sheet Contract

The Lambda produces an **8×4 sprite sheet** (256×128 px, 32×32 per cell):

```
         idle(0)  stepA(1)  stepB(2)  sit(3)  wave(4)  sleep(5)  eat(6)  laugh(7)
Row 0(down)   stand     walk-A    walk-B    sit      wave     sleep    eat     laugh
Row 1(left)   stand     walk-A    walk-B    sit      wave     sleep    eat     laugh
Row 2(up)     stand     walk-A    walk-B    sit      wave     sleep    eat     laugh
Row 3(right)  stand     walk-A    walk-B    sit      wave     sleep    eat     laugh
```

AI generates 4×4 (16 cells). Post-processing derives the remaining 16 via horizontal flips:
- Right-facing row = flip of left row
- Down/Up stepB = flip of stepA (front/back views are symmetric)
- Left stepB = explicit opposite-leg generation (AI Row 4, Cell 1)
- sleep/eat/laugh = direction-independent, same cell for all rows

## Running the Test Client

```bash
cd client
# Edit index.html: set window.ALB_DNS to your ALB DNS name
python3 -m http.server 8080
# Open http://localhost:8080/?test=1 for mock data mode (no backend)
```

## Environment Variables Required by Game Server

These are injected by ECS task definition automatically via CDK outputs:

| Variable | Source |
|---------|--------|
| `COGNITO_USER_POOL_ID` | CDK output |
| `COGNITO_CLIENT_ID` | CDK output |
| `COGNITO_REGION` | CDK region |
| `DYNAMODB_REGION` | CDK region |
| `TABLE_ROOMS` | CDK output |
| `TABLE_PLAYERS` | CDK output |
| `TABLE_INTERACTIONS` | CDK output |
| `AVATAR_LAMBDA_ARN` | CDK output |
| `CLOUDFRONT_DOMAIN` | CDK output |

## Environment Variables Required by Avatar Lambda

Set manually after deploy (contains secrets):

| Variable | Value |
|----------|-------|
| `IMAGE_GEN_API_KEY` | Your AI image API key (OpenAI, Stability AI, etc.) |
| `IMAGE_GEN_PROVIDER` | `openai` \| `stability` \| `replicate` |
| `S3_BUCKET` | CDK output |
| `CLOUDFRONT_DOMAIN` | CDK output |
