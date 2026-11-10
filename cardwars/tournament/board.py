"""Render an offline, linkable leaderboard from the audited match records."""

import os
from html import escape
from math import ceil, floor
from urllib.parse import quote

from .bradley_terry import estimate
from .rating import Standing, standings, unique_matches, win_rate_interval

CSS = """
:root{color-scheme:light;font:16px/1.5 system-ui,sans-serif;color:#222c31;background:#f4f3ed}
body{margin:0}main{max-width:1080px;margin:0 auto;padding:48px 24px 64px}h1,h2,h3,p{margin:0 0 .6rem}
h1,h2{font-family:Georgia,serif;font-weight:500;line-height:1.1}h1{font-size:clamp(36px,6vw,66px)}
h2{font-size:30px}h3{font-size:18px;margin:1.3rem 0 .5rem}.muted,small{color:#586762}
header{border-bottom:2px solid #24453e;padding-bottom:22px}section{margin-top:2rem}
.cards{display:flex;gap:1rem;flex-wrap:wrap;margin:1.4rem 0 0}.stat{border-left:3px solid #287363;padding:0 1.2rem 0 .7rem}
.stat b{display:block;font-size:25px;font-weight:650}.stat span{font-size:14px}
.tablewrap{overflow-x:auto;margin:.85rem 0 1rem}table{width:100%;border-collapse:collapse;background:#fffef9}
th,td{padding:10px 12px;border-bottom:1px solid #d4d8cf;text-align:left;font-variant-numeric:tabular-nums}
th{font-size:13px;font-weight:600;color:#436256;background:#e6ebe2}td:first-child{font-weight:600}
.score{font-size:21px;color:#19584a}.tag{font-size:12px;background:#e5ece6;border-radius:9px;padding:2px 8px;white-space:nowrap}
a{color:#075b55;text-underline-offset:3px}a:focus-visible,summary:focus-visible{outline:3px solid #ae691b}
code{font-size:13px;overflow-wrap:anywhere}summary{cursor:pointer;color:#254a3f;font-weight:600}
footer{margin-top:2rem;border-top:1px solid #cad3c7;padding-top:1rem;font-size:14px}
@media(max-width:640px){main{padding:24px 12px 40px}th,td{padding:7px}.stat{padding-right:0}}
"""


def link(path, target, label):
    relative = os.path.relpath(path.resolve(), target.resolve().parent)
    return f'<a href="{escape(quote(relative), quote=True)}">{escape(label)}</a>'


def table(headers, rows):
    heads = "".join(f'<th scope="col">{escape(label)}</th>' for label in headers)
    body = "".join(
        "<tr>" + "".join("<td>" + cell + "</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f'<div class="tablewrap"><table><thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table></div>'


def policy_kind(value):
    return {
        "random": "Bot",
        "claude": "Claude Code",
        "codex": "Codex CLI",
        "command": "External process",
        "harness": "CLI assistant",
    }.get(value, value)


def render(records, target, scheduled, current_ruleset, completed, bt_entrants=None, profiles=None):
    records = list(unique_matches(records))
    participants = {}
    for record in records:
        participants.update(zip(record.rating_ids, record.player_profiles))
    participants.update(profiles or {})

    def participant(identity):
        label = participants.get(identity, {}).get("display_name", identity)
        if label == identity:
            return escape(identity)
        return f"{escape(label)}<br><small>{escape(identity)}</small>"

    def settings(identity, kind):
        p = participants.get(identity, {})
        if not p.get("model"):
            return escape(policy_kind(kind))
        return escape(" · ".join(filter(None, (p.get("harness"), p["model"], p.get("effort")))))

    boards = standings(records)
    rated = [m for m in records if m.rating_ids[0] != m.rating_ids[1]]
    current = [m for m in rated if m.ruleset == current_ruleset]
    seeds = {m.seed for m in current}
    parts = [
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>Card Wars Arena leaderboard</title><link rel="icon" href="data:,"><style>'
        + CSS
        + "</style><main><header>",
        "<h1>Card Wars Arena leaderboard</h1><p>Each match has five games. Winning at least three counts as one match win.</p>",
        '<div class="cards">',
    ]
    for value, label in (
        (f"{completed} / {scheduled}", "Scheduled matches completed"),
        (len(seeds), "Independent seeds"),
        (5 * len(current), "Games played"),
    ):
        parts.append(f'<div class="stat"><b>{value}</b><span>{label}</span></div>')
    parts.append("</div></header>")
    for ruleset in dict.fromkeys([current_ruleset, *boards]):
        group = [m for m in records if m.ruleset == ruleset]
        rows = boards.get(ruleset, {})
        title = {
            "legacy/from_deck/hp25": "Archive · landscapes assigned before battle",
            "legacy/on_turn/hp25": "Archive · landscapes placed during a turn",
        }.get(
            ruleset, "Tournament" if ruleset == current_ruleset else "Other ruleset"
        )
        parts.append(
            f'<section><h2>{title}</h2><p class="muted">Ruleset <code>{escape(ruleset)}</code></p>'
        )
        if bt_entrants and ruleset == current_ruleset:
            roster = {name: Standing(kind=kind) for name, kind in bt_entrants.items()}
            roster.update(rows)
            ratings, intervals = estimate(group, roster)
            entries = []
            for name in sorted(roster, key=lambda n: (-ratings.get(n, 0), n)):
                row = roster[name]
                interval = intervals.get(name)
                entries.append([
                    participant(name), settings(name, row.kind),
                    f"{ratings[name]:.1f}" if ratings else "—",
                    f"{interval[0]:.0f}–{interval[1]:.0f}" if interval else "—",
                    f"{row.wins}–{row.matches - row.wins}",
                    f"{row.games_won}–{5 * row.matches - row.games_won}",
                ])
            parts.append(table(["Participant", "Configuration", "Bradley–Terry (Elo)", "95% interval",
                                "Matches W–L", "Games W–L"], entries))
            if not ratings:
                parts.append("<p>Ratings become available once every participant is connected to every other by a chain of wins in both directions.</p>")
            parts.append("<p><small>Ratings are estimated jointly from match winners and centered on 1500. "
                         "Intervals are estimated by resampling whole matches within each pairing.</small></p>")
        elif rows:
            if set(rows) == {"random-uniform-v1", "random-play-first-v1"}:
                parts.append(
                    "<p>Both bots select their decks randomly. During play, uniform chooses each legal action "
                    "with equal probability. Play-first ends its turn only when "
                    "it has no other legal action.</p>"
                )
            entries = []
            for name, r in sorted(rows.items(), key=lambda x: (-x[1].rating, x[0])):
                bounds = win_rate_interval(r.wins, r.matches)
                interval = (
                    "—"
                    if bounds is None
                    else f"{floor(100 * bounds[0])}–{ceil(100 * bounds[1])}%"
                )
                entries.append(
                    [
                        participant(name),
                        f'<span class="tag">{settings(name, r.kind)}</span>',
                        f'<b class="score">{r.rating:.1f}</b>',
                        f"{r.wins}–{r.matches - r.wins}",
                        f"{r.games_won}–{5 * r.matches - r.games_won}",
                        str(len(r.opponents)),
                        interval,
                    ]
                )
            parts.append(
                table(
                    [
                        "Participant",
                        "Configuration",
                        "Elo",
                        "Matches W–L",
                        "Games W–L",
                        "Opponents",
                        "Win rate¹",
                    ],
                    entries,
                )
            )
            parts.append(
                "<p><small>¹ Conservative 95% interval for the match win rate, based on completed matches with independent seeds. "
                "An interval of 0–100% means that any win rate is consistent with the sample.</small></p>"
            )
        elif group:
            parts.append(
                "<p>The same random policy played both seats. These matches test the engine and are excluded from Elo.</p>"
            )
        else:
            parts.append(
                "<p>Results will appear after the first verified match.</p>"
            )
        if group:
            parts.append("<h3>Verified matches</h3>")
            entries = []
            for m in group:
                a, b = m.rating_ids
                if a == b:
                    a = f"{m.players[0]} · {a}"
                    b = f"{m.players[1]} · {b}"
                evidence = [
                    link(m.directory / "results.json", target, "Result"),
                    link(m.directory / "trace.jsonl", target, "JSONL"),
                ]
                if (m.directory / "trace.html").is_file():
                    evidence.insert(
                        0, link(m.directory / "trace.html", target, "View turns")
                    )
                entries.append(
                    [
                        participant(a),
                        participant(b),
                        f"{m.wins[0]}–{m.wins[1]}",
                        str(m.seed),
                        " · ".join(evidence),
                    ]
                )
            parts.append(
                table(
                    ["Seat A", "Seat B", "Game score", "Match seed", "Records"],
                    entries,
                )
            )
        parts.append("</section>")
    if bt_entrants:
        parts.append("<footer>Results are grouped by ruleset.</footer></main></html>")
        return "\n".join(parts) + "\n"
    parts.append(
        "<footer>Elo starts at 1500 with K = 32 and updates after every five-game match. "
        "Each ruleset has its own ratings.</footer></main></html>"
    )
    return "\n".join(parts) + "\n"
