"""
Avatar generation Lambda — Gemini image gen + rembg background removal + sprite sheet assembly.

Input:  { "playerId": "abc123", "description": "blue spiky hair, red hoodie, glasses" }
Output: { "avatarUrl": "https://{cdn}/avatars/abc123.png" }

Test locally:  python avatar_lambda.py
Deploy to Lambda: zip with dependencies, set env vars, done.
"""

import json
import os
import io
import logging
import base64
from typing import List, Optional

import boto3
import httpx
from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Config — env vars on Lambda, or .env / export locally
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
IMAGE_GEN_MODEL = os.environ.get("IMAGE_GEN_MODEL", "gemini-2.0-flash-exp")
REMBG_API_KEY = os.environ.get("REMBG_API_KEY", "")
REMBG_API_URL = os.environ.get("REMBG_API_URL", "https://api.remove.bg/v1.0/removebg")  # adjust to your provider
S3_BUCKET = os.environ.get("S3_BUCKET", "pixel-social-assets")
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "")

CELL = 32  # each sprite cell in final sheet
MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Prompt template — user description gets injected
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """A 4x4 pixel art character sprite sheet in the exact style of Stardew Valley.
16 equally sized square cells, 4 columns and 4 rows, on a pure white background.
Every cell has a pure white background. The same chibi-proportioned character
in every cell: {description}. 16-bit pixel art, clean pixel edges,
no anti-aliasing, no text, no labels.

Row 1, Cell 1: Character standing still, body and face pointing toward the viewer. Arms resting at sides.
Row 1, Cell 2: Character walking toward the viewer, right leg stepping forward, left arm swinging forward.
Row 1, Cell 3: Character sitting on a chair facing the viewer. Hands resting on lap, feet hanging down.
Row 1, Cell 4: Character facing the viewer, one hand raised and waving.

Row 2, Cell 1: Character standing still, nose pointing toward the left edge of the image.
Row 2, Cell 2: Character walking toward the left edge, right leg stepping forward.
Row 2, Cell 3: Character sitting on a chair, facing left.
Row 2, Cell 4: Character facing left, one hand raised and waving.

Row 3, Cell 1: Character standing still, back of head facing the viewer.
Row 3, Cell 2: Character walking away from the viewer, right leg stepping forward.
Row 3, Cell 3: Character sitting on a chair, back to viewer.
Row 3, Cell 4: Character with back to viewer, one hand raised and waving.

Row 4, Cell 1: Character walking toward the left edge, LEFT leg stepping forward, right arm swinging forward. Opposite walking pose from Row 2 Cell 2.
Row 4, Cell 2: Character lying flat on their back, eyes closed, asleep. Viewed from above.
Row 4, Cell 3: Character facing the viewer, both hands raised to mouth, eating food. Happy expression.
Row 4, Cell 4: Character facing the viewer, mouth wide open, eyes squished shut, laughing.

Every cell must have identical character proportions, colors, and pixel art style.
Cells are clearly separated with even spacing."""


# ===================================================================
# Step 1: Image Generation (Gemini)
# ===================================================================
def generate_image(prompt: str) -> Image.Image:
    """Call Gemini to generate the 4x4 sprite grid. Returns a PIL Image."""
    client = genai.Client(api_key=GOOGLE_API_KEY)

    response = client.models.generate_content(
        model=IMAGE_GEN_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1"),
        ),
    )

    for part in response.parts:
        if part.inline_data:
            return Image.open(io.BytesIO(part.inline_data.data))

    raise RuntimeError("Gemini returned no image data")


# ===================================================================
# Step 2: Background Removal (rembg API)
# ===================================================================
def remove_background(image: Image.Image) -> Image.Image:
    """Send image to rembg API, get back transparent PNG."""
    # Convert PIL → PNG bytes
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            REMBG_API_URL,
            headers={"x-api-key": REMBG_API_KEY},
            files={"image": ("sprite.png", image_bytes, "image/png")},
            data={"format": "png"},
        )
        response.raise_for_status()

    return Image.open(io.BytesIO(response.content)).convert("RGBA")


def remove_background_simple(image: Image.Image, threshold: int = 240) -> Image.Image:
    """Fallback: replace white/near-white pixels with transparency.
    Use this if rembg API is unavailable or for local testing."""
    image = image.convert("RGBA")
    data = list(image.getdata())
    new_data = [
        (r, g, b, 0) if r > threshold and g > threshold and b > threshold else (r, g, b, a)
        for r, g, b, a in data
    ]
    image.putdata(new_data)
    return image


# ===================================================================
# Step 3: Split raw AI image into 4×4 grid of cells
# ===================================================================
def split_grid(raw_img: Image.Image, rows: int = 4, cols: int = 4) -> list:
    """Returns cells[row][col] = PIL Image sized CELL×CELL."""
    w, h = raw_img.size
    cell_w, cell_h = w // cols, h // rows
    cells = []
    for r in range(rows):
        row = []
        for c in range(cols):
            box = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            cell = raw_img.crop(box).resize((CELL, CELL), Image.NEAREST)
            row.append(cell)
        cells.append(row)
    return cells


# ===================================================================
# Step 4: Flip helper
# ===================================================================
def flip_h(img: Image.Image) -> Image.Image:
    return img.transpose(Image.FLIP_LEFT_RIGHT)


# ===================================================================
# Step 5: Assemble 8×4 sprite sheet from 4×4 AI grid
# ===================================================================
#
#  AI grid (what Gemini generates):
#    Row 0 (down):   idle, walkA, sit, wave
#    Row 1 (left):   idle, walkA, sit, wave
#    Row 2 (up):     idle, walkA, sit, wave
#    Row 3 (extras): walkB_left, sleep, eat, laugh
#
#  Final sheet (what the game client expects):
#    Cols: idle(0) stepA(1) stepB(2) sit(3) wave(4) sleep(5) eat(6) laugh(7)
#    Rows: down(0) left(1) up(2) right(3)
#
def assemble_sheet(cells: list) -> Image.Image:
    sheet = Image.new("RGBA", (8 * CELL, 4 * CELL), (0, 0, 0, 0))

    sleep_cell = cells[3][1]
    eat_cell = cells[3][2]
    laugh_cell = cells[3][3]
    walkB_left = cells[3][0]  # opposite-leg walk, explicitly generated

    for final_row, ai_row, is_flip in [
        (0, 0, False),  # down  = AI row 0 as-is
        (1, 1, False),  # left  = AI row 1 as-is
        (2, 2, False),  # up    = AI row 2 as-is
        (3, 1, True),   # right = horizontal flip of left (AI row 1)
    ]:
        idle = cells[ai_row][0]
        stepA = cells[ai_row][1]
        sit = cells[ai_row][2]
        wave = cells[ai_row][3]

        # Derive stepB per direction
        if final_row == 0:    # down: front view symmetric → flip stepA
            stepB = flip_h(stepA)
        elif final_row == 1:  # left: use the explicitly generated opposite-leg cell
            stepB = walkB_left
        elif final_row == 2:  # up: back view symmetric → flip stepA
            stepB = flip_h(stepA)
        elif final_row == 3:  # right: flip of left's walkB
            stepB = flip_h(walkB_left)

        # Right-facing row: flip everything from left-facing
        if is_flip:
            idle = flip_h(idle)
            stepA = flip_h(stepA)
            stepB = flip_h(stepB)
            sit = flip_h(sit)
            wave = flip_h(wave)

        # Paste all 8 columns
        col_cells = [idle, stepA, stepB, sit, wave, sleep_cell, eat_cell, laugh_cell]
        for c, cell_img in enumerate(col_cells):
            sheet.paste(cell_img, (c * CELL, final_row * CELL))

    return sheet


# ===================================================================
# Step 6: Basic quality check
# ===================================================================
def passes_quality_check(cells: list) -> bool:
    """Sanity check: cells shouldn't be entirely blank or single-color."""
    for r in range(4):
        for c in range(4):
            img = cells[r][c]
            colors = img.convert("RGB").getcolors(maxcolors=256)
            # If entire cell is 1 color → probably empty/broken
            if colors and len(colors) <= 2:
                logger.warning(f"Cell [{r}][{c}] looks empty ({len(colors)} colors)")
                return False
    return True


# ===================================================================
# Full pipeline
# ===================================================================
def generate_avatar(player_id: str, description: str) -> dict:
    """
    End-to-end: prompt → Gemini → bg remove → split → flip → compose → S3.
    Returns { "avatarUrl": "https://cdn/avatars/{player_id}.png" }
    """
    # Wrap user text into the sprite sheet prompt
    safe_desc = description.strip()[:300]  # length cap
    full_prompt = PROMPT_TEMPLATE.format(
        description=f"A young character, {safe_desc}"
    )

    logger.info(f"Generating avatar for {player_id}: {safe_desc[:80]}...")

    # Generate with retries
    best_cells = None
    for attempt in range(MAX_RETRIES):
        logger.info(f"  Attempt {attempt + 1}/{MAX_RETRIES}")

        raw_img = generate_image(full_prompt)
        logger.info(f"  Raw image: {raw_img.size}")

        # Background removal — try API first, fall back to simple threshold
        try:
            clean_img = remove_background(raw_img)
            logger.info("  Background removed via API")
        except Exception as e:
            logger.warning(f"  rembg API failed ({e}), using simple threshold removal")
            clean_img = remove_background_simple(raw_img)

        cells = split_grid(clean_img)

        if passes_quality_check(cells):
            best_cells = cells
            break
        else:
            logger.warning(f"  Quality check failed on attempt {attempt + 1}")
            best_cells = cells  # keep as fallback

    if best_cells is None:
        raise RuntimeError("All generation attempts failed")

    # Assemble final 8×4 sheet (256×128)
    sheet = assemble_sheet(best_cells)
    logger.info(f"  Final sheet: {sheet.size}")

    # Save to S3
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    buf.seek(0)

    key = f"avatars/{player_id}.png"
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=buf.getvalue(),
        ContentType="image/png",
        CacheControl="max-age=86400",
    )
    logger.info(f"  Uploaded to s3://{S3_BUCKET}/{key}")

    avatar_url = f"https://{CLOUDFRONT_DOMAIN}/{key}"
    return {"avatarUrl": avatar_url}


# ===================================================================
# Lambda handler
# ===================================================================
def handler(event, context):
    """
    Lambda entry point.
    Input:  { "playerId": "abc123", "description": "blue spiky hair, red hoodie" }
    Output: { "avatarUrl": "https://cdn/avatars/abc123.png" }
    """
    try:
        player_id = event["playerId"]
        description = event.get("description", "a friendly character with colorful clothes")
        result = generate_avatar(player_id, description)
        return result
    except Exception as e:
        logger.error(f"Avatar generation failed: {e}", exc_info=True)
        return {"error": str(e)}


# ===================================================================
# Local testing — run directly: python avatar_lambda.py
# ===================================================================
if __name__ == "__main__":
    import sys

    desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "spiky blue hair, light skin, red hoodie, round glasses"
    player_id = "local_test_001"

    print(f"=== LOCAL TEST ===")
    print(f"Description: {desc}")
    print()

    # --- Step-by-step with debug saves ---
    safe_desc = desc.strip()[:300]
    full_prompt = PROMPT_TEMPLATE.format(description=f"A young character, {safe_desc}")

    print("[1/5] Generating image via Gemini...")
    raw_img = generate_image(full_prompt)
    raw_img.save("debug_1_raw.png")
    print(f"  Saved debug_1_raw.png ({raw_img.size})")

    print("[2/5] Removing background...")
    try:
        clean_img = remove_background(raw_img)
        print("  Used rembg API")
    except Exception as e:
        print(f"  rembg API failed ({e}), using threshold fallback")
        clean_img = remove_background_simple(raw_img)
    clean_img.save("debug_2_clean.png")
    print(f"  Saved debug_2_clean.png")

    print("[3/5] Splitting into 4×4 grid...")
    cells = split_grid(clean_img)
    for r in range(4):
        for c in range(4):
            cells[r][c].save(f"debug_3_cell_{r}_{c}.png")
    print(f"  Saved debug_3_cell_*.png (16 files)")

    ok = passes_quality_check(cells)
    print(f"  Quality check: {'PASS' if ok else 'FAIL'}")

    print("[4/5] Assembling 8×4 sprite sheet...")
    sheet = assemble_sheet(cells)
    sheet.save("debug_4_sheet.png")
    print(f"  Saved debug_4_sheet.png ({sheet.size})")

    # Skip S3 upload in local mode
    print("[5/5] Skipping S3 upload (local mode)")

    print()
    print("=== DONE ===")
    print("Check these files:")
    print("  debug_1_raw.png       — raw Gemini output (should be 4×4 grid)")
    print("  debug_2_clean.png     — after background removal")
    print("  debug_3_cell_R_C.png  — individual cells (verify poses)")
    print("  debug_4_sheet.png     — final 256×128 sprite sheet")
    print()
    print("Verify:")
    print("  - Row 0 = facing down, Row 1 = left, Row 2 = back, Row 3 = right")
    print("  - Row 3 should be a mirror of Row 1")
    print("  - Cols: idle, stepA, stepB, sit, wave, sleep, eat, laugh")
    print("  - Walk cycle: col0 → col1 → col0 → col2")
    print("  - Transparent background (no white boxes)")
