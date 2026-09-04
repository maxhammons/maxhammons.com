#!/usr/bin/env python3
"""Build the static maxhammons.com site into site/ from:

  raw/            pristine wget mirror of the Adobe Portfolio site (never edited)
  theme/site.css  the design system that overrides the exported Adobe theme
  fonts/          self-hosted Proxima Nova (+ the mono used for code)
  content/pages/  per-page JSON from the review agents: alt text + copy edits

Re-run after any change: `python3 build.py`. site/ is disposable output.
"""
import concurrent.futures as cf
import html as htmlmod
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw")
RAW_SITE = os.path.join(RAW, "maxhammons.com")
RAW_CDN = os.path.join(RAW, "cdn.myportfolio.com")
OUT = os.path.join(ROOT, "site")
ASSETS = os.path.join(OUT, "assets")
FONTS_SRC = os.path.join(ROOT, "fonts")
THEME = os.path.join(ROOT, "theme")
PAGES_JSON = os.path.join(ROOT, "content", "pages")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
CDN_RE = re.compile(r"https://cdn\.myportfolio\.com/[^\s\"'()<>,]+")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TYPEKIT_RE = re.compile(r'<script[^>]*src="//use\.typekit\.net/[^"]+"[^>]*>.*?</script>', re.S)
PAGE_CSS_RE = re.compile(r'<link rel="stylesheet" href="https://cdn\.myportfolio\.com/[^"]+\.css[^"]*" type="text/css" />')
BACK_TO_TOP_RE = re.compile(r'\s*<section class="back-to-top".*?</section>\s*<a class="back-to-top-fixed.*?</a>', re.S)
MOBILE_SOCIAL_RE = re.compile(r'(<div class="js-responsive-nav">.*?)<div class="social pf-nav-social".*?</ul>\s*</div>(.*?</nav>)', re.S)
MOBILE_EMAIL_ROW = '<div class="link-title"><a href="mailto:hello@maxhammons.com">Email me</a></div>'
BFCACHE_RELOAD_RE = re.compile(r"<script type=\"text/javascript\">\s*// fix for Safari.s back/forward cache.*?</script>\s*", re.S)
LONG_INTRO_CHARS = 360
# GitHub Pages refuses sites over 1 GB. Image variants wider than this, and the
# full-size originals the lightbox used, are dropped and every reference is
# pointed at the largest variant that remains (Max, 2026-09-03).
MAX_IMAGE_WIDTH = 2000
VARIANT_RE = re.compile(r"^(" + UUID_RE.pattern + r")(?:_rw_(\d+)|_carw_\d+x\d+x(\d+)|_rwc_\d+x\d+x\d+x\d+x(\d+))?\.([a-z0-9]+)$", re.I)

# The exported theme came as 29 near-identical per-page stylesheets. Four are kept,
# one per page layout; theme/site.css normalises everything on top of them.
ADOBE_CSS = {
    "project": "b012df7cabfe0cec978c916522ebf6d11756239070.css",  # every project page + About
    "home": "90edfce16caeea790f2c620548817fb11756239070.css",     # gallery with masthead GIF
    "sandbox": "eca398eb5b597f83bd44fec129bfb6951756239070.css",  # gallery, no masthead
    "reel": "f8b83a954c68c516c5723a0248b7f8ea1756239070.css",     # splash page with background GIF
}
LAYOUT = {"index": "home", "portfolio": "home", "sandbox": "sandbox", "reel": "reel"}


def cdn_basename(url):
    return os.path.basename(urllib.parse.urlsplit(url).path)


def raw_cdn_path(url):
    parts = urllib.parse.urlsplit(url)
    rel = parts.path.lstrip("/")
    cand = os.path.join(RAW_CDN, rel + ("@" + parts.query if parts.query else ""))
    for c in (cand, cand + ".css", os.path.join(RAW_CDN, rel)):
        if os.path.exists(c):
            return c
    return None


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://maxhammons.com/"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest + ".part", "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(dest + ".part", dest)


def localise(s):
    return CDN_RE.sub(lambda m: "/assets/" + cdn_basename(m.group(0)), s)


def plan_trim(names):
    """Return (dropped:set, remap:{dropped basename -> kept basename}) for the size cap."""
    families = {}
    for n in names:
        m = VARIANT_RE.match(n)
        if not m:
            continue
        uid, ext = m.group(1), m.group(5).lower()
        w = next((int(g) for g in m.groups()[1:4] if g), None)  # None = original
        families.setdefault((uid, ext), []).append((w, n))
    dropped, remap = set(), {}
    for _, variants in families.items():
        keep = [(w, n) for w, n in variants if w is not None and w <= MAX_IMAGE_WIDTH]
        if not keep:
            continue  # nothing small enough to fall back to: keep everything in this family
        best = max(keep)[1]
        for w, n in variants:
            if w is None or w > MAX_IMAGE_WIDTH:
                dropped.add(n)
                remap[n] = best
    return dropped, remap


def apply_trim(s, dropped, remap):
    def fix_srcset(m):
        entries = []
        for e in m.group(2).split(","):
            e = e.strip()
            if e and os.path.basename(e.split()[0]) not in dropped:
                entries.append(e)
        return f'{m.group(1)}="{",".join(entries)}"'
    s = re.sub(r'((?:data-)?srcset)="([^"]*)"', fix_srcset, s)
    return re.sub(r"/assets/([^\s\"'()<>,]+)", lambda m: "/assets/" + remap.get(m.group(1), m.group(1)), s)


def load_content():
    alt, copy = {}, {}
    if not os.path.isdir(PAGES_JSON):
        return alt, copy
    for fn in sorted(os.listdir(PAGES_JSON)):
        if fn.endswith(".json"):
            d = json.load(open(os.path.join(PAGES_JSON, fn), encoding="utf-8"))
            alt.update({k: v.strip() for k, v in d.get("alt", {}).items() if v and v.strip()})
            copy[d.get("slug", fn[:-5])] = d.get("copy", [])
    return alt, copy


def add_alt(s, alt, report):
    def fix(m):
        tag = m.group(0)
        if re.search(r"\salt=", tag):
            return tag
        ids = UUID_RE.findall(tag)
        text = alt.get(ids[0]) if ids else None
        if text is None:
            report["missing"] += 1
            text = ""
        else:
            report["added"] += 1
        text = htmlmod.escape(text, quote=True)
        return tag[:-1].rstrip() + f' alt="{text}">'
    return re.sub(r"<img\b[^>]*>", fix, s, flags=re.S)


def apply_copy(s, edits, slug, report):
    for e in edits:
        find, rep = e.get("find", ""), e.get("replace", "")
        if not find or find == rep:
            continue
        n = s.count(find)
        if n == 0:
            report["copy_failed"].append((slug, find[:60]))
            continue
        s = s.replace(find, rep)
        report["copy_applied"].append((slug, find[:50], rep[:50], e.get("reason", "")))
    return s


def main():
    pages = sorted(f for f in os.listdir(RAW_SITE) if f.endswith(".html"))
    html = {p: open(os.path.join(RAW_SITE, p), encoding="utf-8").read() for p in pages}
    alt, copy = load_content()
    report = {"added": 0, "missing": 0, "copy_applied": [], "copy_failed": [], "long_intros": []}

    # 1. every CDN asset referenced by html or by the kept theme css
    urls = set()
    for s in html.values():
        urls.update(CDN_RE.findall(s))
    urls = {u for u in urls if not urllib.parse.urlsplit(u).path.endswith(".css")}
    css_src = {}
    for name, fn in ADOBE_CSS.items():
        p = [x for x in os.listdir(RAW_CDN + "/4f704c3da73b8f00cf5454392257914f") if x.startswith(fn)][0]
        css_src[name] = open(os.path.join(RAW_CDN, "4f704c3da73b8f00cf5454392257914f", p), encoding="utf-8").read()
        urls.update(CDN_RE.findall(css_src[name]))
    by_name = {}
    for u in urls:
        by_name.setdefault(cdn_basename(u), u)
    dropped, remap = plan_trim(by_name)
    for n in dropped:
        by_name.pop(n, None)

    # 2. site/assets (reuse what is already there or in raw/, download the rest)
    os.makedirs(ASSETS, exist_ok=True)
    for f in os.listdir(ASSETS):
        if f not in by_name:
            os.remove(os.path.join(ASSETS, f))
    todo = []
    for name, u in by_name.items():
        dest = os.path.join(ASSETS, name)
        if os.path.exists(dest):
            continue
        src = raw_cdn_path(u)
        if src:
            shutil.copyfile(src, dest)
        else:
            todo.append((u, dest))
    failed = []
    if todo:
        print(f"downloading {len(todo)} assets")
        with cf.ThreadPoolExecutor(8) as ex:
            futs = {ex.submit(fetch, u, d): u for u, d in todo}
            for f in cf.as_completed(futs):
                try:
                    f.result()
                except Exception as e:  # noqa: BLE001
                    failed.append((futs[f], str(e)))
    for u, e in failed:
        print("FAILED", u, e)

    # 3. css + js + fonts
    for d in ("css", "js", "dist/css", "dist/js", "site"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    shutil.copyfile(os.path.join(THEME, "site.js"), os.path.join(OUT, "js", "site.js"))
    for name, text in css_src.items():
        with open(os.path.join(OUT, "css", f"adobe-{name}.css"), "w", encoding="utf-8") as f:
            f.write(apply_trim(localise(text), dropped, remap))
    shutil.copyfile(os.path.join(THEME, "site.css"), os.path.join(OUT, "css", "site.css"))
    shutil.copyfile(os.path.join(RAW_SITE, "dist", "css", "main.css"), os.path.join(OUT, "dist", "css", "main.css"))
    js = [f for f in os.listdir(os.path.join(RAW_SITE, "dist", "js")) if f.startswith("main.js")][0]
    shutil.copyfile(os.path.join(RAW_SITE, "dist", "js", js), os.path.join(OUT, "dist", "js", "main.js"))
    tr = [f for f in os.listdir(os.path.join(RAW_SITE, "site")) if f.startswith("translations")][0]
    shutil.copyfile(os.path.join(RAW_SITE, "site", tr), os.path.join(OUT, "site", "translations.js"))
    if os.path.isdir(os.path.join(OUT, "fonts")):
        shutil.rmtree(os.path.join(OUT, "fonts"))
    shutil.copytree(FONTS_SRC, os.path.join(OUT, "fonts"))

    # 4. pages
    for d in os.listdir(OUT):
        if os.path.isdir(os.path.join(OUT, d)) and d not in ("assets", "css", "js", "dist", "fonts", "site"):
            shutil.rmtree(os.path.join(OUT, d))
    for p, s in html.items():
        slug = p[:-5]
        if slug == "portfolio":
            continue
        layout = LAYOUT.get(slug, "project")
        s = TYPEKIT_RE.sub("", s)
        s = PAGE_CSS_RE.sub(
            f'<link rel="stylesheet" href="/css/adobe-{layout}.css" type="text/css" />\n'
            f'    <link rel="stylesheet" href="/css/site.css" type="text/css" />', s)
        s = apply_trim(localise(s), dropped, remap)
        s = re.sub(r'src="/dist/js/main\.js\?cb=[0-9a-f]+"', 'src="/dist/js/main.js"', s)
        s = re.sub(r'src="/site/translations\?cb=[0-9a-f]+"', 'src="/site/translations.js"', s)
        s = s.replace('<html class="', '<html class="wf-active ').replace("<html>", '<html class="wf-active">')
        s = BACK_TO_TOP_RE.sub("\n", s)
        s = MOBILE_SOCIAL_RE.sub(lambda m: m.group(1) + MOBILE_EMAIL_ROW + m.group(2), s, count=1)
        s = BFCACHE_RELOAD_RE.sub("", s)
        s = s.replace('<script type="text/javascript" src="/dist/js/main.js"></script>',
                      '<script type="text/javascript" src="/dist/js/main.js"></script>\n  <script src="/js/site.js"></script>')
        # internal links: /slug -> /slug/ (no redirect hop on GitHub Pages), /portfolio -> / (one canonical home)
        s = re.sub(r'href="/portfolio"', 'href="/"', s)
        s = re.sub(r'href="/([a-z0-9-]+)"', lambda m: f'href="/{m.group(1)}/"' if m.group(1) + ".html" in html else m.group(0), s)
        s = s.replace('<link rel="canonical" href="https://maxhammons.com/portfolio" />', '<link rel="canonical" href="https://maxhammons.com/" />')
        m = re.search(r'<p class="description">(.*?)</p>', s, re.S)
        if m and len(re.sub(r"<[^>]+>", "", m.group(1)).strip()) > LONG_INTRO_CHARS:
            s = s.replace('<header class="page-header content"', '<header class="page-header content is-long"', 1)
            report["long_intros"].append(slug)
        s = apply_copy(s, copy.get(slug, []), slug, report)
        s = add_alt(s, alt, report)
        targets = [os.path.join(OUT, "index.html"), os.path.join(OUT, "portfolio", "index.html")] if slug == "index" \
            else [os.path.join(OUT, slug, "index.html")]
        for t in targets:
            os.makedirs(os.path.dirname(t), exist_ok=True)
            with open(t, "w", encoding="utf-8") as f:
                f.write(s)

    # 5. GitHub Pages plumbing
    open(os.path.join(OUT, "CNAME"), "w").write("maxhammons.com\n")
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    shutil.copyfile(os.path.join(OUT, "index.html"), os.path.join(OUT, "404.html"))

    # 6. report
    left = 0
    for dp, _, fns in os.walk(OUT):
        for fn in fns:
            if fn.endswith((".html", ".css")):
                t = open(os.path.join(dp, fn), encoding="utf-8", errors="ignore").read()
                left += len(CDN_RE.findall(t)) + t.count("use.typekit.net")
    total = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fns in os.walk(OUT) for fn in fns)
    print(f"images: {len(dropped)} variants over {MAX_IMAGE_WIDTH}px or originals dropped, {len(by_name)} kept; site/ is {total / 1e6:.0f} MB")
    print(f"alt text: {report['added']} added, {report['missing']} images with no text yet")
    print(f"copy edits: {len(report['copy_applied'])} applied, {len(report['copy_failed'])} failed")
    for slug, find in report["copy_failed"]:
        print(f"  FAILED {slug}: {find!r}")
    print(f"two-column intros: {len(report['long_intros'])} ({', '.join(report['long_intros'])})")
    print("remaining external cdn/typekit refs:", left)
    with open(os.path.join(ROOT, "content", "copy-changelog.md"), "w", encoding="utf-8") as f:
        f.write("# Copy edits applied by build.py\n\n")
        for slug, a, b, why in report["copy_applied"]:
            f.write(f"- **{slug}**: `{a}` → `{b}` ({why})\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
