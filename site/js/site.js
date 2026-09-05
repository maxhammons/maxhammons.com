/* maxhammons.com behaviour on top of the exported Adobe bundle. Loaded in <head>, before
   the first render, so the pagereveal listener is in place when a view transition starts.

   1. Cover zoom (cross-document View Transitions). Clicking a gallery thumbnail: the
      image, its white panel, the red title and the strike line grow to fill the screen
      (the project page builds full-size twins of them, so the browser interpolates the
      geometry and the title ends up as crisp text). Once the project page underneath has
      loaded, the strike erases like a progress bar and everything fades off together.
      Going back (logo, Home, back button, swipe) plays the exact reverse into the thumbnail.
   2. Plain page fade for browsers without view transitions.
   3. Prefetch: a project page and its first image start loading on hover / touch. */
(function () {
  var FADE = 250; // ms, matches .transition-out in dist/css/main.css
  var VT = "onpagereveal" in window && "CSSViewTransitionRule" in window;
  var html = document.documentElement;
  var lastCover = null;
  var NAMES = {
    image: "cover-image",
    panel: "cover-panel",
    title: "cover-title",
    strike: "cover-strike",
  };
  if (VT) html.classList.add("vt-ready"); // CSS: the Adobe click fade-out must not run, or the capture is blank

  /* sessionStorage can be missing or locked (private mode); the zoom then simply degrades to a fade */
  function storage(op, key, value) {
    try {
      if (op === "set") sessionStorage.setItem(key, JSON.stringify(value));
      else if (op === "remove") sessionStorage.removeItem(key);
      else return JSON.parse(sessionStorage.getItem(key) || "null");
    } catch (err) {
      return null;
    }
    return null;
  }
  function store(key, value) {
    storage("set", key, value);
  }
  function load(key) {
    return storage("get", key);
  }
  function forget(key) {
    storage("remove", key);
  }

  /* ---- gallery side: the thumbnail parts ---- */
  function coverParts(cover) {
    return {
      image: cover.querySelector(".cover"),
      panel: cover.querySelector(".cover-panel"),
      title: cover.querySelector(".details .title"),
      strike: cover.querySelector(".details .title-strike"),
    };
  }
  function coverInfo(cover) {
    var img = cover.querySelector("img");
    var r = cover.getBoundingClientRect();
    var t = cover.querySelector(".details .title-text");
    return {
      src: img ? img.currentSrc || img.src : "",
      w: r.width,
      h: r.height,
      title: t ? t.textContent : "",
    };
  }
  function markCover(cover, on) {
    var p = coverParts(cover);
    Object.keys(NAMES).forEach(function (key) {
      if (p[key]) p[key].style.viewTransitionName = on ? NAMES[key] : "";
    });
    cover.classList.toggle("touch-hover", !!on); // shows the panel, title and strike so they are captured
    cover.classList.toggle("vt-cover", !!on);
  }
  function rememberCovers() {
    var map = {};
    Array.prototype.forEach.call(document.querySelectorAll("a.project-cover[href]"), function (c) {
      map[c.getAttribute("href")] = coverInfo(c);
    });
    if (Object.keys(map).length) store("mh:covers", map);
  }

  /* ---- project side: full-screen twins of the thumbnail parts ---- */
  function buildOverlay(info) {
    var k = Math.max(window.innerWidth / info.w, window.innerHeight / info.h);
    var o = document.createElement("div");
    o.className = "vt-overlay";
    o.setAttribute("aria-hidden", "true");
    var img = document.createElement("img");
    img.className = "vt-image";
    img.alt = "";
    img.src = info.src;
    img.style.viewTransitionName = NAMES.image;
    var panel = document.createElement("div");
    panel.className = "vt-panel";
    panel.style.viewTransitionName = NAMES.panel;
    var title = document.createElement("div");
    title.className = "vt-title";
    title.textContent = info.title;
    title.style.fontSize = 24 * k + "px";
    title.style.lineHeight = 28 * k + "px";
    title.style.viewTransitionName = NAMES.title;
    var strike = document.createElement("span");
    strike.className = "vt-strike";
    strike.style.viewTransitionName = NAMES.strike;
    title.appendChild(strike);
    o.appendChild(img);
    o.appendChild(panel);
    o.appendChild(title);
    document.body.appendChild(o);
    return o;
  }
  function removeOverlay() {
    Array.prototype.forEach.call(document.querySelectorAll(".vt-overlay"), function (o) {
      o.parentNode.removeChild(o);
    });
  }

  /* to-project: the beats after the zoom wait until the project page underneath has loaded */
  function releaseWhenLoaded(minMs, capMs) {
    var start = performance.now();
    function firstImageReady() {
      var img = document.querySelector(".project-module-image img, .grid__item-container img");
      if (!img) return true;
      var src = img.currentSrc || img.src || "";
      return img.complete && img.naturalWidth > 0 && src.indexOf("data:") !== 0;
    }
    (function tick() {
      var t = performance.now() - start;
      var done = document.readyState === "complete" && firstImageReady();
      if ((t >= minMs && done) || t >= capMs) html.classList.add("vt-loaded");
      else setTimeout(tick, 40);
    })();
  }
  function armSkip(vt) {
    var skip = function () {
      vt.skipTransition(); // a no-op once the transition has finished
    };
    ["wheel", "touchmove", "keydown", "pointerdown"].forEach(function (ev) {
      window.addEventListener(ev, skip, { once: true, passive: true });
    });
  }
  function timeScale() {
    return parseFloat(getComputedStyle(html).getPropertyValue("--vt-t")) || 1;
  }

  document.addEventListener(
    "click",
    function (e) {
      var a = e.target.closest && e.target.closest("a.project-cover[href]");
      if (a && e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey)
        lastCover = a;
    },
    true,
  );

  if (VT) {
    /* leaving a gallery: only a click on a thumbnail zooms; masthead buttons and nav links fade */
    function swapFromGallery() {
      var cover = lastCover;
      if (!cover) return false;
      markCover(cover, true);
      var info = coverInfo(cover);
      info.to = cover.getAttribute("href");
      info.at = Date.now();
      store("mh:zoom", info);
      return true;
    }
    /* leaving a project page for a gallery: the old side of the zoom-out is the full-screen overlay */
    function swapFromProject(to) {
      var mine = (load("mh:covers") || {})[location.pathname];
      var back = !!to && /^\/(portfolio\/|sandbox\/)?$/.test(to);
      if (!mine || !back) return false;
      buildOverlay(mine);
      return true;
    }
    function destinationOf(e) {
      var entry = e.activation && e.activation.entry;
      return entry && entry.url ? new URL(entry.url).pathname : null;
    }

    window.addEventListener("pageswap", function (e) {
      var gallery = !!document.querySelector("a.project-cover");
      // a project page remembers itself so the gallery knows which thumbnail to zoom back into
      if (gallery) forget("mh:from");
      else store("mh:from", location.pathname);
      if (gallery) rememberCovers();
      if (!e.viewTransition) return;
      var zooming = gallery ? swapFromGallery() : swapFromProject(destinationOf(e));
      if (!zooming) forget("mh:zoom");
      e.viewTransition.types.add(zooming ? (gallery ? "to-project" : "to-home") : "fade");
    });

    /* the thumbnail click handoff, if it is for this page and fresh (an aborted navigation leaves a stale one) */
    function zoomHandoff() {
      var zoom = load("mh:zoom");
      forget("mh:zoom");
      var fresh = zoom && Date.now() - (zoom.at || 0) < 8000;
      return fresh && zoom.to === location.pathname && !document.querySelector("a.project-cover")
        ? zoom
        : null;
    }
    /* arriving on a project page from a thumbnail: build the full-size twins, run the zoom */
    function revealProject(vt, zoom) {
      buildOverlay(zoom);
      vt.finished.then(removeOverlay);
      releaseWhenLoaded(550 * timeScale(), 550 * timeScale() + 3000);
    }
    /* back on a gallery: the thumbnail we came from is the new side of the zoom-out */
    function coverWeCameFrom() {
      var act = window.navigation && navigation.activation;
      var prev = act && act.from && act.from.url ? new URL(act.from.url).pathname : load("mh:from");
      return prev && document.querySelector('a.project-cover[href="' + prev + '"]');
    }
    function revealGallery(vt, cover) {
      var r = cover.getBoundingClientRect();
      if (r.top < 0 || r.bottom > window.innerHeight)
        cover.scrollIntoView({ block: "center", behavior: "instant" });
      markCover(cover, true);
      vt.finished.then(function () {
        markCover(cover, false);
      });
    }

    window.addEventListener("pagereveal", function (e) {
      var vt = e.viewTransition;
      removeOverlay();
      Array.prototype.forEach.call(document.querySelectorAll(".vt-cover"), function (c) {
        markCover(c, false);
      });
      if (!vt) return;
      html.classList.add("vt"); // neutralises the Adobe body fade for this page load
      if (document.body) document.body.classList.remove("transition-enabled");
      armSkip(vt);
      var zoom = zoomHandoff();
      var cover = zoom ? null : coverWeCameFrom();
      if (zoom) revealProject(vt, zoom);
      else if (cover) revealGallery(vt, cover);
      vt.types.add(zoom ? "to-project" : cover ? "to-home" : "fade");
    });
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", rememberCovers);
    else rememberCovers();
  }

  /* ---- fallback page fade (no view transitions) ---- */
  document.addEventListener(
    "click",
    function (e) {
      if (
        VT ||
        e.defaultPrevented ||
        e.button !== 0 ||
        e.metaKey ||
        e.ctrlKey ||
        e.shiftKey ||
        e.altKey
      )
        return;
      var a = e.target.closest && e.target.closest("a[href]");
      if (!a) return;
      var href = a.getAttribute("href");
      if (
        !href ||
        href.charAt(0) === "#" ||
        a.target ||
        a.hasAttribute("download") ||
        a.hasAttribute("data-bypass")
      )
        return;
      if (/^(mailto|tel|javascript):/i.test(href)) return;
      if (a.host !== location.host || a.pathname === location.pathname) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      document.body.classList.add("transition-out");
      setTimeout(function () {
        location.href = a.href;
      }, FADE);
    },
    true,
  );
  window.addEventListener("pageshow", function () {
    document.body.classList.remove("transition-out");
  });

  /* ---- videos that replaced animated GIFs: nudge autoplay in case the browser held it back ---- */
  function playVideos() {
    Array.prototype.forEach.call(document.querySelectorAll("video[autoplay]"), function (v) {
      var p = v.play();
      if (p && p.catch) p.catch(function () { /* autoplay blocked (low-power mode): the poster stays */ });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", playVideos);
  else playVideos();

  /* ---- prefetch on intent: the page HTML and its first image ---- */
  var warmed = {};
  function warm(a) {
    var href = a.href;
    if (!href || warmed[href] || a.host !== location.host) return;
    warmed[href] = true;
    fetch(href, { credentials: "same-origin", priority: "low" }).catch(function () {
      warmed[href] = false; // offline or blocked: let a later hover try again
    });
    var img = a.getAttribute("data-preload");
    if (img) {
      var i = new Image();
      i.src = img;
    }
  }
  ["mouseenter", "touchstart", "focus"].forEach(function (ev) {
    document.addEventListener(
      ev,
      function (e) {
        var a = e.target.closest && e.target.closest("a.project-cover[href], nav a[href]");
        if (a) warm(a);
      },
      { capture: true, passive: true },
    );
  });
})();
