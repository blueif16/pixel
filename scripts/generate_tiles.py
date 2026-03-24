"""
Generate floor, wall, and door tiles for Pixel Social.
Run once during development, curate results, upload to S3.
"""

import os
import io
import base64
import requests
from PIL import Image

API_KEY = os.environ.get('OPENAI_API_KEY')
OUTPUT_DIR = 'tiles'

TILES = [
    {'id': 'floor_wood',  'prompt': 'A wooden floor tile, top-down view, warm oak planks, 16-bit pixel art style, pure white background'},
    {'id': 'wall_stone',  'prompt': 'A stone wall tile, front view, gray cobblestone pattern, 16-bit pixel art style, pure white background'},
    {'id': 'door_wood',   'prompt': 'A wooden door tile, front view, arched doorway, 16-bit pixel art style, pure white background'},
]

SIZE = 32


def generate_tile(tile):
    resp = requests.post(
        'https://api.openai.com/v1/images/generations',
        headers={'Authorization': f'Bearer {API_KEY}'},
        json={
            'model': 'dall-e-3',
            'prompt': tile['prompt'],
            'n': 1,
            'size': '1024x1024',
            'response_format': 'b64_json',
            'quality': 'hd',
            'style': 'natural',
        },
        timeout=120,
    )
    resp.raise_for_status()
    b64 = resp.json()['data'][0]['b64_json']
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def remove_white_bg(img, threshold=240):
    img = img.convert('RGBA')
    data = img.getdata()
    new_data = [
        (r, g, b, 0) if r > threshold and g > threshold and b > threshold else (r, g, b, a)
        for r, g, b, a in data
    ]
    img.putdata(new_data)
    return img


def main():
    if not API_KEY:
        raise ValueError('OPENAI_API_KEY environment variable not set')

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for tile in TILES:
        print(f'Generating {tile["id"]}...')
        raw = generate_tile(tile)
        resized = raw.resize((SIZE, SIZE), Image.NEAREST).convert('RGBA')
        resized = remove_white_bg(resized)
        resized.save(os.path.join(OUTPUT_DIR, f'{tile["id"]}.png'))
        print(f'  Saved {tile["id"]}.png')


if __name__ == '__main__':
    main()
