/* herrada.me, direction E: Select Screen.

   The page is complete before this file runs. Every row, pane and link is in the HTML,
   and the stylesheet already shows the chosen row. This file adds four things:

     1. Enter opens a row, and Esc (or, on a touch screen, a link) comes back from what it opened.
     2. The loop controls: pause, and a stop while the pane is off screen.
     3. Bumpy: he hops to the chosen row, naps when the menu is left alone, and can be hidden.
     4. Catch: the one row you can play.

   No libraries and no network. One stored value: whether Bumpy is hidden.
   The rules of catch come first and touch no page, so Node can load this file and
   tests/catch.test.js can replay a seed.
   Keys belong to controls: the list hears Enter (and j, k) while a row has focus, and
   the game hears Left, Right and Esc while the pane has focus. Up and Down in the list
   are the browser's own radio keys. No key listener sits on the document. */
(() => {
  'use strict';

  /* ---------- the rules of catch: pure, so tests/catch.test.js can replay them ---------- */

  const W = 400;
  const H = 300;
  const PADDLE_W = 40;
  const PADDLE_Y = 280;
  const BLOCK = 20;
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

  // A small seeded generator (mulberry32). It returns a number and the next seed,
  // so the dice live in the world and step() stays pure.
  function roll(seed) {
    const next = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(next ^ (next >>> 15), next | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return [((t ^ (t >>> 14)) >>> 0) / 4294967296, next];
  }

  const fresh = (seed) => ({
    seed, paddle: (W - PADDLE_W) / 2, bx: 0, by: -BLOCK, falling: false, wait: 0.5, speed: 95, score: 0, lives: 3
  });

  // One pure function steps the world, the way the thirteen games do it. It has no
  // clock, no keyboard and no dice of its own: the same seed and the same intents
  // always give the same game.
  function step(world, intent, dt) {
    if (world.lives === 0) return world;
    let { seed, paddle, bx, by, falling, wait, speed, score, lives } = world;

    if (intent.to !== null) paddle += clamp(intent.to - PADDLE_W / 2 - paddle, -900 * dt, 900 * dt);
    else paddle += intent.dir * 300 * dt;
    paddle = clamp(paddle, 0, W - PADDLE_W);

    if (!falling) {
      wait -= dt;
      if (wait <= 0) {
        let r;
        [r, seed] = roll(seed);
        bx = r * (W - BLOCK);
        by = -BLOCK;
        falling = true;
      }
    } else {
      const before = by + BLOCK;
      by += speed * dt;
      const crossed = before <= PADDLE_Y && by + BLOCK >= PADDLE_Y;
      if (crossed && bx + BLOCK > paddle && bx < paddle + PADDLE_W) {
        score += 1;
        speed = Math.min(250, 95 + score * 7);
        falling = false;
        wait = 0.3;
      } else if (by > H) {
        lives -= 1;
        falling = false;
        wait = 0.5;
      }
    }
    return { seed, paddle, bx, by, falling, wait, speed, score, lives };
  }

  // Under Node there is no page: hand the rules to the test and stop here.
  if (typeof document === 'undefined') {
    if (typeof module === 'object') module.exports = { W, H, PADDLE_W, PADDLE_Y, BLOCK, roll, fresh, step };
    return;
  }

  const root = document.documentElement;
  root.classList.add('js');

  const calm = matchMedia('(prefers-reduced-motion: reduce)');
  const memory = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) {
      try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch (e) { /* private mode: nothing is kept */ }
    }
  };
  // Bumpy is one switch in src/site.json. With it off the page has no sprite and the
  // placeholder block is the cursor for good.
  const hasBumpy = Boolean(document.querySelector('[data-bumpy]'));
  if (hasBumpy && memory.get('bumpy') === 'hidden') root.classList.add('no-bumpy');

  const menu = document.querySelector('[data-menu]');
  if (!menu) return;

  const radios = [...menu.querySelectorAll('.row-radio')];
  const rows = radios.map((radio) => radio.closest('.row'));
  const stage = menu.querySelector('.stage');
  const status = menu.querySelector('[data-status]');
  const indexOf = (value) => radios.findIndex((radio) => radio.value === value);
  let chosen = Math.max(0, radios.findIndex((radio) => radio.checked));
  let paused = false;

  const say = (text) => { status.textContent = text; };
  // what the pane now shows, for a reader who cannot see it: the drawing in words
  const describe = (i) => {
    const figure = stage.querySelector('.pv-' + radios[i].value);
    return (figure.querySelector('[data-alt]') || figure.querySelector('.fact')).textContent;
  };

  /* ---------- 1. choose, open, come back ---------- */

  function choose(i) {
    radios[i].checked = true;
    radios[i].focus();
    radios[i].dispatchEvent(new Event('change', { bubbles: true }));
  }

  menu.addEventListener('change', (event) => {
    const next = radios.indexOf(event.target);
    if (next < 0 || next === chosen) return;
    const from = chosen;
    chosen = next;
    // some browsers do not focus a radio on a click, and then Up and Down would not reach the list
    if (document.activeElement !== event.target) event.target.focus({ preventScroll: true });
    stage.style.setProperty('--delay', '0s'); // from now on a loop starts at its first frame
    game.leave(false);
    say(describe(next));
    bumpy.hop((from - next) * rows[0].offsetHeight);
    // on a phone the pane is pinned: a row tapped at its edge comes out from behind it
    event.target.scrollIntoView({ block: 'nearest' });
  });

  menu.addEventListener('keydown', (event) => {
    const i = radios.indexOf(event.target);
    if (i < 0 || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'Enter') {
      event.preventDefault();
      const play = rows[i].querySelector('[data-play]');
      // In a round, Enter on the row goes back to the game, whose focus resumes it, as
      // its note says. It never presses stop: that takes a click on the button itself.
      if (play && game.on) game.focus();
      else (play || rows[i].querySelector('a.row-go')).click();
    } else if (event.key === 'j' || event.key === 'k') {
      // Up and Down are the browser's own. j and k are for the hands that expect them.
      event.preventDefault();
      choose((i + (event.key === 'j' ? 1 : radios.length - 1)) % radios.length);
    }
  });

  // a browser may put back the row that was chosen before a reload or a trip back
  addEventListener('pageshow', () => { chosen = Math.max(0, radios.findIndex((radio) => radio.checked)); });

  // "open" is a plain link. Follow it, then put focus where the reader now is,
  // so that Esc can bring them back.
  let opened = null;
  const close = () => { if (opened) opened.classList.remove('is-open'); opened = null; };
  menu.addEventListener('click', (event) => {
    const link = event.target.closest('a.row-go[href^="#"]');
    const target = link && document.getElementById(link.hash.slice(1));
    if (!target) return;
    close();
    opened = target;
    target.classList.add('is-open');
    requestAnimationFrame(() => target.focus({ preventScroll: true }));
  });
  const page = document.querySelector('.doc');
  if (page) {
    // Esc, or the "back to the menu" link a touch screen shows in its place, closes what
    // was opened and puts focus back on the chosen row. Without this file the link's
    // href still goes to the menu.
    const back = () => {
      close();
      radios[chosen].focus({ preventScroll: true });
      window.scrollTo({ top: 0 });
    };
    page.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || !opened || !opened.contains(event.target)) return;
      back();
    });
    page.addEventListener('click', (event) => {
      if (!event.target.closest('a.sec-back')) return;
      event.preventDefault();
      back();
    });
    page.addEventListener('focusout', (event) => {
      if (opened && !opened.contains(event.relatedTarget)) close();
    });
  }

  // a link in the page can choose a row: "play catch in the menu"
  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-select]');
    const i = link ? indexOf(link.dataset.select) : -1;
    if (i < 0) return;
    event.preventDefault();
    choose(i);
    window.scrollTo({ top: 0 });
  });

  /* ---------- 2. pause, and stop when nobody is looking ---------- */

  const pauseButton = menu.querySelector('[data-pause]');
  const pauseWord = menu.querySelector('[data-pause-word]');
  function setPaused(value) {
    paused = value;
    menu.classList.toggle('is-paused', paused);
    pauseWord.textContent = paused ? 'resume' : 'pause';
  }
  pauseButton.hidden = false;
  pauseButton.addEventListener('click', () => {
    setPaused(!paused);
    say(paused ? 'Paused.' : 'Playing.');
    if (paused) game.hold();
    else if (game.on) game.focus();
  });

  let offScreen = false;
  const setAway = () => {
    const away = offScreen || document.hidden;
    menu.classList.toggle('is-away', away);
    if (away) game.hold();
  };
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((entries) => {
      offScreen = !entries[entries.length - 1].isIntersecting;
      setAway();
    }).observe(stage);
  }
  document.addEventListener('visibilitychange', setAway);

  /* ---------- 3. Bumpy ---------- */

  const bumpy = !hasBumpy ? { hop() {} } : (() => {
    const el = menu.querySelector('[data-bumpy]');
    const toggle = menu.querySelector('[data-bumpy-toggle]');
    const TICK = 83;       // about 12 frames a second, as on the desktop he comes from
    const NAP_AFTER = 14000;
    let timer = 0;
    let napTimer = 0;
    let y = 0;             // where he is drawn, in px from where he belongs

    function pose(name, dy) {
      y = Math.round(dy);
      el.dataset.pose = name;
      el.style.transform = y ? `translateY(${y}px)` : '';
    }

    function play(frames) {
      clearTimeout(timer);
      clearTimeout(napTimer);
      const next = () => {
        const [name, dy] = frames.shift();
        pose(name, dy);
        if (frames.length) timer = setTimeout(next, TICK);
        else rest();
      };
      next();
    }

    // Awake and idle. Leave the menu alone and he naps on his row.
    function rest() {
      clearTimeout(napTimer);
      if (calm.matches) return pose('sleep', 0);
      napTimer = setTimeout(() => {
        if (game.on || paused) rest();
        else pose('sleep', 0);
      }, NAP_AFTER);
    }

    // A slime has no legs to walk with: he hops. He stretches on the way and squashes
    // for two frames on landing. `from` is how far the row he left is, in px.
    function hop(from) {
      if (calm.matches) return pose('sleep', 0);
      from += y;
      const lift = 10 + Math.min(Math.abs(from), 140) * 0.06;
      const at = (t) => from * (1 - t) - lift * 4 * t * (1 - t);
      play([
        ['squash', from],
        ['stretch', at(0.3)],
        ['stretch', at(0.62)],
        ['stretch', at(0.9)],
        ['squash', 0],
        ['squash', 0],
        ['base', 0]
      ]);
    }

    const enter = () => hop(-34);
    const jump = () => {
      if (calm.matches) { pose('base', 0); clearTimeout(napTimer); napTimer = setTimeout(() => pose('sleep', 0), NAP_AFTER); return; }
      play([['squash', 0], ['stretch', -8], ['stretch', -13], ['stretch', -7], ['squash', 0], ['base', 0]]);
    };

    // any sign of life in the menu wakes him and restarts the wait
    function stir() {
      if (timer && el.dataset.pose !== 'base' && el.dataset.pose !== 'sleep') return; // mid hop
      if (el.dataset.pose === 'sleep' && !calm.matches) pose('base', 0);
      rest();
    }

    el.addEventListener('click', jump); // a tap wakes him
    ['pointerdown', 'keydown', 'focusin'].forEach((type) => menu.addEventListener(type, (event) => {
      if (!el.contains(event.target)) stir();
    }));
    calm.addEventListener('change', rest);

    const hidden = () => root.classList.contains('no-bumpy');
    // the button says "hide bumpy", and its name says who Bumpy is
    const label = () => {
      const word = hidden() ? 'Show Bumpy' : 'Hide Bumpy';
      toggle.textContent = word;
      toggle.title = word + ', the cursor';
      toggle.setAttribute('aria-label', word + ', the cursor');
    };
    toggle.hidden = false;
    label();
    toggle.addEventListener('click', () => {
      const hide = !hidden();
      root.classList.toggle('no-bumpy', hide);
      memory.set('bumpy', hide ? 'hidden' : null);
      label();
      if (!hide) enter();
    });

    enter();
    return { hop };
  })();

  /* ---------- 4. catch ---------- */

  const game = (() => {
    const screen = menu.querySelector('[data-game]');
    const mine = indexOf('minigames');
    const playButton = rows[mine].querySelector('[data-play]');
    const playWord = rows[mine].querySelector('[data-play-word]');
    const paddle = screen.querySelector('[data-paddle]');
    const block = screen.querySelector('[data-block]');
    const score = screen.querySelector('[data-score]');
    const lives = screen.querySelector('[data-lives]');
    const note = screen.querySelector('[data-note]');
    const desc = menu.querySelector('[data-game-desc]');
    const IDLE_DESC = desc.textContent;
    // a touch screen has no Enter to press, so its notes name only the tap
    const touch = () => matchMedia('(pointer: coarse)').matches;
    // The invitation to play. With a keyboard the word Enter is drawn as a key, like
    // the j, d, d keys in the vim-puzzles pane.
    const idleNote = () => {
      if (touch()) return note.replaceChildren('Tap to play');
      const key = document.createElement('span');
      key.className = 'key';
      key.textContent = 'Enter';
      note.replaceChildren(key, ' or tap to play');
    };
    const POSTER = { paddle: 180, bx: 270, by: 96, falling: true, score: 0, lives: 3 };
    const intent = { dir: 0, to: null };
    const keys = { left: false, right: false };
    const api = { on: false, hold, leave, focus };
    let world = POSTER;
    let round = 0;
    let frameId = 0;
    let last = 0;
    let held = false;

    function draw(w) {
      paddle.setAttribute('x', w.paddle.toFixed(1));
      block.setAttribute('x', w.bx.toFixed(1));
      block.setAttribute('y', w.by.toFixed(1));
      block.style.visibility = w.falling ? '' : 'hidden';
      score.textContent = w.score;
      lives.textContent = w.lives;
    }

    function frame(now) {
      world = step(world, intent, Math.min(0.05, (now - last) / 1000));
      last = now;
      draw(world);
      if (world.lives === 0) return over();
      frameId = requestAnimationFrame(frame);
    }

    function run() {
      held = false;
      note.textContent = '';
      last = performance.now();
      cancelAnimationFrame(frameId);
      frameId = requestAnimationFrame(frame);
    }

    function newRound() {
      round += 1;
      world = fresh(2008 + round); // the first round is always the same game
      setPaused(false);
      draw(world);
      run();
    }

    function start() {
      api.on = true;
      menu.classList.add('is-playing');
      screen.classList.remove('is-ready');
      screen.classList.add('is-live');
      screen.tabIndex = 0;
      screen.setAttribute('role', 'application');
      screen.setAttribute('aria-label', 'Catch. Left and Right move the paddle. Escape leaves the game.');
      playWord.textContent = 'stop';
      desc.textContent = (touch() ? 'Drag or tap.' : 'Left and Right, or drag.') + ' Three misses end the round.';
      say('Catch. Left and Right move the paddle. Three misses end the round. Escape leaves the game.');
      screen.focus({ preventScroll: true });
      newRound();
    }

    function hold() {
      if (!api.on || held) return;
      held = true;
      cancelAnimationFrame(frameId);
      // Enter reaches the game only while it has focus: after a blur, name the tap
      if (touch()) note.textContent = 'Paused. Tap to go on.';
      else if (document.activeElement === screen) note.textContent = 'Paused. Tap or press Enter to go on.';
      else note.textContent = 'Paused. Tap the game to go on.';
    }

    function resume() {
      if (!api.on || !held) return;
      if (world.lives === 0) return newRound();
      setPaused(false);
      run();
    }

    function over() {
      held = true;
      note.textContent = `Round over. Caught ${world.score}. ${touch() ? 'Tap' : 'Tap or press Enter'} for another.`;
      say(`Round over. Caught ${world.score}.`);
    }

    function leave(refocus) {
      if (!api.on) return;
      api.on = false;
      held = false;
      cancelAnimationFrame(frameId);
      keys.left = keys.right = false;
      intent.dir = 0;
      intent.to = null;
      menu.classList.remove('is-playing');
      screen.classList.remove('is-live');
      screen.classList.add('is-ready');
      screen.removeAttribute('tabindex');
      screen.removeAttribute('role');
      screen.removeAttribute('aria-label');
      playWord.textContent = 'play';
      desc.textContent = IDLE_DESC;
      idleNote();
      world = POSTER;
      draw(world);
      if (refocus) radios[mine].focus({ preventScroll: true });
    }

    function focus() { screen.focus({ preventScroll: true }); }

    const aim = (event) => {
      const box = screen.getBoundingClientRect();
      intent.to = clamp(((event.clientX - box.left) / box.width) * W, 0, W);
    };

    playButton.hidden = false;
    playButton.addEventListener('click', () => (api.on ? leave(true) : start()));

    // a tap places the paddle and a drag steers it, so nothing needs a drag
    screen.addEventListener('pointerdown', (event) => {
      if (!api.on) return start();
      if (held) { focus(); return resume(); }
      aim(event);
      if (screen.setPointerCapture) screen.setPointerCapture(event.pointerId);
    });
    screen.addEventListener('pointermove', (event) => {
      if (api.on && !held && event.buttons) aim(event);
    });

    const steer = (event, down) => {
      if (!api.on || event.altKey || event.ctrlKey || event.metaKey) return;
      const key = event.key;
      if (key === 'ArrowLeft' || key === 'h') keys.left = down;
      else if (key === 'ArrowRight' || key === 'l') keys.right = down;
      else if (down && key === 'Escape') { event.preventDefault(); return leave(true); }
      else if (down && (key === 'Enter' || key === ' ')) { event.preventDefault(); return resume(); }
      else return; // Up and Down still scroll the page
      event.preventDefault();
      intent.to = null;
      intent.dir = (keys.right ? 1 : 0) - (keys.left ? 1 : 0);
    };
    screen.addEventListener('keydown', (event) => steer(event, true));
    screen.addEventListener('keyup', (event) => steer(event, false));

    // the game listens only while it has focus
    screen.addEventListener('blur', () => { if (api.on && world.lives > 0) hold(); });
    screen.addEventListener('focus', () => { if (api.on && held && !paused && world.lives > 0) resume(); });

    screen.classList.add('is-ready');
    idleNote();
    return api;
  })();
})();
