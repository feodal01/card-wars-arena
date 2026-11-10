const $ = (id) => document.getElementById(id);
const array = (v) => (Array.isArray(v) ? v : []);
function el(tag, text = "", cls = "") {
  const element = document.createElement(tag);
  if (text != null) element.textContent = String(text);
  if (cls) element.className = cls;
  return element;
}
const payload = JSON.parse($("trace-data").textContent);
const events = payload.events;
const start = events.find((e) => e.type === "match_start")?.data ?? {};
const seats = array(start.seats).length ? start.seats : ["A", "B"];
const playerName = (seat) => start.display_names?.[seat] ?? start.identities?.[seat] ?? seat ?? "unknown player";
const names = new Map(Object.entries(payload.display.names));
const labels = new Map(Object.entries(payload.display.labels));
const actionLabel = (label) => labels.get(label) ?? label;
const cardName = (id) => names.get(id) ?? String(id ?? "—");
const atTime = (ts) =>
  Number.isFinite(ts) && Math.abs(ts) < 8.64e12
    ? new Date(ts * 1000).toISOString().slice(11, 23) + " UTC"
    : "Time unknown";
const titles = {
  match_start: "Match start",
  draft_start: "Deck selection",
  opening: "Opening position",
  game_end: "Game result",
  match_end: "Match result",
  run_interrupted: "Run interrupted",
  run_resumed: "Run resumed",
  timeout: "Time expired",
  public_events: "Board events",
  unity_state: "Board state",
};
const nodes = [];
function turnLabel(turn, actor) {
  return (turn === 0 ? "Landscape placement" : "Turn " + turn) + " · " + playerName(actor);
}
function readableSeconds(seconds) {
  if (!Number.isFinite(seconds)) return "—";
  const value = Math.max(0, seconds);
  return value >= 60
    ? Math.floor(value / 60) + "m " + Math.floor(value % 60) + "s"
    : value.toFixed(1) + "s";
}
const states = new Map(),
  pending = new Map();
for (const event of events) {
  const d = event.data ?? {},
    game = String(event.game ?? "—"),
    type = event.type;
  if (
    ["opening", "run_interrupted", "run_resumed", "game_end"].includes(type)
  ) {
    states.delete(game);
    pending.delete(game);
  }
  let turn = d.turn ?? states.get(game)?.turn ?? null;
  let title = titles[type] ?? type;
  let category = "event";
  if (type === "act") {
    title = actionLabel(d.label ?? d.engine_id ?? "Action");
    category = "action";
  }
  if (type === "submit_deck") title = "Deck · " + playerName(d.seat);
  if (["draft_start", "submit_deck", "opening"].includes(type)) {
    category = "draft";
    turn = null;
  }
  if (["match_end", "game_end"].includes(type)) {
    category = "result";
    turn = null;
  }
  if (/interrupt|resum|error|timeout|reject|fail/.test(type))
    category = "error";
  const state = type === "unity_state" ? d : states.get(game);
  const actor = type === "act" ? d.seat :
    state?.turn === turn ? seats[state.active] : null;
  const node = {
    event,
    game,
    turn,
    title,
    category,
    actor,
    before: null,
    after: null,
    group: "Game " + game + (turn != null ? " / " + turnLabel(turn, actor) : ""),
    index: nodes.length,
  };
  if (type === "unity_state") {
    const action = pending.get(game);
    if (
      action &&
      Number.isInteger(action.event.data?.revision) &&
      d.revision === action.event.data.revision + 1
    )
      action.after = d;
    pending.delete(game);
    states.set(game, d);
    node.after = d;
  } else if (type === "act") {
    const prior = states.get(game);
    if (prior && prior.revision === d.revision) node.before = prior;
    pending.set(game, node);
  }
  nodes.push(node);
}
const games = [...new Set(nodes.map((n) => n.game))];
const completed = nodes.filter((n) => n.event.type === "game_end");
const end = nodes.findLast((n) => n.event.type === "match_end")?.event.data;
let game = games[0] ?? "",
  selected = null;
function button(text, cls, fn) {
  const b = el("button", text, cls);
  b.type = "button";
  b.onclick = fn;
  return b;
}
function overview() {
  const area = $("overview");
  area.append(el("div", "Match trace", "kicker"));
  const head = el("div", "", "summary"),
    side = el("div"),
    title = el("h1");
  title.append(
    document.createTextNode(playerName(seats[0]) + " "),
    el(
      "span",
      end ? (end[seats[0]] ?? "—") + " : " + (end[seats[1]] ?? "—") : " · ",
      "score",
    ),
    document.createTextNode(" " + playerName(seats[1])),
  );
  side.append(
    title,
    el(
      "p",
      [
        String(start.match_id ?? payload.source),
        completed.length + " games completed",
        nodes.filter((n) => n.category === "action").length + " decisions",
        events.length + " events",
      ].join("  ·  "),
      "sub",
    ),
  );
  head.append(side, el("span", "Organizer report", "privacy"));
  area.append(head);
  if (!end)
    $("notices").append(
      el("p", "Incomplete trace. The match result has yet to be recorded.", "notice warn"),
    );
  for (const message of payload.diagnostics)
    $("notices").append(el("p", message, "notice warn"));
}
function gameBar() {
  const area = $("games");
  area.replaceChildren();
  for (const g of games) {
    const result = completed.find((n) => n.game === g)?.event.data;
    const b = button("", "game", () => {
      game = g;
      selected = null;
      $("query").value = "";
      $("turn").value = "";
      refresh(true);
    });
    b.setAttribute("aria-pressed", String(game === g));
    b.append(
      el("strong", "Game " + g),
      el("small", result ? "Winner · " + playerName(result.winner) : "No result"),
    );
    area.append(b);
  }
}
function timeline() {
  const area = $("timeline");
  area.replaceChildren();
  const records = nodes.filter(
    (n) => n.game === game && Number.isFinite(n.event.ts),
  );
  const checkpoints = records.filter(
    (n) => n.event.type === "unity_state" && Number.isInteger(n.turn),
  );
  if (!checkpoints.length) return;
  const turns = [];
  for (const n of checkpoints) {
    if (turns.at(-1)?.turn !== n.turn || turns.at(-1)?.actor !== n.actor) turns.push(n);
  }
  // The last sample in the game ends the measured interval. A clock correction
  // can yield zero duration; never present a negative elapsed time.
  const last = records.at(-1).event.ts;
  const track = el("div", "", "track");
  area.append(
    el("div", "Turn durations · Game " + game, "kicker"),
    track,
  );
  for (let i = 0; i < turns.length; i++) {
    const n = turns[i];
    const span = Math.max(0, (turns[i + 1]?.event.ts ?? last) - n.event.ts);
    const name = turnLabel(n.turn, n.actor) + " · " + readableSeconds(span);
    const segment = button(n.turn === 0 ? "L" : String(n.turn), "segment", () => {
      $("turn").value = String(n.turn);
      $("query").value = "";
      $("kind").value = "";
      refresh();
    });
    segment.dataset.side = String(seats.indexOf(n.actor));
    segment.style.flexGrow = String(span);
    segment.title = name;
    segment.setAttribute("aria-label", name);
    segment.setAttribute(
      "aria-pressed",
      String($("turn").value === String(n.turn)),
    );
    track.append(segment);
  }
  const key = el("div", "", "seat-key");
  seats.forEach((seat, i) => {
    const label = el("span", playerName(seat));
    label.dataset.side = String(i);
    key.append(label);
  });
  area.append(
    key,
    el(
      "span",
      readableSeconds(last - turns[0].event.ts) +
        " from the first snapshot to the last event",
      "legend",
    ),
  );
}
function refresh(resetTurns = false) {
  gameBar();
  const query = $("query").value.trim().toLowerCase(),
    filter = $("kind").value;
  if (resetTurns) {
    const t = $("turn");
    t.replaceChildren(new Option("All turns", ""));
    const turns = new Map();
    for (const n of nodes) {
      if (n.game === game && n.turn != null && !turns.get(n.turn))
        turns.set(n.turn, n.actor);
    }
    for (const [number, actor] of turns)
      t.add(new Option(number === 0 ? "Landscape placement" : turnLabel(number, actor), String(number)));
  }
  timeline();
  const turn = $("turn").value;
  const visible = nodes.filter((n) => {
    if (n.game !== game || (turn && String(n.turn) !== turn)) return false;
    if (filter === "wheel") {
      if (
        n.event.type !== "act" ||
        !array(n.after?.events).some((v) => String(v).startsWith("wheel "))
      )
        return false;
    } else if (filter && filter !== "raw" && n.category !== filter)
      return false;
    if (
      !query &&
      filter !== "raw" &&
      ["public_events", "unity_state"].includes(n.event.type)
    )
      return false;
    if (
      query &&
      !(
        n.title + " " + n.group +
        " " +
        n.event.type +
        " " +
        JSON.stringify(n.event.data) +
        " " +
        JSON.stringify(n.event.data, (_, value) => names.get(value) ?? actionLabel(value)) +
        " " +
        JSON.stringify(array(n.after?.events).map(actionLabel))
      )
        .toLowerCase()
        .includes(query)
    )
      return false;
    return true;
  });
  if (!visible.includes(selected))
    selected =
      visible.find((n) => n.category === "action") ?? visible[0] ?? null;
  const tree = $("tree");
  tree.replaceChildren();
  let last = null;
  for (const n of visible) {
    if (n.group !== last) {
      tree.append(el("span", n.group, "group"));
      last = n.group;
    }
    const b = button("", "row", () => {
      selected = n;
      refresh();
    });
    b.setAttribute("aria-current", String(n === selected));
    b.append(
      el("span", "", "dot " + n.category),
      el("span", n.title, "title"),
      el("time", "#" + (n.event.seq ?? n.index + 1)),
    );
    tree.append(b);
  }
  if (!visible.length)
    tree.append(el("div", "No matching events.", "empty"));
  renderDetail(selected, seats);
}
$("kind").add(new Option("All raw records", "raw"));
$("query").placeholder = "Search this game…";
$("query").setAttribute("aria-label", "Search this game");
$("query").oninput = () => refresh();
$("kind").onchange = () => refresh();
$("turn").onchange = () => refresh();
overview();
refresh(true);
