"""Turn a script into a 1080x1920 MP4: one text card per scene, stitched with ffmpeg."""
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
PALETTES = {  # (top, bottom) gradient per niche
    "fmcg_distribution": ((14, 42, 71), (30, 120, 135)),
    "fast_food": ((120, 24, 24), (225, 120, 35)),
    "cafe": ((48, 32, 24), (170, 120, 80)),
}
DEFAULT_PALETTE = ((25, 25, 45), (70, 90, 160))
FONT_CANDIDATES = [
    "assets/fonts/bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _gradient(top, bottom) -> Image.Image:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)))
    return img


def _wrap(draw, text, font, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def _card(text, palette, brand, progress, big=True) -> Image.Image:
    img = _gradient(*palette)
    d = ImageDraw.Draw(img)
    max_w, max_h = 880, 1000
    size = 104 if big else 72
    while True:
        font = _font(size)
        lines = _wrap(d, text, font, max_w)
        line_h = int(size * 1.25)
        if len(lines) * line_h <= max_h or size <= 52:
            break
        size -= 4
    y = (H - len(lines) * line_h) // 2
    for line in lines:
        x = (W - d.textlength(line, font=font)) // 2
        d.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0))
        d.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_h
    d.rectangle([0, 0, int(W * progress), 14], fill=(255, 255, 255))  # progress bar
    small = _font(42)
    d.text(((W - d.textlength(brand, font=small)) // 2, H - 170), brand, font=small, fill=(235, 235, 235))
    return img


def make_video(script: dict, cfg: dict, niche: str, out_path: Path) -> Path:
    palette = PALETTES.get(niche, DEFAULT_PALETTE)
    brand = cfg["brand"]["name"]
    cards = [(s["text"], float(s["seconds"])) for s in script["scenes"]]
    cta = cfg["brand"]["cta"]
    if cfg["brand"].get("website"):
        cta += f"\n{cfg['brand']['website']}"
    cards.append((cta.replace("\n", " "), 4.0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    music = Path("assets/music.mp3")  # optional; use royalty-free audio you have the rights to
    with tempfile.TemporaryDirectory() as tmp:
        pngs = []
        for i, (text, _) in enumerate(cards):
            p = os.path.join(tmp, f"{i:02d}.png")
            _card(text, palette, brand, (i + 1) / len(cards), big=i < len(cards) - 1).save(p)
            pngs.append(p)

        total = sum(sec for _, sec in cards)
        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        for p, (_, sec) in zip(pngs, cards):
            cmd += ["-loop", "1", "-t", f"{sec:.2f}", "-i", p]
        n = len(pngs)
        graph = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps=30,format=yuv420p[v]"
        if music.exists():
            cmd += ["-stream_loop", "-1", "-i", str(music)]
            graph += f";[{n}:a]volume=0.25,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[a]"
            audio_map = "[a]"
        else:  # silent track so every platform accepts the file
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
            audio_map = f"{n}:a"
        cmd += [
            "-filter_complex", graph, "-map", "[v]", "-map", audio_map,
            "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)
    return out_path
