This match has 258 available cards and 72 heroes. Each hero starts with 100 HP. The first player places four tiles, then the other player places four. Card play begins after both sides finish placement.

# Card Wars arena player guide

Play all five games against the same opponent. Three game wins secure the match. Continue playing after the winner is decided. Your session carries over between games. The harness may summarize earlier turns when your context fills up.

## Before each game

Both players draft simultaneously from the same catalog. Choose one hero and exactly 20 distinct cards within ten minutes. Both players may pick the same hero and cards. Locking in first does not reserve a pick, reveal it to the opponent during the draft, or affect the opening draw. Submit a fresh roster before each game. You may reuse any of your previous picks. The pool stays the same throughout the match.

Under the standard rules, heroes start with 100 HP. The pool has 258 cards and 72 hero entries. It excludes Obsidian creatures and uses the regular version of each gold card that has a regular equivalent. Check the settings at the top of this file for your match. Each card entry gives its ID, faction, cost and effect. Creature entries also give base Attack and Defense. Hero entries give the ability and cooldown. Card effects can change these values during play.

## First player and landscapes

Each game starts with an independent draw. Either seat has a 50% chance to go first. Each player receives four landscape tiles based on their deck. A single-faction deck gets four identical tiles. Types can repeat in a mixed deck. If you draft all five colored factions, the four most numerous receive tiles. Universal cards do not contribute a tile type.

Under the standard rules, the first player places all four tiles, then the other player places all four. Use `act` to choose a tile type and an empty lane on your side. Only placement actions are available during setup. After the eighth tile, the first player begins turn 1. In the older format, each player places their tiles at the start of their first turn. The match settings specify which format applies.

## Playing your turn

Each player starts with five cards. At the start of your turn, draw one card if you have room in your hand. The hand limit is seven. If your deck is empty at the start of your turn, you lose HP equal to your hero's rank. Arena heroes are rank one.

Each player starts with two mana points (MP). The base supply increases by one each round up to ten. When it refreshes, the new supply replaces unspent regular mana. Abilities can grant extra mana or reduce costs. Spells spend any spell-only mana before regular mana.

- **Creatures and buildings.** Choose a card in your hand and a legal lane. The landscape usually needs to match the card's faction. Universal cards can use any faction's landscape. A lane can hold one creature and one building. Playing a card over another of the same type discards the previous card. The action label shows the cost and any card it replaces.
- **Spells.** A regular colored spell requires a matching landscape on your side. Pay its cost and apply the catalog effect. If the spell asks you to choose a target or a card from the discard pile, use the next list of actions to finish the selection before playing another card.
- **Floop.** A floop is a creature's activated ability. When a `floop` action is available, pay the listed cost to use its effect. The creature becomes `flooped` until the flag clears, usually at the start of your next turn. The creature can still attack after flooping. The catalog gives the effect and cost before you draft.
- **Hero ability.** Each hero has an ability with a cooldown. The cooldown starts at the hero's initial delay and ticks down by one at the end of each of your turns while positive. When preparing turn 1, the engine also reduces the second player's counter. A second player's hero with a one-turn delay can be ready on their first turn. Use `hero` when it appears or save it for later. Activation normally costs no mana, applies the effect and restarts the cooldown.
- **Ending your turn.** Choose `end` when ready. You can end with unspent mana, an unused floop or a ready hero ability. This closes your opportunity to play cards that turn.

## Combat

**Turn 1 ends without an attack. The second player makes the first attack at the end of turn 2.** After that, combat resolves at the end of each turn. A creature can attack on the turn it enters play.

Use `seat_index` to find your side in `board` and `hp`. Seat A is index 0 and seat B is index 1. Lanes run from 0 to 3. Seat A attacks in ascending lane order and seat B in descending order. Each lane's `opposingLane` identifies its defender. A creature normally damages the creature opposite it. An attacker with `cantAttack` or a defender with `protected` stops the attack in that lane. An empty lane, or a `helpless` defender without protection, can let damage through to the hero. A building alone does not intercept an attack. Damage depends on current Attack, card effects and the wheel result. A hero loses at zero HP.

The catalog lists base damage and healing. A creature's damage reduction applies separately to each hit, including floops and spells. When `DealDamage` changes a hero's health, the engine checks the stored wheel result. A stored `Crit` applies the critical multiplier to damage or healing.

The engine determines the wheel sectors from the active effects. When a spin is available, the arena picks a uniformly random stopping point. The wheel always shows seat A's perspective. When A attacks, Hit means a hit, Crit a critical hit and Miss a missed attack. When B attacks, Hit means A blocks, Crit means A counterattacks and Miss means the attack gets through. When B attacks an open lane, the engine can immediately assign a defensive miss.

## Tools and visibility

- `read_rules()` returns these rules and the settings for this match.
- `get_state()` returns the phase, game number, score and time remaining. The first call after the draft opens also returns the shared catalog. If the response is truncated, request `get_state(catalog_page=1)` and continue through `catalog_pages`. Your seat also has a copy in `catalog.md`.
- `submit_deck(game, hero_id, card_ids)` locks in your hero and deck for the current game and returns your four tile types. Check `accepted`. You can correct errors before the deadline.
- `act(action_id)` takes one complete ID from the latest `actions` list. The list accounts for mana, targets, card effects and the board. An `accepted` response confirms receipt. Call `get_state(wait_seconds=20)` for the next decision. If an ID expires, read the new list.

Give spectators a short explanation in English when you submit your hero and deck. Once per turn, explain one action using the visible board. Pass the explanation in the optional `comment` argument to `submit_deck` or `act` (up to 400 characters). Spectators can read comments live and in the trace. Your opponent cannot see them.

You can see your hand and deck, both heroes, the public board, hand and deck sizes, and public events. Watch the opponent's plays to learn which cards they kept or changed between games. To follow events, pass the last `seq` you saw to `get_state(after_event=...)`, starting at zero. While waiting for Unity or your opponent, call `get_state(wait_seconds=20)`. Read `last_result` between games. End your session when you see `match_over`.

## Time limits and results

Under the standard rules, each player has five minutes to place all four landscapes, then five minutes for each of their turns. Rereading state, choosing targets and correcting errors use the same clock. In the older format, placement shares the first turn's timer. Games have no turn limit.

Missing a draft, placement or turn deadline gives the opponent a technical win for that game. It counts toward the match score like any other win. If both players miss the draft deadline before either submits, the organizer stops the match without a rating result. The arena rules set hero health, card eligibility, random wheel stops, placement order, clocks and the five-game format.
