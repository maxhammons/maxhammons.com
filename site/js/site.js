/* Page fade between pages, independent of network speed.
   The exported Adobe JS adds .transition-out on click but lets the browser navigate
   immediately, so on a fast host the fade never shows. This waits for the fade first. */
(function () {
  var FADE = 250; // ms, keep equal to --fade in site.css and .transition-out in dist/css/main.css
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#' || a.target || a.hasAttribute('download') || a.hasAttribute('data-bypass')) return;
    if (/^(mailto|tel|javascript):/i.test(href)) return;
    if (a.host !== location.host) return;
    if (a.pathname === location.pathname) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    document.body.classList.add('transition-out');
    setTimeout(function () { location.href = a.href; }, FADE);
  }, true);
  // Back/forward cache restores can leave the page faded out; undo that.
  window.addEventListener('pageshow', function () { document.body.classList.remove('transition-out'); });
})();
