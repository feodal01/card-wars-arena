// Exercise the live timeline with two separate clocks: draft completion and
// availability of the first frame. Neither test depends on a Unity installation.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../cardwars/reports/on_air.js'), 'utf8');

function program() {
  let now = 1_000_000;
  const scenes = [], timers = [];
  const context = vm.createContext({
    games: Array.from({length: 5}, (_, i) => ({number: i + 1, decks: [], hp: []})),
    Date: {now: () => now},
    fetch: () => new Promise(() => {}),
    setTimeout: (fn, ms) => timers.push({at: now + ms, fn}),
    renderScene: ({kind}) => scenes.push(kind),
    nativeField: () => scenes.push('battle'),
  });
  vm.runInContext(script, context);
  return {
    scenes,
    row: (game, type, data) => context.eventRow([1, now / 1000, game, type, data]),
    paint: feed => context.updateProgram(feed),
    advance(ms) {
      now += ms;
      for (const timer of timers.filter(t => t.at <= now)) {
        timers.splice(timers.indexOf(timer), 1);
        timer.fn();
      }
    },
  };
}

test('two locked decks stay on air until Unity is ready, then Fight lasts 1.2 seconds', () => {
  const p = program();
  p.row(1, 'draft_start', {});
  for (const player of [1, 0]) p.row(1, 'submit_deck', {player});
  p.advance(35_000);
  p.paint(null);
  assert.deepEqual(p.scenes, ['draft']);
  p.paint(1);
  p.advance(1199);
  assert.equal(p.scenes.at(-1), 'fight');
  p.advance(1);
  assert.equal(p.scenes.at(-1), 'battle');
});

test('the final scoreboard appears even if the host closes after delivering the result', () => {
  const p = program();
  p.row(5, 'game_end', {winner: 1, turns: 11, hp: [0, 78], reason: 'health'});
  p.row(5, 'match_end', {});
  p.paint(null);
  assert.deepEqual(p.scenes, ['result']);
  p.advance(4010);
  assert.deepEqual(p.scenes, ['result', 'final']);
});
