/* maxhammons.com behaviour on top of the exported Adobe bundle.
   1. Cover zoom: clicking a gallery thumbnail zooms it up to fill the screen, the
      image fades to white, the title un-strikes and collapses, the panel drops away
      and the project page is underneath. Going back plays it in reverse into the
      thumbnail. Built on cross-document View Transitions; browsers without them get
      the plain page fade in (2).
   2. Page fade for browsers without view transitions, independent of network speed.
   3. Prefetch: a project page and its first image start loading on hover / touch. */
(function () {
  var FADE = 250;             // ms, matches .transition-out in dist/css/main.css
  var VT = 'onpagereveal' in window && 'CSSViewTransitionRule' in window;
  var html = document.documentElement;
  var lastCover = null;
  if (VT) html.classList.add('vt-ready');   // CSS: the Adobe click fade-out must not run, or the capture is blank

  function coverParts(cover) {
    return {
      image: cover.querySelector('.cover'),
      panel: cover.querySelector('.cover-panel'),
      title: cover.querySelector('.details .title'),
      plain: cover.querySelector('.details .title-ghost')
    };
  }

  function name(cover, on) {
    var p = coverParts(cover);
    var names = { image: 'cover-image', panel: 'cover-panel', title: 'cover-title', plain: 'cover-title-plain' };
    Object.keys(names).forEach(function (k) {
      if (p[k]) p[k].style.viewTransitionName = on ? names[k] : '';
    });
    cover.classList.toggle('touch-hover', !!on);   // shows the panel + title so they are captured
    cover.classList.toggle('vt-cover', !!on);
  }

  /* target transform for each part: scale the whole cover by k about its centre, moved to the viewport centre */
  function zoomTransforms(cover) {
    var p = coverParts(cover);
    var c = cover.getBoundingClientRect();
    var vw = window.innerWidth, vh = window.innerHeight;
    var k = Math.max(vw / c.width, vh / c.height);
    var cx = c.left + c.width / 2, cy = c.top + c.height / 2;
    var out = { k: k };
    ['image', 'panel', 'title', 'plain'].forEach(function (key) {
      if (!p[key]) return;
      var r = p[key].getBoundingClientRect();
      var x = vw / 2 + k * (r.left - cx), y = vh / 2 + k * (r.top - cy);
      out[key] = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px) scale(' + k.toFixed(4) + ')';
    });
    return out;
  }

  function setVars(t) {
    ['image', 'panel', 'title', 'plain'].forEach(function (key) {
      if (t[key]) html.style.setProperty('--vt-' + key, t[key]);
    });
  }

  function armSkip(vt) {
    var skip = function () { try { vt.skipTransition(); } catch (e) {} };
    ['wheel', 'touchmove', 'keydown', 'pointerdown'].forEach(function (ev) {
      window.addEventListener(ev, skip, { once: true, passive: true });
    });
  }

  /* ---- outbound: remember which cover was clicked and capture it in its hover state ---- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a.project-cover[href]');
    if (a && e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) lastCover = a;
  }, true);

  if (VT) {
    window.addEventListener('pageswap', function (e) {
      if (!e.viewTransition) return;
      var to = e.activation && e.activation.entry && e.activation.entry.url;
      var cover = lastCover;
      if (!cover && to) cover = document.querySelector('a.project-cover[href="' + new URL(to).pathname + '"]');
      if (cover) {
        name(cover, true);
        var t = zoomTransforms(cover);
        t.to = cover.getAttribute('href');
        t.from = location.pathname;
        t.at = Date.now();
        try { sessionStorage.setItem('mh:zoom', JSON.stringify(t)); } catch (err) {}
        e.viewTransition.types.add('to-project');
      } else {
        try { sessionStorage.removeItem('mh:zoom'); } catch (err) {}
        e.viewTransition.types.add('fade');
      }
    });

    window.addEventListener('pagereveal', function (e) {
      var vt = e.viewTransition;
      // a cover left marked by an aborted navigation must not keep its overlay or its names
      Array.prototype.forEach.call(document.querySelectorAll('.vt-cover'), function (c) { name(c, false); });
      if (!vt) return;
      html.classList.add('vt');                       // neutralises the Adobe body fade for this page load
      document.body && document.body.classList.remove('transition-enabled');
      armSkip(vt);

      var zoom = null;
      try {
        zoom = JSON.parse(sessionStorage.getItem('mh:zoom') || 'null');
        sessionStorage.removeItem('mh:zoom');               // one navigation only
      } catch (err) {}
      if (zoom && Date.now() - (zoom.at || 0) > 8000) zoom = null;   // stale handoff from an aborted navigation
      var act = window.navigation && navigation.activation;   // pagereveal has no activation of its own
      var fromUrl = act && act.from && act.from.url;
      var fromPath = fromUrl ? new URL(fromUrl).pathname : null;

      // inbound to a project page: run the zoom choreography with the transforms measured on the gallery
      if (zoom && zoom.to === location.pathname) {
        setVars(zoom);
        vt.types.add('to-project');
        return;
      }
      // back to a gallery: zoom the cover we came from back into place
      var prev = fromPath || (function () { try { return sessionStorage.getItem('mh:from'); } catch (err) { return null; } })();
      var cover = prev && document.querySelector('a.project-cover[href="' + prev + '"]');
      if (cover) {
        name(cover, true);
        setVars(zoomTransforms(cover));
        vt.types.add('to-home');
        vt.finished.then(function () { name(cover, false); });
        return;
      }
      vt.types.add('fade');
    });

    // project pages remember themselves so the gallery knows which thumbnail to zoom back into
    try { if (!document.querySelector('a.project-cover')) sessionStorage.setItem('mh:from', location.pathname); } catch (err) {}
  }

  /* ---- fallback page fade (no view transitions) ---- */
  document.addEventListener('click', function (e) {
    if (VT || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#' || a.target || a.hasAttribute('download') || a.hasAttribute('data-bypass')) return;
    if (/^(mailto|tel|javascript):/i.test(href)) return;
    if (a.host !== location.host || a.pathname === location.pathname) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    document.body.classList.add('transition-out');
    setTimeout(function () { location.href = a.href; }, FADE);
  }, true);
  window.addEventListener('pageshow', function () { document.body.classList.remove('transition-out'); });

  /* ---- prefetch on intent: the page HTML and its first image ---- */
  var warmed = {};
  function warm(a) {
    var href = a.href;
    if (!href || warmed[href] || a.host !== location.host) return;
    warmed[href] = true;
    try { fetch(href, { credentials: 'same-origin', priority: 'low' }).catch(function () {}); } catch (err) {}
    var img = a.getAttribute('data-preload');
    if (img) { var i = new Image(); i.src = img; }
  }
  ['mouseenter', 'touchstart', 'focus'].forEach(function (ev) {
    document.addEventListener(ev, function (e) {
      var a = e.target.closest && e.target.closest('a.project-cover[href], nav a[href]');
      if (a) warm(a);
    }, { capture: true, passive: true });
  });
})();
