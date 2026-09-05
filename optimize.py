#!/usr/bin/env python3
"""Image and video optimisation for build.py.

Every raster asset becomes a WebP (photos and mockups alike; visually identical at
the quality used, 40 to 90 percent smaller). Animated GIFs become muted looping
MP4 + WebM pairs with a WebP poster. Results are cached in raw/derived/ (git-ignored)
so a rebuild only converts what changed.
"""
import concurrent.futures as cf
import os
import subprocess

from PIL import Image, ImageOps

WEBP_QUALITY = 82
WEBP_METHOD = 4
RASTER = (".jpg", ".jpeg", ".png", ".gif")


def is_animated(path):
    try:
        with Image.open(path) as im:
            return getattr(im, "n_frames", 1) > 1
    except OSError:
        return False


def to_webp(src, dst):
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "transparency" in im.info or im.mode in ("P", "LA") else "RGB")
        im.save(dst + ".part", "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    os.replace(dst + ".part", dst)
    return dst


def poster(src, dst):
    if os.path.exists(dst):
        return dst
    with Image.open(src) as im:
        im.seek(0)
        im.convert("RGB").save(dst, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    return dst


def to_video(src, base):
    """base + .mp4 and base + .webm; returns (mp4, webm, width, height)."""
    mp4, webm = base + ".mp4", base + ".webm"
    even = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    if not os.path.exists(mp4):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", even, "-movflags", "+faststart",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "30", "-preset", "medium", "-an", mp4], check=True)
    if not os.path.exists(webm):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", even, "-pix_fmt", "yuv420p", "-c:v", "libvpx-vp9", "-b:v", "0",
                        "-crf", "36", "-deadline", "good", "-cpu-used", "2", "-row-mt", "1", "-an", webm], check=True)
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", mp4], capture_output=True, text=True, check=True).stdout.strip()
    w, h = (int(x) for x in out.split(","))
    return mp4, webm, w, h


def optimise(assets_dir, cache_dir, names):
    """names: iterable of asset basenames in assets_dir.
    Returns (renames, videos): renames maps an image basename to its .webp basename;
    videos maps an animated gif basename to {mp4, webm, poster, w, h} basenames."""
    os.makedirs(cache_dir, exist_ok=True)
    renames, videos, jobs = {}, {}, []
    for name in names:
        stem, ext = os.path.splitext(name)
        if ext.lower() not in RASTER:
            continue
        src = os.path.join(assets_dir, name)
        if ext.lower() == ".gif" and is_animated(src):
            mp4, webm, w, h = to_video(src, os.path.join(cache_dir, stem))
            post = poster(src, os.path.join(cache_dir, stem + ".webp"))
            videos[name] = {"mp4": os.path.basename(mp4), "webm": os.path.basename(webm), "poster": os.path.basename(post), "w": w, "h": h}
        else:
            jobs.append((src, os.path.join(cache_dir, stem + ".webp")))
            renames[name] = stem + ".webp"
    with cf.ThreadPoolExecutor(max(2, (os.cpu_count() or 4) - 1)) as ex:
        list(ex.map(lambda j: to_webp(*j), jobs))
    return renames, videos
