// The rules of catch, replayed from a seed (HM-0002, test T-HM-2-10).
//
//   node --test tests/catch.test.js
//
// script.js hands its pure rules to Node when there is no page. The same seed and the
// same intents must always give the same world, as in the thirteen games.
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { W, PADDLE_W, roll, fresh, step } = require(path.join(__dirname, '..', 'script.js'));

const DT = 1 / 60;

// A fixed player: chase the block when it falls, rest in the middle otherwise.
function chase(world) {
  if (!world.falling) return { dir: 0, to: null };
  const centre = world.paddle + PADDLE_W / 2;
  const target = world.bx + 10;
  return { dir: target > centre + 2 ? 1 : target < centre - 2 ? -1 : 0, to: null };
}

function play(seed, frames, player) {
  let world = fresh(seed);
  for (let i = 0; i < frames && world.lives > 0; i += 1) world = step(world, player(world), DT);
  return world;
}

const round = (world) => Object.fromEntries(
  Object.entries(world).map(([key, value]) => [key, typeof value === 'number' && !Number.isInteger(value) ? Number(value.toFixed(6)) : value])
);

test('the dice are a pure function of the seed', () => {
  assert.deepEqual(roll(2009), roll(2009));
  const [r, next] = roll(2009);
  assert.ok(r >= 0 && r < 1);
  assert.notEqual(next, 2009);
});

test('the same seed and the same intents give the same game', () => {
  assert.deepEqual(play(2009, 3600, chase), play(2009, 3600, chase));
});

test('the first round of the site replays to the recorded world', () => {
  // Round one on the site is fresh(2008 + 1). A minute at 60 frames a second with the chasing player.
  assert.deepEqual(round(play(2009, 3600, chase)), {
    seed: 943967364,
    paddle: 150,
    bx: 162.478559,
    by: 263.333333,
    falling: false,
    wait: 0.166667,
    speed: 250,
    score: 31,
    lives: 3,
  });
});

test('a paddle that never moves loses the round after three misses', () => {
  const world = play(2009, 60 * 60, () => ({ dir: 0, to: null }));
  assert.equal(world.lives, 0);
  assert.ok(world.score < 31);
});

test('a finished round does not change', () => {
  const over = { ...fresh(1), lives: 0 };
  assert.equal(step(over, { dir: 1, to: null }, DT), over);
});

test('the paddle stays on the screen', () => {
  let world = fresh(7);
  for (let i = 0; i < 600; i += 1) world = step(world, { dir: 1, to: null }, DT);
  assert.equal(world.paddle, W - PADDLE_W);
  for (let i = 0; i < 600; i += 1) world = step(world, { dir: 0, to: -50 }, DT);
  assert.equal(world.paddle, 0);
});
