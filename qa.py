#!/usr/bin/env python3
"""Drive the built site in Chrome (Playwright) and check the things that matter.
Usage: python3 qa.py [base_url] [screenshot_dir]"""

import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
SHOTS = (
    sys.argv[2]
    if len(sys.argv) > 2
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa-shots")
)
os.makedirs(SHOTS, exist_ok=True)
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        fails.append(name)


def style(pg, sel, *props):
    return pg.evaluate(
        "([s,p]) => { const e=document.querySelector(s); if(!e) return null; const c=getComputedStyle(e); return Object.fromEntries(p.map(k=>[k,c[k]])); }",
        [sel, list(props)],
    )


def box(pg, sel):
    return pg.evaluate(
        "s => { const r=document.querySelector(s).getBoundingClientRect(); return [r.x,r.y,r.width,r.height].map(v=>Math.round(v*10)/10); }",
        sel,
    )


PROBE = """window.addEventListener('pageswap', e => { try { sessionStorage.setItem('qa:swap', JSON.stringify({vt: !!e.viewTransition, from: location.pathname})); } catch (x) {} });
window.addEventListener('pagereveal', e => { window.__revealed = true; if (!e.viewTransition) { window.__vt = null; return; }
  e.viewTransition.ready.then(() => { window.__vt = { types: Array.from(e.viewTransition.types), anims: document.getAnimations().length, t0: performance.now() }; }).catch(err => { window.__vt = { error: String(err), types: Array.from(e.viewTransition.types) }; });
  e.viewTransition.finished.then(() => { window.__vt && (window.__vt.finished = performance.now()); }); });"""

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(PROBE)
    pg = ctx.new_page()

    # ---- home masthead
    pg.goto(BASE + "/")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=f"{SHOTS}/01-home-masthead.png")
    check(
        "masthead title is brand red",
        style(pg, ".masthead h1", "color")["color"] == "rgb(234, 61, 61)",
    )
    check(
        "masthead subtitle is ink",
        style(pg, ".masthead p", "color")["color"] == "rgb(17, 17, 17)",
    )
    b1, b2 = (
        style(pg, ".masthead-button-1", "backgroundColor", "color"),
        style(pg, ".masthead-button-2", "backgroundColor", "color", "borderColor"),
    )
    check("primary button black", b1["backgroundColor"] == "rgb(17, 17, 17)", str(b1))
    check(
        "secondary button red outline, no fill",
        b2["borderColor"] == "rgb(234, 61, 61)"
        and b2["backgroundColor"] == "rgba(0, 0, 0, 0)",
        str(b2),
    )
    before1, before2 = box(pg, ".masthead-button-1"), box(pg, ".masthead-button-2")
    pg.hover(".masthead-button-1")
    pg.wait_for_timeout(250)
    h1 = style(pg, ".masthead-button-1", "backgroundColor")["backgroundColor"]
    pg.hover(".masthead-button-2")
    pg.wait_for_timeout(250)
    h2 = style(pg, ".masthead-button-2", "backgroundColor", "color")
    pg.screenshot(
        path=f"{SHOTS}/02-home-button2-hover.png",
        clip={"x": 380, "y": 330, "width": 680, "height": 260},
    )
    after1, after2 = box(pg, ".masthead-button-1"), box(pg, ".masthead-button-2")
    check("primary button hover turns red", h1 == "rgb(234, 61, 61)", h1)
    check(
        "secondary button hover fills red",
        h2["backgroundColor"] == "rgb(234, 61, 61)",
        str(h2),
    )
    check(
        "no layout shift on button hover",
        before1 == after1 and before2 == after2,
        f"{before2} -> {after2}",
    )

    # ---- sticky nav + cover hover
    pg.evaluate("window.scrollTo(0,1500)")
    pg.wait_for_timeout(400)
    check("nav sticks to top when scrolled", box(pg, "header.site-header")[1] == 0)
    pg.hover("a.project-cover[href='/ambition-angels/']")
    pg.wait_for_timeout(300)
    ct = style(
        pg,
        "a.project-cover[href='/ambition-angels/'] .title",
        "color",
        "fontSize",
        "textDecorationLine",
    )
    check("cover title red on hover", ct["color"] == "rgb(234, 61, 61)", str(ct))
    pg.screenshot(path=f"{SHOTS}/03-home-cover-hover.png")

    # ---- nav hover + speed
    navsel = "header.site-header nav .page-title a[href='/about/']"
    tr = style(pg, navsel, "transitionDuration", "color")
    check(
        "hover speed is 100ms on nav links",
        tr["transitionDuration"].startswith("0.1s"),
        tr["transitionDuration"],
    )
    pg.hover(navsel)
    pg.wait_for_timeout(200)
    nh = style(pg, navsel, "color", "textDecorationLine")
    check(
        "nav hover is red + strikethrough",
        nh["color"] == "rgb(234, 61, 61)"
        and "line-through" in nh["textDecorationLine"],
        str(nh),
    )
    pg.screenshot(
        path=f"{SHOTS}/04-nav-hover.png",
        clip={"x": 0, "y": 0, "width": 1440, "height": 100},
    )
    same = pg.evaluate(
        "Array.from(document.querySelectorAll('a, .button-module, .project-cover .details')).map(e=>getComputedStyle(e).transitionDuration).filter(d=>d && d!=='0s')"
    )
    check(
        "every hover transition uses the same speed",
        all(d.split(",")[0].strip() == "0.1s" for d in same),
        f"{len(same)} elements, distinct={sorted(set(d.split(',')[0].strip() for d in same))}",
    )

    # ---- nav link: plain cross-fade via view transitions, page usable right after
    pg.goto(BASE + "/ambition-angels/")
    pg.wait_for_timeout(1200)
    pg.click("header.site-header nav .page-title a[href='/about/']", no_wait_after=True)
    pg.wait_for_url("**/about/", timeout=5000)
    pg.wait_for_timeout(800)
    vt = pg.evaluate("window.__vt")
    if not vt:
        print("   note: inbound transition skipped once by the browser, retrying")
        pg.goto(BASE + "/ambition-angels/")
        pg.wait_for_timeout(1200)
        pg.click(
            "header.site-header nav .page-title a[href='/about/']", no_wait_after=True
        )
        pg.wait_for_url("**/about/", timeout=5000)
        pg.wait_for_timeout(800)
        vt = pg.evaluate("window.__vt")
    check(
        "nav link runs a cross-fade transition",
        bool(vt) and vt["anims"] >= 2 and "to-project" not in vt["types"],
        str(vt),
    )
    check(
        "new page is at full opacity afterwards",
        pg.evaluate("getComputedStyle(document.body).opacity") == "1",
    )

    # ---- cover zoom transition (cross-document view transitions) + prefetch
    reqs = []
    pg.on("request", lambda r: reqs.append(r.url))
    pg.goto(BASE + "/")
    pg.wait_for_timeout(1200)
    pg.evaluate("window.scrollTo(0,1500)")
    pg.wait_for_timeout(300)
    pg.hover("a.project-cover[href='/ambition-angels/']")
    pg.wait_for_timeout(700)
    check(
        "hovering a cover prefetches its page",
        any(u.endswith("/ambition-angels/") for u in reqs),
        str([u for u in reqs][-3:]),
    )
    check(
        "hovering a cover preloads its first image",
        any("_rw_1920" in u or "_rw_1200" in u for u in reqs),
    )

    def click_cover():
        pg.click("a.project-cover[href='/ambition-angels/']", no_wait_after=True)
        pg.wait_for_url("**/ambition-angels/")
        pg.wait_for_timeout(2200)
        return pg.evaluate("window.__vt")

    vt = click_cover()
    if not vt:
        # headless Chrome occasionally declines to start the inbound transition (the page then just fades in,
        # which is the designed fallback); retry once before calling it a failure
        print("   note: inbound transition skipped once by the browser, retrying")
        pg.go_back()
        pg.wait_for_url(BASE + "/")
        pg.wait_for_timeout(1200)
        pg.hover("a.project-cover[href='/ambition-angels/']")
        pg.wait_for_timeout(400)
        vt = click_cover()
    check(
        "clicking a cover runs the zoom transition into the project page",
        bool(vt) and "to-project" in vt["types"] and vt["anims"] >= 12,
        str(vt),
    )
    check(
        "zoom transition lasts about 0.75s once the page is loaded",
        bool(vt) and vt.get("finished") and 650 <= vt["finished"] - vt["t0"] <= 1200,
        str(vt and vt.get("finished") and round(vt["finished"] - vt["t0"])) + "ms",
    )
    check(
        "full-size twins are removed after the transition",
        pg.evaluate("document.querySelectorAll('.vt-overlay').length") == 0,
    )
    check(
        "page is scrollable right after the transition",
        pg.evaluate("window.scrollTo(0,500); window.scrollY") == 500,
    )
    check(
        "no double fade after the transition",
        pg.evaluate("getComputedStyle(document.body).opacity") == "1",
    )
    pg.go_back()
    pg.wait_for_url(BASE + "/")
    pg.wait_for_timeout(2200)
    vt = pg.evaluate("window.__vt")
    check(
        "going back zooms out into the thumbnail",
        bool(vt) and "to-home" in vt["types"] and vt["anims"] >= 12,
        str(vt),
    )
    check(
        "zoom-back lasts about 0.75s",
        bool(vt) and vt.get("finished") and 650 <= vt["finished"] - vt["t0"] <= 1100,
        str(vt and vt.get("finished") and round(vt["finished"] - vt["t0"])) + "ms",
    )
    check(
        "thumbnail state is cleaned up afterwards",
        pg.evaluate(
            "document.querySelectorAll('.vt-cover, .touch-hover, .vt-overlay').length"
        )
        == 0,
    )
    pg.hover("a.project-cover[href='/ambition-angels/']")
    pg.wait_for_timeout(300)
    st = pg.evaluate(
        "(()=>{const a=document.querySelector(\"a.project-cover[href='/ambition-angels/']\"); const s=a.querySelector('.title-strike').getBoundingClientRect(); const t=a.querySelector('.title').getBoundingClientRect(); return [Math.round(s.width), Math.round(t.width)]})()"
    )
    check(
        "cover hover draws a strike line across the title text",
        st[0] > 50 and abs(st[0] - st[1]) < 2,
        str(st),
    )
    check(
        "gallery scroll position restored",
        pg.evaluate("window.scrollY") > 300,
        str(pg.evaluate("window.scrollY")),
    )

    # ---- reel button font
    pg.goto(BASE + "/reel/")
    pg.wait_for_timeout(1500)
    ff = style(pg, ".button-module", "fontFamily")["fontFamily"]
    check("reel button uses Proxima Nova", "Proxima Nova" in ff, ff)
    pg.screenshot(path=f"{SHOTS}/05-reel.png")

    # ---- mobile menu
    m = b.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2
    ).new_page()
    m.goto(BASE + "/about/")
    m.wait_for_timeout(1200)
    m.screenshot(path=f"{SHOTS}/06-mobile-about.png")
    m.click(".js-hamburger")
    m.wait_for_timeout(600)
    m.screenshot(path=f"{SHOTS}/07-mobile-menu.png")
    labels = m.evaluate(
        "Array.from(document.querySelectorAll('.responsive-nav nav a')).filter(a=>a.offsetParent!==null).map(a=>[a.textContent.trim(), Math.round(parseFloat(getComputedStyle(a).fontSize)), Math.round(a.getBoundingClientRect().height)])"
    )
    check(
        "mobile menu has 6 rows ending in Email me",
        len(labels) == 6 and labels[-1][0] == "Email me",
        str(labels),
    )
    check(
        "mobile menu labels are big (>=34px) with tall tap targets (>=64px)",
        all(l[1] >= 34 and l[2] >= 64 for l in labels),
        str(labels),
    )
    m.click(".js-close-responsive-nav")
    m.wait_for_timeout(400)
    m.evaluate("window.scrollTo(0,800)")
    m.wait_for_timeout(300)
    check("mobile header sticks", box(m, "header.site-header")[1] == 0)

    # ---- every page: no broken requests, no console errors
    bad, errs = [], []
    pg.on(
        "response",
        lambda r: (
            bad.append(f"{r.status} {r.url}")
            if r.status >= 400 and "google-analytics" not in r.url
            else None
        ),
    )
    pg.on(
        "requestfailed",
        lambda r: (
            bad.append("FAILED " + r.url) if "google-analytics" not in r.url else None
        ),
    )
    pg.on("console", lambda msg: errs.append(msg.text) if msg.type == "error" else None)
    slugs = [
        d
        for d in os.listdir(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
        )
        if os.path.isdir(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", d)
        )
        and d not in ("assets", "css", "js", "dist", "fonts", "site")
    ]
    for s in [""] + sorted(slugs):
        pg.goto(f"{BASE}/{s}/" if s else BASE + "/")
        pg.wait_for_timeout(500)
        pg.evaluate("window.scrollTo(0,document.body.scrollHeight)")
        pg.wait_for_timeout(500)
        noalt = pg.evaluate("document.querySelectorAll('img:not([alt])').length")
        if noalt:
            bad.append(f"{s or '/'}: {noalt} img without alt")
    check(
        f"{len(slugs) + 1} pages load with no broken requests",
        not bad,
        "; ".join(bad[:5]),
    )
    check("no console errors across the site", not errs, "; ".join(errs[:3]))
    b.close()

print(f"\n{len(fails)} failures" if fails else "\nALL CHECKS PASSED")
print("screenshots:", SHOTS)
sys.exit(1 if fails else 0)
