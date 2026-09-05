#!/usr/bin/env python3
"""Emit content/manifest/<slug>.json for every page: the page's text (verbatim
HTML snippets, so copy edits can be exact find/replace) and its images in
document order with a small local file agents can look at."""

import html
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_SITE = os.path.join(ROOT, "raw", "maxhammons.com")
ASSETS = os.path.join(ROOT, "site", "assets")
OUT = os.path.join(ROOT, "content", "manifest")
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
have = os.listdir(ASSETS)


def small_variant(uid):
    c = [f for f in have if f.startswith(uid) and re.search(r"(_rw_600|x640)\.", f)]
    return os.path.join(ASSETS, sorted(c)[0]) if c else None


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).split()


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in sorted(os.listdir(RAW_SITE)):
        if not fn.endswith(".html") or fn == "portfolio.html":
            continue
        slug = fn[:-5]
        s = open(os.path.join(RAW_SITE, fn), encoding="utf-8").read()
        body = s[s.find("<main") :]
        m = {
            "slug": slug,
            "url": f"https://maxhammons.com/{slug if slug != 'index' else ''}",
            "texts": [],
            "images": [],
        }
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        m["page_title_tag"] = html.unescape(t.group(1).strip()) if t else ""
        d = re.search(r'<meta name="description" content="([^"]*)"', s)
        m["meta_description"] = html.unescape(d.group(1)) if d else ""
        # text blocks, in order: page header title/description, masthead, text modules, cover titles
        for kind, pat in [
            ("title", r'<h1 class="title[^"]*">(.*?)</h1>'),
            ("description", r'<p class="description">(.*?)</p>'),
            (
                "masthead",
                r'<(?:h1|p)[^>]*class="[^"]*main-text[^"]*"[^>]*>(.*?)</(?:h1|p)>',
            ),
            ("masthead_button", r'class="masthead-button[^"]*">(.*?)</a>'),
            ("text_module", r'<div class="rich-text[^"]*">(.*?)</div>\s*</div>'),
            ("cover_title", r'<div class="title preserve-whitespace">(.*?)</div>'),
            ("button", r'class="button-module[^"]*">(.*?)</a>'),
            ("footer", r'<div class="footer-text">\s*(.*?)\s*</div>'),
        ]:
            for mm in re.finditer(pat, body, re.S):
                raw = mm.group(1)
                if strip_tags(raw):
                    m["texts"].append(
                        {"kind": kind, "html": raw, "plain": " ".join(strip_tags(raw))}
                    )
        # images in order, deduped by id, with nearest preceding text for context
        seen = set()
        for mm in re.finditer(r"<img[^>]*>", body, re.S):
            tag = mm.group(0)
            ids = re.findall(UUID, tag)
            if not ids or ids[0] in seen:
                continue
            uid = ids[0]
            seen.add(uid)
            before = body[: mm.start()]
            ctx = re.findall(r'<div class="rich-text[^"]*">(.*?)</div>', before, re.S)
            cover = re.search(
                r'<a class="project-cover[^>]*href="([^"]+)"[^>]*>(?:(?!</a>).)*$',
                before,
                re.S,
            )
            m["images"].append(
                {
                    "id": uid,
                    "file": small_variant(uid),
                    "preceding_text": " ".join(strip_tags(ctx[-1]))[:300]
                    if ctx
                    else "",
                    "cover_link": cover.group(1) if cover else None,
                }
            )
        with open(os.path.join(OUT, slug + ".json"), "w", encoding="utf-8") as f:
            json.dump(m, f, indent=1, ensure_ascii=False)
        print(f"{slug:36} texts={len(m['texts']):3} images={len(m['images']):3}")


if __name__ == "__main__":
    main()
