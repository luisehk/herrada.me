/* herrada.me, the Field Guide (HM-0002, direction D, "ficha").
   Three small jobs: hold the growth of the stand until the stand is on screen, open a fold
   a link points at, and open every fold for paper. The growth itself is CSS, and every page
   is complete without this file. */
(function () {
  'use strict';

  var stand = document.querySelector('.stand');
  var held = null;   // the stand while the script holds its growth

  if (stand) {
    // Under a test driver the plate is drawn finished, so screenshots and CI runs hold still.
    var driven = navigator.webdriver;

    if (driven) {
      document.documentElement.classList.add('is-still');
    } else if ('IntersectionObserver' in window && window.matchMedia &&
               !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      holdUntilSeen(stand);
    }
  }

  function byHash(hash) {
    var id = (hash || '').replace(/^#/, '');
    if (!id) { return null; }
    try { id = decodeURIComponent(id); } catch (e) { return null; }
    return document.getElementById(id);
  }

  function holdUntilSeen(el) {
    var mark = el.querySelector('.stand__sentinel');   // sits near the middle of the stand
    if (!mark) { return; }

    // A link to a part of the page beyond the stand scrolls there after this runs, so where
    // the stand sits now says nothing: leave it to the observer.
    var target = byHash(location.hash);
    if (!target || el.contains(target)) {
      var box = mark.getBoundingClientRect();
      if (box.top < window.innerHeight && box.bottom > 0) { return; }   // in view: let it grow
    }

    el.classList.add('is-waiting');
    held = el;
    var watcher = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i += 1) {
        if (entries[i].isIntersecting) {
          el.classList.remove('is-waiting');
          held = null;
          watcher.disconnect();
          return;
        }
      }
    });
    watcher.observe(mark);
  }

  // A link to a fold opens it: the cover's "pick a tree" opens the key on a phone. A click on
  // a link to the hash already in the address fires no hashchange, so a click opens it too.
  function openFold(hash) {
    var el = byHash(hash);
    if (el && el.tagName === 'DETAILS') { el.open = true; }
  }

  openFold(location.hash);
  window.addEventListener('hashchange', function () { openFold(location.hash); });
  document.addEventListener('click', function (event) {
    var link = event.target && event.target.closest ? event.target.closest('a[href^="#"]') : null;
    if (link) { openFold(link.getAttribute('href')); }
  });

  // On paper every sheet shows its field notes and every fold, and the stand is drawn
  // finished. Afterwards the page is as it was.
  var opened = [];

  window.addEventListener('beforeprint', function () {
    if (held) { held.classList.remove('is-waiting'); }
    var notes = document.querySelectorAll('details');
    for (var i = 0; i < notes.length; i += 1) {
      if (!notes[i].open) {
        notes[i].open = true;
        opened.push(notes[i]);
      }
    }
  });

  window.addEventListener('afterprint', function () {
    for (var i = 0; i < opened.length; i += 1) { opened[i].open = false; }
    opened = [];
    if (held) { held.classList.add('is-waiting'); }
  });
})();
