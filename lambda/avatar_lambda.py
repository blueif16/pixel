"""
Avatar Generation Lambda
Pixel Social - AI-generated character sprite sheets
"""

import json
import os
import io
import boto3
import requests
from PIL import Image

s3 = boto3.client('s3')

BUCKET = os.environ['S3_BUCKET']
CDN = os.environ['CLOUDFRONT_DOMAIN']
API_KEY = os.environ['IMAGE_GEN_API_KEY']
PROVIDER = os.environ.get('IMAGE_GEN_PROVIDER', 'openai')

CELL = 32

PROMPT_TEMPLATE = """A 4x4 pixel art character sprite sheet in the exact style of Stardew Valley.
16 equally sized square cells, 4 columns and 4 rows, on a pure white background.
Every cell has a pure white background. The same chibi-proportioned character
in every cell: [CHARACTER_DESCRIPTION]. 16-bit pixel art, clean pixel edges,
no anti-aliasing, no text, no labels.

Row 1, Cell 1: Character standing still, body and face pointing toward the
viewer. Arms resting at sides.
Row 1, Cell 2: Character walking toward the viewer, right leg stepping forward,
left arm swinging forward. Body and face pointing toward the viewer.
Row 1, Cell 3: Character sitting on a chair facing the viewer. Hands resting
on lap, feet hanging down.
Row 1, Cell 4: Character facing the viewer, one hand raised and waving. Body
and face pointing toward the viewer.

Row 2, Cell 1: Character standing still, body turned so the character's nose
points toward the left edge of the image. We see the right side of the
character's body.
Row 2, Cell 2: Character walking toward the left edge of the image, right leg
stepping forward, left arm swinging forward. Nose pointing toward the left edge.
Row 2, Cell 3: Character sitting on a chair, nose pointing toward the left edge
of the image. We see the right side of the character's body.
Row 2, Cell 4: Character facing the left edge of the image, one hand raised and
waving. Nose pointing toward the left edge.

Row 3, Cell 1: Character standing still, back of head facing the viewer. We see
the character's back, not their face.
Row 3, Cell 2: Character walking away from the viewer, right leg stepping
forward, left arm swinging forward. We see the character's back.
Row 3, Cell 3: Character sitting on a chair, back of head facing the viewer. We
see the character's back.
Row 3, Cell 4: Character with back to the viewer, one hand raised and waving. We
see the back of the character's head.

Row 4, Cell 1: Character walking toward the left edge of the image, left leg
stepping forward, right arm swinging forward. Nose pointing toward the left edge.
This is the opposite walking pose from Row 2 Cell 2.
Row 4, Cell 2: Character lying flat on their back, eyes closed, asleep. Viewed
from above, head near the top of the cell, feet near the bottom.
Row 4, Cell 3: Character facing the viewer, both hands raised to mouth, eating
food. Happy expression.
Row 4, Cell 4: Character facing the viewer, mouth wide open, eyes squished shut,
laughing. Body leaning back slightly.

Every cell must have identical character proportions, colors, and pixel art style.
Cells are clearly separated with even spacing."""


def generate_image(prompt):
    """Call AI image gen API. Returns a PIL Image."""
    if PROVIDER == 'openai':
        resp = requests.post(
            'https://api.openai.com/v1/images/generations',
            headers={'Authorization': f'Bearer {API_KEY}'},
            json={
                'model': 'dall-e-3',
                'prompt': prompt,
                'n': 1,
                'size': '1024x1024',
                'response_format': 'b64_json',
                'quality': 'hd',
                'style': 'natural',
            },
            timeout=120,
        )
        resp.raise_for_status()
        import base64
        b64 = resp.json()['data'][0]['b64_json']
        return Image.open(io.BytesIO(base64.b64decode(b64)))

    elif PROVIDER == 'stability':
        resp = requests.post(
            'https://api.stability.ai/v2beta/stable-image/generate/core',
            headers={'Authorization': f'Bearer {API_KEY}'},
            files={'none': ''},
            data={
                'prompt': prompt,
                'output_format': 'png',
                'aspect_ratio': '1:1',
                'style_preset': 'pixel-art',
            },
            timeout=120,
        )
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content))

    raise ValueError(f'Unknown provider: {PROVIDER}')


def split_grid(raw_img, rows=4, cols=4):
    """Split a raw AI image into a grid of cells.
    Returns a 2D list: cells[row][col] = PIL Image (CELL x CELL)."""
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


def remove_white_bg(img, threshold=240):
    """Replace white/near-white pixels with transparency."""
    img = img.convert('RGBA')
    data = img.getdata()
    new_data = []
    for pixel in data:
        if pixel[0] > threshold and pixel[1] > threshold and pixel[2] > threshold:
            new_data.append((pixel[0], pixel[1], pixel[2], 0))
        else:
            new_data.append(pixel)
    img.putdata(new_data)
    return img


def flip_h(img):
    """Horizontal flip."""
    return img.transpose(Image.FLIP_LEFT_RIGHT)


def assemble_sheet(cells):
    """Take the 4x4 AI grid cells and produce the 8x4 final sheet.

    AI grid layout:
      Row 0 (down):  idle, walkA, sit, wave
      Row 1 (left):  idle, walkA, sit, wave
      Row 2 (up):    idle, walkA, sit, wave
      Row 3 (extra): walkB_left, sleep, eat, laugh

    Final sheet columns:
      0=idle, 1=stepA, 2=stepB, 3=sit, 4=wave, 5=sleep, 6=eat, 7=laugh
    Final sheet rows:
      0=down, 1=left, 2=up, 3=right
    """
    COLS_OUT = 8
    ROWS_OUT = 4
    sheet = Image.new('RGBA', (COLS_OUT * CELL, ROWS_OUT * CELL), (0, 0, 0, 0))

    sleep_cell = cells[3][1]
    eat_cell = cells[3][2]
    laugh_cell = cells[3][3]
    walkB_left = cells[3][0]

    for final_row, ai_row, is_flip in [
        (0, 0, False),
        (1, 1, False),
        (2, 2, False),
        (3, 1, True),
    ]:
        idle = cells[ai_row][0]
        stepA = cells[ai_row][1]
        sit = cells[ai_row][2]
        wave = cells[ai_row][3]

        if final_row == 0:
            stepB = flip_h(stepA)
        elif final_row == 1:
            stepB = walkB_left
        elif final_row == 2:
            stepB = flip_h(stepA)
        elif final_row == 3:
            stepB = flip_h(walkB_left)

        if is_flip:
            idle = flip_h(idle)
            stepA = flip_h(stepA)
            stepB = flip_h(stepB)
            sit = flip_h(sit)
            wave = flip_h(wave)

        col_cells = [idle, stepA, stepB, sit, wave, sleep_cell, eat_cell, laugh_cell]
        for c, cell_img in enumerate(col_cells):
            sheet.paste(cell_img, (c * CELL, final_row * CELL))

    return sheet


def handler(event, context):
    player_id = event['playerId']
    description = event['characterDescription']

    prompt = PROMPT_TEMPLATE.replace('[CHARACTER_DESCRIPTION]', description)
    raw_img = generate_image(prompt)
    cells = split_grid(raw_img)

    for r in range(4):
        for c in range(4):
            cells[r][c] = remove_white_bg(cells[r][c])

    sheet = assemble_sheet(cells)

    buf = io.BytesIO()
    sheet.save(buf, format='PNG')
    buf.seek(0)

    key = f'avatars/{player_id}.png'
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=buf.getvalue(),
        ContentType='image/png',
        CacheControl='max-age=86400',
    )

    return {'avatarUrl': f'https://{CDN}/{key}'}
