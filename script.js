/* herrada.me, the Field Guide (HM-0002, direction D, "ficha").
   One job: hold the growth of the stand until the stand is on screen.
   The growth itself is CSS, and every page is complete without this file. */
(function () {
  'use strict';

  var stand = document.querySelector('.stand');

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

  function holdUntilSeen(el) {
    var mark = el.querySelector('.stand__sentinel');   // sits near the middle of the stand
    if (!mark) { return; }

    var box = mark.getBoundingClientRect();
    if (box.top < window.innerHeight && box.bottom > 0) { return; }   // in view: let it grow

    el.classList.add('is-waiting');
    var watcher = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i += 1) {
        if (entries[i].isIntersecting) {
          el.classList.remove('is-waiting');
          watcher.disconnect();
          return;
        }
      }
    });
    watcher.observe(mark);
  }

  // On paper every sheet shows its field notes and every fold.
  window.addEventListener('beforeprint', function () {
    var notes = document.querySelectorAll('details');
    for (var i = 0; i < notes.length; i += 1) { notes[i].open = true; }
  });
})();
