#!/usr/bin/env python3
"""Image optimisation for build.py.

Every raster asset becomes a WebP (photos and mockups alike; visually identical at
the quality used, 40 to 90 percent smaller). Animated GIFs become animated WebP,
which plays everywhere a GIF does (including as a CSS background) at a quarter of
the size and in full colour. Results are cached (git-ignored) so a rebuild only
converts what is missing.
"""

import base64
import concurrent.futures as cf
import io
import os

from PIL import Image, ImageFile, ImageOps, ImageSequence

# a few CDN JPEGs end a couple of bytes short of what Pillow expects; they decode fine
ImageFile.LOAD_TRUNCATED_IMAGES = True

WEBP_QUALITY = 82
ANIMATED_QUALITY = 65  # photo slideshows keep their look; UI recordings stay crisp
WEBP_METHOD = 4
RASTER = (".jpg", ".jpeg", ".png", ".gif")
PLACEHOLDER_PX = 16  # longest side of an image's low-res preview; the page scales it up behind a blur
PLACEHOLDER_QUALITY = 50


def placeholder(path, cache):
    """Data URI of a tiny WebP copy of an image, the source of its blurred preview.
    cache maps file name -> data URI; the caller loads and saves it."""
    name = os.path.basename(path)
    if name not in cache:
        with Image.open(path) as im:
            im = im.convert("RGB")  # an animation's first frame
            im.thumbnail((PLACEHOLDER_PX, PLACEHOLDER_PX))
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=PLACEHOLDER_QUALITY)
        cache[name] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    return cache[name]


def is_animated(path):
    try:
        with Image.open(path) as im:
            return getattr(im, "n_frames", 1) > 1
    except OSError:
        return False


def to_webp(src, dst):
    if (
        os.path.exists(dst) and os.path.getsize(dst) > 0
    ):  # originals never change; the cache is by name
        return dst
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert(
                "RGBA" if "transparency" in im.info or im.mode in ("P", "LA") else "RGB"
            )
        im.save(dst + ".part", "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    os.replace(dst + ".part", dst)
    return dst


def to_animated_webp(src, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return dst
    with Image.open(src) as im:
        frames, durations = [], []
        for frame in ImageSequence.Iterator(im):
            frames.append(frame.convert("RGB"))
            durations.append(frame.info.get("duration", 100))
    frames[0].save(
        dst + ".part",
        "WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        quality=ANIMATED_QUALITY,
        method=WEBP_METHOD,
    )
    os.replace(dst + ".part", dst)
    return dst


def optimise(sources, cache_dir):
    """sources: {asset basename: path of the original (or None if unavailable)}.
    Returns renames: image basename -> its .webp basename."""
    os.makedirs(cache_dir, exist_ok=True)
    renames, jobs = {}, []
    for name, src in sources.items():
        stem, ext = os.path.splitext(name)
        if ext.lower() not in RASTER or not src:
            continue
        convert = (
            to_animated_webp if ext.lower() == ".gif" and is_animated(src) else to_webp
        )
        jobs.append((convert, src, os.path.join(cache_dir, stem + ".webp")))
        renames[name] = stem + ".webp"
    with cf.ThreadPoolExecutor(max(2, (os.cpu_count() or 4) - 1)) as ex:
        list(ex.map(lambda j: j[0](j[1], j[2]), jobs))
    return renames
