# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

- **Infra**: AWS CDK TypeScript (`infra/`) — VPC, DynamoDB, Cognito, S3+OAC, CloudFront, ECS Fargate, ALB, Lambda
- **Game Server**: Node.js 20 WebSocket server (`game-server/`) on ECS Fargate, port 3000
- **Avatar Lambda**: Python 3.12 Lambda (`lambda/`) — Gemini image gen + rembg background removal → S3
- **Client**: Single HTML canvas app (`client/index.html`) with Cognito SRP auth
- **Scripts**: Python asset generators (`scripts/`) for tiles and furniture via Gemini API

## Architecture

```
Browser → CloudFront (S3 static assets: tiles, furniture, avatars)
       → ALB:80/ws (WebSocket, JWT-authenticated) → ECS Fargate → DynamoDB
                                                                → Lambda (avatar gen) → Gemini API + rembg → S3
       → Cognito (SRP auth, email-based sign-up)
```

**WebSocket message flow**: Client sends `{ type, payload }` → `router.js` dispatches to handler → handler updates `state.js` in-memory maps → `broadcast.js` sends to room peers.

**Game server modules**:
- `state.js`: In-memory maps (`roomConnections`, `playerState`, `allConnections`) — no DynamoDB persistence yet
- `auth.js`: Cognito JWT validation via JWKS
- Handlers: `character.js`, `room.js`, `social.js`, `furniture.js`
- `socialEngine.js` and `decorEngine.js`: Stubs — friend/furniture methods throw "not yet implemented"

**Character creation pipeline**: Text description → Lambda → Gemini generates 4×4 sprite grid (256×256) → rembg removes background → split into cells → assemble 8×4 sheet (256×128 px) → upload to S3 → CloudFront URL returned

## Sprite Sheet Format

- 256×128 PNG (8 cols × 4 rows, 32px cells)
- Cols: idle(0), stepA(1), stepB(2), sit(3), wave(4), sleep(5), eat(6), laugh(7)
- Rows: down(0), left(1), up(2), right(3)
- Walk cycle: idle → stepA → idle → stepB
- Right row is horizontally flipped from left row

## Key Endpoints (deployed)

- ALB: `PixelS-Pixel-Av5cnPVBHFIm-2101309226.us-east-1.elb.amazonaws.com`
- CloudFront: `dc9iwjwlk784c.cloudfront.net`
- S3 Bucket: `pixel-social-assets`
- Cognito Pool: `us-east-1_T4Gej0pzm`

## Dev Commands

```bash
# Game server (local)
cd game-server && npm start

# Test Lambda locally (saves debug_*.png for pipeline inspection)
cd lambda && pip install -r requirements.txt && python avatar_lambda.py "blue spiky hair, red hoodie"

# Generate tile/furniture assets (outputs to client/tiles/, client/furniture/, client/manifest.json)
cd scripts && uv venv --python 3.12 && uv pip install google-genai httpx Pillow python-dotenv
scripts/.venv/bin/python generate_assets.py

# Upload all static assets to S3 (client/, tiles, furniture, rooms, manifest, index.html)
# ALWAYS invalidate CloudFront after any S3 upload — otherwise browsers serve stale cached files
aws s3 sync client/ s3://pixel-social-assets/ --exclude "*.DS_Store" && \
  aws cloudfront create-invalidation --distribution-id E36VNYA2B4UQRB --paths "/*"

# Deploy infra
cd infra && npm run build && npx cdk deploy

# Rebuild & redeploy game server (MUST use --platform linux/amd64, ECS Fargate is x86_64)
cd game-server && \
  docker buildx build --platform linux/amd64 -t 911319296449.dkr.ecr.us-east-1.amazonaws.com/pixel-social-server:latest . && \
  docker push 911319296449.dkr.ecr.us-east-1.amazonaws.com/pixel-social-server:latest && \
  aws ecs update-service --cluster pixel-social-cluster --service PixelSocialStack-PixelSocialServiceF69AC5DC-eWEHoEaRCDCI --force-new-deployment

# Run integration tests (require deployed infra + wscat + jq)
bash tests/integration/test0_smoke.sh
bash tests/integration/test1_single_player.sh
bash tests/integration/test2_two_players.sh
bash tests/integration/test5_disconnect_cleanup.sh
```

## Environment Variables

**Lambda** (set in AWS console/CDK): `GOOGLE_API_KEY`, `IMAGE_GEN_MODEL` (gemini-3-pro-image-preview), `REMBG_API_KEY`, `REMBG_API_URL`, `S3_BUCKET`, `CLOUDFRONT_DOMAIN`

**Game Server** (injected by CDK): `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_REGION`, `TABLE_ROOMS`, `TABLE_PLAYERS`, `TABLE_INTERACTIONS`, `AVATAR_LAMBDA_ARN`, `CLOUDFRONT_DOMAIN`

## Python Package Manager

Use `uv` for all Python work in `scripts/` and `lambda/`. Run scripts under `.venv`.

## Room Format

Rooms are JSON files in `client/rooms/` with `name`, `width`, `height`, `spawnPoint`, `tileMap` (2D array of tile IDs), and `furniture` (array of `{itemId, x, y}`). Asset metadata lives in `client/manifest.json`.

## Docker Builds (Apple Silicon → AWS)

ALWAYS specify `--platform linux/amd64` for Docker images targeting AWS (ECS Fargate, Lambda). Without it, builds on Apple Silicon produce arm64 images that fail with `exec format error` (ECS) or `Runtime.InvalidEntrypoint` (Lambda).
- **Game server**: `docker buildx build --platform linux/amd64 ...` (manual build+push)
- **Lambda Docker**: Use `platform: Platform.LINUX_AMD64` in CDK's `DockerImageCode.fromImageAsset()` (import from `aws-cdk-lib/aws-ecr-assets`)

## NEVER commit

- `.env`, `*.env` — contain API keys
- `debug_*.png` — debug output files
