// The inspector reads the selected organizer event; all trace strings are rendered as text.
window.renderDetail = function renderDetail(node, seats) {
  const root = document.getElementById("inspector");
  root.replaceChildren();
  if (!node) {
    root.append(el("p", "Select a timeline event.", "empty"));
    return;
  }
  const {event, before, after} = node;
  const data = event.data ?? {};
  const seatName = id => playerName(seats[id] ?? id);
  const name = id => id == null ? "—" : cardName(id);
  const stage = turn => turn === 0 ? "Landscape placement" : "Turn " + String(turn ?? "—");
  const show = value => value == null ? "—" : String(value);
  const block = (tag, text, cls) => el(tag, text, cls);
  const list = values => {
    const ul = block("ul", "", "list");
    for (const v of values) ul.append(block("li", String(v)));
    return ul;
  };
  const chips = values => {
    const row = block("div", "", "chips");
    for (const v of values) row.append(block("span", String(v), "chip"));
    return row;
  };
  const events = event.type === "public_events" ? array(data) : array(after?.events);
  const wheelLines = events.filter(s => typeof s === "string" && s.startsWith("wheel "));
  const isAct = event.type === "act";
  const options = array((isAct ? before : after ?? before)?.actions);
  const reasons = {health: "Hero health reached zero", deck_timeout: "Deck selection timed out",
    turn_timeout: "Turn timed out", retry_same_opening: "Restarted with the same opening position"};
  const reasonText = reason => reasons[reason] ?? show(reason);

  root.append(block("div", node.group, "kicker"), block("h2", node.title),
    block("p", [atTime(event.ts), "#" + event.seq, event.type].join(" · "), "meta"));
  const tabs = block("nav", "", "tabs");
  tabs.setAttribute("aria-label", "Event details");
  const content = block("div", "", "inspector-body");
  root.append(tabs, content);

  function roster(group, p) {
    const pane = block("div", "", "panel");
    pane.append(block("strong", playerName(p.seat ?? group)), block("p", "Hero · " + name(p.hero)));
    if (Array.isArray(p.cards)) pane.append(block("h3", "Deck · " + p.cards.length), chips(p.cards.map(name)));
    const tiles = p.required_landscapes ?? p.landscapes;
    if (Array.isArray(tiles)) pane.append(block("h3", "Landscapes"), chips(tiles));
    return pane;
  }
  function summary() {
    if ((isAct || event.type === "submit_deck") && data.comment) {
      content.append(block("h3", "Player comment"), block("p", data.comment, "panel"));
    }
    if (isAct) {
      content.append(chips([playerName(data.seat), stage(data.turn), "Revision " + show(data.revision)]));
      if (before && after) {
        const changes = seats.map((s, i) => playerName(s) + " · HP " + show(before.hp?.[i]) + " → " + show(after.hp?.[i]));
        content.append(block("h3", "After the action"), chips(changes));
      }
      if (events.length) content.append(list(events.map(actionLabel)));
    } else if (event.type === "submit_deck") {
      content.append(roster(data.seat, data));
    } else if (event.type === "opening") {
      content.append(block("p", "First player · " + seatName(data.first) + " · Starting health · " + show(data.health), "panel"));
      for (const p of array(data.players)) content.append(roster(p.seat, p));
    } else if (event.type === "match_start") {
      content.append(chips(["Seed " + show(data.seed), "Starting HP " + show(data.health), ...array(data.seats).map(playerName)]));
      if (data.pool) content.append(block("h3", "Shared pool · " + data.pool.length), chips(data.pool.map(name)));
      if (data.heroes) content.append(block("h3", "Heroes"), chips(data.heroes.map(name)));
    } else if (event.type === "game_end") {
      content.append(block("p", "Winner · " + playerName(data.winner), "panel"), block("p", reasonText(data.reason)));
      content.append(chips(["Turns · " + show(data.turns), ...array(data.hp).map((h, i) => seatName(i) + " · HP " + h)]));
    } else if (event.type === "match_end") {
      content.append(list(Object.entries(data).map(([s, n]) => playerName(s) + " · " + n + " wins")));
    } else if (event.type === "timeout") {
      const phase = data.phase === "select_deck" ? "deck selection" : show(data.phase);
      content.append(block("p", "Time expired · " + playerName(data.seat) + " · " + phase, "notice warn"),
        chips(["Deadline · " + atTime(data.deadline), "Observed · " + atTime(data.observed_at)]));
    } else if (event.type === "run_interrupted" || event.type === "run_resumed" || node.category === "error") {
      content.append(block("p", reasonText(typeof data === "string" ? data : data.reason ?? data.message), "notice warn"));
    } else if (event.type === "public_events") {
      content.append(list(events.map(actionLabel)));
    } else if (event.type === "unity_state") {
      content.append(chips([stage(data.turn), "Revision " + show(data.revision),
        "Active player · " + seatName(data.active), "Available actions · " + array(data.actions).length]));
      if (events.length) content.append(list(events.map(actionLabel)));
    } else if (event.type === "draft_start") {
      content.append(block("p", "Choose a hero and twenty cards for game " + event.game + ".", "panel"));
    } else {
      content.append(block("pre", JSON.stringify(data, null, 2)));
    }
  }
  function choices() {
    if (!options.length) {
      content.append(block("p", "No actions were available in this state.", "empty"));
      return;
    }
    const ul = block("ul", "", "list");
    for (const choice of options) {
      const picked = isAct && choice.id === data.engine_id;
      const li = block("li", "", picked ? "chosen" : "");
      li.append(block("span", (picked ? "Selected · " : "") + actionLabel(choice.label ?? choice.id)),
        block("small", "  " + choice.id));
      ul.append(li);
    }
    content.append(ul);
  }
  function snapshot(state) {
    if (!state) {
      content.append(block("p", "This trace has no snapshot for this state.", "empty"));
      return;
    }
    content.append(block("p", stage(state.turn) + " · Revision " + show(state.revision)
      + " · Active player · " + seatName(state.active), "meta"));
    const columns = block("div", "", "columns");
    for (const side of array(state.board)) {
      const i = side.seat;
      const col = block("section", "", "board");
      col.append(block("h3", seatName(i)), block("p", name(side.hero)),
        chips(["HP " + show(state.hp?.[i]), "Mana · " + show(side.mp), "Spell mana · " + show(side.spellMP),
          "Ability cooldown · " + show(side.heroCooldown), "Cards in deck · " + show(side.deckCount)]));
      for (const lane of array(side.lanes)) {
        const row = block("div", "", "lane");
        const flags = [lane.flipped && "flipped", lane.disabled && "blocked"].filter(Boolean);
        row.append(block("b", "Lane " + (lane.lane + 1) + " · " + (lane.landscape === "None" ? "empty" : show(lane.landscape))));
        if (flags.length) row.append(block("small", " · " + flags.join(", ")));
        const c = lane.creature;
        if (c) {
          const conditions = [c.flooped && "flooped", c.cantAttack && "cannot attack", c.protected && "protected",
            c.helpless && "helpless", c.floopBlocked && "floop blocked"].filter(Boolean);
          row.append(block("p", name(c.id) + " · attack " + show(c.attack) + " · HP " + show(c.hp)
            + (c.maxHP == null ? "" : "/" + c.maxHP) + (conditions.length ? " · " + conditions.join(", ") : "")));
        }
        if (lane.building) row.append(block("p", "Building · " + name(lane.building)));
        col.append(row);
      }
      const hand = array(state.hands?.[i]);
      col.append(block("h3", "Hand · " + hand.length), chips(hand.map(name)));
      columns.append(col);
    }
    content.append(columns);
  }
  function wheel() {
    for (const line of wheelLines) {
      const panel = block("div", "", "panel");
      const fields = Object.fromEntries(Array.from(line.matchAll(/(\w+)=([^ ]+)/g), m => [m[1], m[2]]));
      panel.append(block("strong", seatName(fields.seat) + " · Lane " + (Number(fields.lane) + 1)
        + " · " + (fields.mode === "defense" ? "Defense" : "Attack") + " · " + show(fields.result)));
      const bar = block("div", "", "wheelbar");
      const addSector = (x, y, cls) => {
        const sector = block("span", "", cls);
        sector.style.left = (x * 100) + "%";
        sector.style.width = ((y - x) * 100) + "%";
        bar.append(sector);
      };
      for (const key of ["hit", "crit"]) {
        const range = /^\[([-\d.]+),([-\d.]+)\]$/.exec(fields[key] ?? "");
        if (!range) continue;
        const [x, y] = range.slice(1).map(Number);
        if (![x,y].every(v => Number.isFinite(v) && v >= 0 && v <= 1)) continue;
        if (x <= y) addSector(x, y, "sector " + key);
        else { addSector(x, 1, "sector " + key); addSector(0, y, "sector " + key); }
      }
      const stop = Number(fields.stop);
      if (Number.isFinite(stop) && stop >= 0 && stop <= 1) {
        const needle = block("span", "", "needle");
        needle.style.left = (100 * stop) + "%";
        bar.append(needle);
      }
      panel.append(bar, block("p", "Green indicates a hit. Gold indicates a critical hit. "
        + (fields.stop === "forced" ? "The engine forced this result." : "The marker shows where the wheel stopped."), "legend"),
        block("pre", line));
      content.append(panel);
    }
  }
  const entries = [["Overview", summary]];
  if (isAct || options.length) entries.push(["Choices · " + options.length, choices]);
  if (before) entries.push(["Before", () => snapshot(before)]);
  if (after) entries.push(["After", () => snapshot(after)]);
  if (wheelLines.length) entries.push(["Wheel · " + wheelLines.length, wheel]);
  entries.push(["JSON", () => content.append(block("pre", JSON.stringify(event, null, 2)))]);
  function select(button, draw) {
    for (const b of tabs.children) b.setAttribute("aria-pressed", String(b === button));
    content.replaceChildren();
    draw();
  }
  for (const [label, draw] of entries) {
    const button = block("button", label);
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => select(button, draw));
    tabs.append(button);
  }
  select(tabs.children[0], summary);
};
