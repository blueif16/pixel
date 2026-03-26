# Pixel Social — Project CLAUDE.md

## Stack
- **Infra**: AWS CDK (VPC, DynamoDB, Cognito, S3+OAC, CloudFront, ECS Fargate, ALB, Lambda)
- **Game Server**: Node.js WebSocket server on ECS Fargate (port 3000)
- **Avatar Gen**: Python Lambda + Gemini image gen + rembg background removal
- **Client**: Single HTML file (canvas-based, pixel art renderer)

## Key Endpoints (deployed)
- ALB DNS: `PixelS-Pixel-Av5cnPVBHFIm-2101309226.us-east-1.elb.amazonaws.com`
- CloudFront: `dc9iwjwlk784c.cloudfront.net`
- S3 Bucket: `pixel-social-assets`
- Cognito Pool: `us-east-1_T4Gej0pzm`

## Character Flow
1. Client sends `{ type: 'create_character', payload: { description: "..." } }` via WebSocket
2. Server wraps description (200 char cap), invokes Lambda
3. Lambda: Gemini generates 4x4 sprite grid → rembg removes background → splits to cells → assembles 8x4 sheet → uploads to S3
4. Server sends `{ type: 'character_created', payload: { avatarUrl: "..." } }`
5. Client renders sprite sheet at 32x32 cell resolution

## Sprite Sheet Format
- 256x128 PNG (8 cols × 4 rows, 32px cells)
- Cols: idle(0), stepA(1), stepB(2), sit(3), wave(4), sleep(5), eat(6), laugh(7)
- Rows: down(0), left(1), up(2), right(3)
- Walk cycle: idle → stepA → idle → stepB

## Lambda Env Vars
`GOOGLE_API_KEY`, `IMAGE_GEN_MODEL` (gemini-3-pro-image-preview), `REMBG_API_KEY`, `REMBG_API_URL`, `S3_BUCKET`, `CLOUDFRONT_DOMAIN`

## Dev Commands
```bash
# Test Lambda locally
cd lambda && pip install -r requirements.txt && python avatar_lambda.py "blue spiky hair, red hoodie"

# Rebuild & redeploy game server
docker --context desktop-linux build -t pixel-social-server:latest . && \
  docker --context desktop-linux push 911319296449.dkr.ecr.us-east-1.amazonaws.com/pixel-social-server:latest && \
  aws ecs update-service --cluster pixel-social-cluster --service PixelSocialStack-PixelSocialServiceF69AC5DC-eWEHoEaRCDCI --force-new-deployment
```

## NEVER commit
- `.env`, `*.env` — contain API keys
- `debug_*.png` — debug output files
