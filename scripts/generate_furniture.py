"""
Generate furniture sprites for Pixel Social.
Run once during development, curate results, upload to S3.
"""

import os
import io
import base64
import requests
from PIL import Image

API_KEY = os.environ.get('OPENAI_API_KEY')
OUTPUT_DIR = 'furniture'

FURNITURE = [
    {'itemId': 'chair_wood_01',   'name': 'small wooden chair',                'w': 32, 'h': 32},
    {'itemId': 'sofa_blue_01',    'name': 'blue two-seat sofa',                'w': 64, 'h': 32},
    {'itemId': 'table_round_01',  'name': 'small round wooden table',           'w': 32, 'h': 32},
    {'itemId': 'rug_red_01',      'name': 'red woven area rug',                'w': 64, 'h': 64},
    {'itemId': 'lamp_tall_01',    'name': 'tall standing floor lamp',          'w': 32, 'h': 32},
    {'itemId': 'bookshelf_01',    'name': 'wide wooden bookshelf full of colorful books', 'w': 64, 'h': 32},
]

PROMPT_TEMPLATE = """A single {name} sprite for a pixel art game in the Stardew Valley style.
Viewed from a 3/4 top-down isometric perspective. Pure white background.
{w}x{h} pixels. 16-bit pixel art, clean pixel edges, no anti-aliasing,
no text, no labels, no shadow, no floor."""


def generate_furniture_item(item):
    prompt = PROMPT_TEMPLATE.format(
        name=item['name'],
        w=item['w'],
        h=item['h'],
    )
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

    for item in FURNITURE:
        print(f'Generating {item["itemId"]}...')
        raw = generate_furniture_item(item)
        resized = raw.resize((item['w'], item['h']), Image.NEAREST).convert('RGBA')
        resized = remove_white_bg(resized)
        resized.save(os.path.join(OUTPUT_DIR, f'{item["itemId"]}.png'))
        print(f'  Saved {item["itemId"]}.png')


if __name__ == '__main__':
    main()
