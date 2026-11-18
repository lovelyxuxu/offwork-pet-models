"""Turn a locked-camera action video into pack-ready transparent HD frames.

Pipeline: ffmpeg extract -> background-model matte the plain gradient -> align
feet/size to the idle reference bbox -> emit 768x832 frames + an action snippet
(animation/action/menu) for merging into behavior.json.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

CELL = (768, 832)


def matte(rgb, thresh=30):
    a = np.asarray(rgb).astype(float)
    H, W, _ = a.shape
    # background is a smooth static gradient: model it per row from the frame
    # sides (character never covers both), interpolating across the width
    m = max(2, W // 50)
    left = np.median(a[:, :m], axis=1)
    right = np.median(a[:, -m:], axis=1)
    bad_l = left.mean(-1) < 150
    bad_r = right.mean(-1) < 150
    left[bad_l] = right[bad_l]
    right[bad_r] = left[bad_r]
    t = np.linspace(0, 1, W)[None, :, None]
    bg = left[:, None, :] * (1 - t) + right[:, None, :] * t
    dist = np.sqrt(((a - bg) ** 2).sum(-1))
    lab, n = ndimage.label(dist < thresh)
    ids = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    ids.discard(0)
    mask = np.isin(lab, sorted(ids))
    # see-through gaps match the local background exactly; character whites and
    # rim-lights are brighter (mean dist > 12) and stay opaque
    sizes = np.bincount(lab.ravel())
    means = ndimage.mean(dist, lab, index=np.arange(1, n + 1))
    pockets = [i for i in range(1, n + 1)
               if i not in ids and 150 <= sizes[i] <= 10000 and means[i - 1] < 8]
    mask |= np.isin(lab, pockets)
    # ground contact shadow hugs the feet and is not background-connected;
    # key it out by low chroma + light value in the bottom band (feet stay: high chroma)
    chroma = a.max(-1) - a.min(-1)
    band = np.zeros_like(mask)
    band[int(H * 0.90):, :] = True
    mask |= band & (chroma < 45) & (a.mean(-1) > 140)
    alpha = Image.fromarray(np.where(mask, 0, 255).astype('uint8'))
    out = rgb.convert('RGBA')
    out.putalpha(alpha)
    return out


def bbox(image):
    return image.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--order', type=int, required=True)
    parser.add_argument('--fps', type=int, default=10)
    parser.add_argument('--idle-strip', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    raw = args.out / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-y', '-i', str(args.video), '-vf', f'fps={args.fps}',
                    str(raw / '%03d.png')], check=True, capture_output=True)

    idle = Image.open(args.idle_strip).convert('RGBA').crop((0, 0, *CELL))
    ix0, iy0, ix1, iy1 = bbox(idle)
    target_h = iy1 - iy0
    target_cx = (ix0 + ix1) / 2
    target_bottom = iy1

    assets = args.source / 'assets' / 'actions' / args.id
    assets.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, path in enumerate(sorted(raw.glob('*.png'))):
        rgba = matte(Image.open(path).convert('RGB'))
        box = bbox(rgba)
        if not box:
            continue
        char = rgba.crop(box)
        scale = target_h / char.height
        char = char.resize((max(1, round(char.width * scale)), target_h), Image.LANCZOS)
        canvas = Image.new('RGBA', CELL, (0, 0, 0, 0))
        canvas.paste(char, (round(target_cx - char.width / 2), target_bottom - char.height), char)
        name = f'{i:03d}.webp'
        canvas.save(assets / name, quality=90)
        frames.append({'file': f'assets/actions/{args.id}/{name}', 'rect': [0, 0, *CELL],
                       'durationMs': round(1000 / args.fps)})

    snippet = {
        'animation': {args.id: {'loop': False, 'frames': frames}},
        'action': {args.id: {'animation': args.id, 'priority': 10, 'interruptible': True,
                            'onBusy': 'enqueue', 'queueTtlMs': 3000, 'cooldownMs': 800,
                            'after': {'type': 'return'}}},
        'menu': {'id': args.id, 'label': args.label, 'order': args.order,
                 'invoke': {'type': 'action', 'id': args.id}},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'snippet.json').write_text(json.dumps(snippet, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{args.id}: {len(frames)} frames -> {assets}')


if __name__ == '__main__':
    main()