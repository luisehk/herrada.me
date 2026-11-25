#!/usr/bin/env python3
"""Writes index.html, how-i-build.html and 404.html, the Field Guide (HM-0002, direction D).

The pages are plain static HTML, committed, and served as they are: nothing builds at run
time. This script exists so that ten sheets share one form and every count and date comes
from one file, build/counts.json. Run it from the repo root after changing that file:

    python3 build/build.py           # rewrite the three pages
    python3 build/build.py --check   # fail when a committed page differs from a rebuild (make ci)
"""
import json
import os
import re
import sys

import plate

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
PAGES = ("index.html", "how-i-build.html", "404.html")

with open(os.path.join(HERE, "counts.json"), encoding="utf-8") as fh:
    DATA = json.load(fh)

COUNTED = DATA["read"]
READ_YEAR, READ_MONTH = int(COUNTED[:4]), int(COUNTED[5:7])
P = DATA["projects"]
TREE = {t["sheet"]: t for t in DATA["plate"]}
YEARS = READ_YEAR - DATA["shipping_since"]
# The two font files (latin range), served from fonts/. style.css holds their @font-face
# rules. The pages only preload them, so the swap comes early.
FONT_FILES = ("fonts/fraunces-v38-latin.woff2", "fonts/instrument-sans-v4-latin.woff2")
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' rx='6' fill='%23EEF0E6'/%3E"
           "%3Cpath d='M15 26V15h2v11z' fill='%2317211C'/%3E"
           "%3Cpath d='M16 17c0-6-4-10-10-10 0 6 4 10 10 10zM16 15c0-6 4-10 10-10 0 6-4 10-10 10z' fill='%23A6481F'/%3E"
           "%3Crect x='5' y='25' width='22' height='2' fill='%2317211C'/%3E%3C/svg%3E")

PEND = '<span class="pend" lang="es">[pendiente]</span>'
WORDS = ["none", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
         "nineteen", "twenty"]


def num(n):
    """A count as the page prints it: 1,154."""
    return f"{n:,}"


def word(n, cap=False):
    """A small count spelled out, as the copy writes it: four, Thirteen."""
    w = WORDS[n] if 0 <= n < len(WORDS) else num(n)
    return w[:1].upper() + w[1:] if cap else w


def duration(minutes):
    h, m = divmod(minutes, 60)
    hours = f"{h} hour{'s' if h != 1 else ''}" if h else ""
    mins = f"{m} minute{'s' if m != 1 else ''}" if m else ""
    return " ".join(x for x in (hours, mins) if x)


def pend_then(mark):
    """The tag with the punctuation that follows it, kept on one line."""
    return f'<span class="nb">{PEND}{mark}</span>'
MONTHS = plate.MONTH_NAMES


def month_name(ym):
    """2024-08 as August 2024."""
    return f"{MONTHS[int(ym[5:7]) - 1]} {ym[:4]}"


def months_words(worked):
    """The months a sheet was worked on, as words: January to April, June and October.
    A run of three or more is written as a range."""
    runs, run = [], []
    for m in sorted(worked):
        if run and m == run[-1] + 1:
            run.append(m)
        else:
            if run:
                runs.append(run)
            run = [m]
    if run:
        runs.append(run)
    parts = []
    for r in runs:
        if len(r) >= 3:
            parts.append(f"{MONTHS[r[0] - 1]} to {MONTHS[r[-1] - 1]}")
        else:
            parts.extend(MONTHS[m - 1] for m in r)
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def months_between(start, end):
    """Calendar months from one YYYY-MM to another, both counted."""
    return (int(end[:4]) - int(start[:4])) * 12 + int(end[5:7]) - int(start[5:7]) + 1


def dashed_sentence():
    """Which dots are dashed on the count date: the months still ahead in the year."""
    if READ_MONTH == 12:
        return "Every month is counted."
    if READ_MONTH == 11:
        return "December is dashed: not counted yet."
    return f"{MONTHS[READ_MONTH]} to December are dashed: not counted yet."


def ind(text, n):
    pad = " " * n
    return "\n".join((pad + line) if line.strip() else line for line in text.strip("\n").split("\n"))


# ---------------------------------------------------------------- shared parts
def head(title, description, base=""):
    """base is "" for the pages at the root and "/" for 404.html, which nginx serves at any path."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="noindex">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#EEF0E6" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#1C150F" media="(prefers-color-scheme: dark)">
  <link rel="icon" href="{FAVICON}">
  <link rel="preload" as="font" type="font/woff2" crossorigin href="{base}{FONT_FILES[0]}">
  <link rel="preload" as="font" type="font/woff2" crossorigin href="{base}{FONT_FILES[1]}">
  <link rel="stylesheet" href="{base}style.css">
  <script src="{base}script.js" defer></script>
</head>
<!--
  A field guide to what I build.

  Sheet          this site
  Kind           personal site
  Status         preview
  Where it runs  static files: no framework, no tracking, complete without JavaScript
  Sources        written by build/build.py from build/counts.json (a rebuild overwrites this file)
  Last revised   {COUNTED}
-->"""


def masthead(current, base=""):
    def link(key, href, label):
        cur = ' aria-current="page"' if key == current else ""
        return f'<li><a href="{href}"{cur}>{label}</a></li>'
    record = "#record" if current == "guide" else f"{base}index.html#record"
    return f"""<a class="skip" href="#main">Skip to the content</a>
<header class="masthead">
  <a class="masthead__name" href="{base}index.html">Luis Herrada</a>
  <nav aria-label="Site">
    <ul>
      {link("guide", f"{base}index.html", "Guide")}
      {link("method", f"{base}how-i-build.html", "How I build")}
      {link("record", record, "Record")}
    </ul>
  </nav>
</header>"""


def footer(home_prefix=""):
    site = TREE["colophon"]
    return f"""<footer class="foot" id="colophon">
  <div class="foot__ground" aria-hidden="true">
    <svg viewBox="0 0 90 44" width="90" height="44" focusable="false">
      <path class="foot__root" d="M0 36.5C11 37.6 19.5 32.6 30 33.2S44.6 32.4 48.4 26.8S51.8 20.6 52 15.6"/>
      <circle class="foot__node" cx="52" cy="15.6" r="2.4"/>
      <g class="foot__sprout" transform="translate(52 12)">{"".join(plate.sprout(10))}</g>
      <g class="foot__figure"><circle cx="24" cy="3.55" r="1.55"/><rect x="22.25" y="5.45" width="3.5" height="3.9" rx="1.1"/><rect x="22.4" y="8.6" width="1.3" height="2.4"/><rect x="24.3" y="8.6" width="1.3" height="2.4"/></g>
    </svg>
  </div>
  <div class="foot__cols">
    <div>
      <h2 class="label">Colophon</h2>
      <p>Preview. Drawn by AI agents as a work item on my own board.</p>
      <p class="foot__small">This site is tree {site["n"]} on <a href="{home_prefix}#tree-{site["n"]}">the plate</a>: planted {site["planted"]}, {word(site["months"])} month{"s" if site["months"] != 1 else ""} tall, on Smithy&rsquo;s board. Set in Fraunces and Instrument Sans.</p>
    </div>
    <div>
      <h2 class="label">Elsewhere</h2>
      <ul class="foot__links">
        <li><a href="https://www.linkedin.com/in/luisehk">LinkedIn</a></li>
        <li><a href="https://github.com/luisehk">GitHub</a></li>
      </ul>
    </div>
  </div>
  <p class="foot__legal"><span>&copy; {READ_YEAR} Luis Herrada</span> <span>Preview.</span></p>
</footer>"""


# ---------------------------------------------------------------- sheet parts
STATES = ["sketch", "in dev", "pre-launch", "live", "done", "relic"]


def status(idx, word, sentence):
    segs = "".join('<i class="on"></i>' if i == idx else "<i></i>" for i in range(6))
    nth = f'<span class="vh"> (state {idx + 1} of 6)</span>' if idx >= 0 else ""
    return f"""<div class="field field--status">
  <dt>Status</dt>
  <dd class="status"><span class="status__bar" aria-hidden="true">{segs}</span><b>{word}</b>{nth}</dd>
  <dd>{sentence}</dd>
</div>"""


def months_field(worked, note="", words=None, read=COUNTED):
    """Twelve dots for the count date's year. worked holds month numbers, 1 for January.
    The months still ahead of the count date are dashed. The words are written from the
    dots unless a sheet passes its own."""
    letters = "JFMAMJJASOND"
    dots = []
    for i, letter in enumerate(letters):
        cls = ' class="on"' if i + 1 in worked else (' class="soon"' if i + 1 > READ_MONTH else "")
        dots.append(f"<i{cls}>{letter}</i>")
    if words is None:
        words = months_words(worked) + "."
    text = words + (" " + note if note else "")
    return f"""<div class="field">
  <dt>Worked on in {READ_YEAR} <span class="field__note">Counted {read}</span></dt>
  <dd><span class="months" aria-hidden="true">{"".join(dots)}</span>{text}</dd>
</div>"""


def tally(rows, note="Read " + COUNTED, label="Counts"):
    lis = "\n".join(f"      <li><b>{n}</b> <span>{unit}</span></li>" for n, unit in rows)
    return f"""<div class="field">
  <dt>{label} <span class="field__note">{note}</span></dt>
  <dd>
    <ul class="tally">
{lis}
    </ul>
  </dd>
</div>"""


def field(label, body, half=False, cls=""):
    c = "field" + (" field--half" if half else "") + (" " + cls if cls else "")
    return f"""<div class="{c}">
  <dt>{label}</dt>
  <dd>{body}</dd>
</div>"""


def notes(body):
    return f"""<details class="notes">
  <summary><span>Field notes</span></summary>
  <div class="notes__body">
{ind(body, 4)}
  </div>
</details>"""


def dated(rows):
    lis = "\n".join(f'  <li><time datetime="{iso}">{label}</time> <span>{text}</span></li>' for iso, label, text in rows)
    return f'<ul class="dated">\n{lis}\n</ul>'


def fold(summary, body, cls="", state="", fid=""):
    """A part of a sheet that a phone folds away. Under 960 px it is closed until tapped. Wider,
    the stylesheet hides the summary and shows the part, where the browser can (see .fold in
    style.css). Closed or open, it is in the page."""
    state_html = f' <span class="fold__state">{state}</span>' if state else ""
    c = "fold" + (" " + cls if cls else "")
    id_html = f' id="{fid}"' if fid else ""
    return f"""<details class="{c}"{id_html}>
  <summary><span>{summary}</span>{state_html}</summary>
{ind(body, 2)}
</details>"""


def sheet(s, level=3, folds=True):
    ref = s.get("ref")
    if ref:
        # the link lands on the plate and rings this sheet's own tree (see .ring in style.css)
        ref_html = f'<a href="#tree-{s["tree"]}">{ref}</a>'
    else:
        ref_html = "<span>Not on the plate</span>"
    name = s.get("name_html", s["name"])
    short = " sheet--short" if s.get("short") else ""
    first, more = [], []
    first.append(status(s["state_idx"], s["state_word"], s["state"]))
    if "challenge" in s:
        first.append(field("The complex challenge", s["challenge"], cls="field--pair"))
        first.append(field("The simple answer", s["answer"], cls="field--pair"))
    if "counts" in s:
        first.append(tally(s["counts"], note="Read " + s.get("read", COUNTED)))
    if "months" in s:
        more.append(months_field(s["months"], s.get("months_note", ""), s.get("months_words"), s.get("read", COUNTED)))
    if "facts" in s:
        more.append(field(s.get("facts_label", "Notes"), s["facts"]))
    if "where" in s:
        more.append(field("Where it runs", s["where"], half=True))
    src_half = "where" in s
    more.append(field("Sources", f'{s["sources"]} <span class="revised">Last revised {s.get("revised", COUNTED)}.</span>', half=src_half))

    def dl(parts, cls="fields"):
        return f'<dl class="{cls}">\n{ind(chr(10).join(parts), 2)}\n</dl>'

    if s.get("short"):
        # A short sheet is its name and its line. Its fields fold on a phone.
        body = fold("The sheet", dl(first + more), "fold--sheet", f'<span class="vh">Status: </span>{s["state_word"]}')
    elif folds:
        body = dl(first) + "\n" + fold(s.get("more_label", "Months, where it runs, sources"), dl(more, "fields fields--more"))
    else:
        body = dl(first + more)
    notes_html = ("\n" + ind(notes(s["notes"]), 4)) if "notes" in s else ""
    return f"""<article class="sheet{short} c-{s["cls"]}" id="{s["id"]}" aria-labelledby="{s["id"]}-name">
  <header class="sheet__head">
    <p class="sheet__kicker"><span>{s["kind"]}</span> {ref_html}</p>
    <h{level} class="sheet__name" id="{s["id"]}-name" style="--r:{s["r"]}">{name}</h{level}>
    <p class="sheet__line">{s["line"]}</p>
  </header>
  <div class="sheet__body">
{ind(body, 4)}{notes_html}
  </div>
</article>"""


# ---------------------------------------------------------------- the sheets
SM, RV, AR, VP = P["smithy"], P["rentaventa"], P["arbopedia"], P["vim-puzzles"]
LI, MG, BU, MT = P["lichess-irl"], P["minigames"], P["budgeter"], P["rentaventa-meet"]
TREE_N = {t["n"]: t for t in DATA["plate"]}
RV_MONTHS = TREE["rentaventa"]["months"]
_rv_gap = months_between(RV["began"], COUNTED[:7]) - RV_MONTHS
RV_GAP = f" but {word(_rv_gap)}" if _rv_gap else ""

SHEETS = [
    dict(
        id="smithy", cls="smithy", ref="Plate 1, tree 8", tree=8, kind="Tool, for one user", name="Smithy", r=3.0,
        line="The workshop where AI agents build my software and I keep the decisions.",
        state_idx=3, state_word="In use", state="In daily use since October 2026. Private.",
        challenge="AI agents can write code faster than one person can follow.",
        answer="A board that moves only on facts, a ledger of decisions, and one short list of what needs me.",
        read=SM["read"], months=SM["worked"], months_note=f"It was {SM['age_days']} days old on the count date.",
        counts=[(num(SM["work_items"]), f"work items, {num(SM['work_items_done'])} done"), (num(SM["gate_verdicts"]), "gate verdicts"),
                (num(SM["decisions"]), "decisions written"), (num(SM["reports"]), "reports"),
                (num(SM["projects_on_board"]), "projects on one board")],
        where="Claude Code sessions on my own machines.",
        sources='Private repository. The method is public: <a href="how-i-build.html">How I build with agents</a>.',
        notes="""<p>Smithy is the tool I built to build everything else. Work items move across a board only when something real happens: a claim, a passed gate, a merge, a deploy. Agents do the work and stamp each gate. Decisions go in a ledger. Anything that needs me lands in one short list.</p>
""" + dated([
            (TREE["smithy"]["planted"], TREE["smithy"]["planted"], "First commit. Built with itself from that day."),
            ("2026-10", "October 2026", "vim-puzzles becomes its first outside pilot."),
            ("2026-11", "November 2026", f"{word(SM['projects_on_board'], True)} projects on one board, this site among them."),
        ]) + """
<p>One person, many agents, one record.</p>""",
    ),
    dict(
        id="rentaventa", cls="rentaventa", ref="Plate 1, tree 2", tree=2, kind="Product, built with a partner", name="Rentaventa", r=4.83,
        line="Rent and sale listings for Monterrey, built for brokers who work from WhatsApp.",
        state_idx=2, state_word="Pre-launch", state="Since August 2024.",
        challenge="Brokers in Monterrey live in WhatsApp.",
        answer="Meet them there. A broker publishes a listing, sends photos or works a lead in a chat with an agent.",
        read=RV["read"], months=RV["worked"], months_note=f"{RV_MONTHS} months with work in all: every month since {month_name(RV['began'])}{RV_GAP}.",
        counts=[(num(RV_MONTHS), "months with work"), ("about " + num(RV["repositories"]), "repositories"),
                (num(RV["decisions"]), "decisions written"), (PEND, "launch date")],
        where="WhatsApp, the web and a phone.",
        sources='<a class="src" href="https://rentaventa.mx">rentaventa.mx (in Spanish)</a>.',
        notes="""<p>Rentaventa is the product I am building with a partner for real-estate brokers in Monterrey. Listings for rent and sale on a map, a CRM for leads, and two ways to work without opening a dashboard: a WhatsApp agent for brokers and a Claude connector for the team. Pre-launch.</p>
""" + dated([
            (RV["began"], month_name(RV["began"]), "It begins."),
            ("2025-11", "November 2025", "The web app is rebuilt in React."),
            ("2026-03", "March 2026", "The WhatsApp agent."),
            ("2026-04", "April 2026", "The mobile app."),
            ("2026-10", "October 2026", "The Claude connector."),
            ("2026-11", "November 2026", "Broker rooms, in progress."),
        ]) + """
<p>The WhatsApp agent runs on Claude. Every write through the connector is a preview first and a commit after approval. Behind them: a Django and PostGIS API, a React web app with server-rendered property pages, a React Native app, a small k3s cluster.</p>""",
    ),
    dict(
        id="arbopedia", cls="arbopedia", ref="Plate 1, tree 1", tree=1, kind="Open archive", name="arbopedia", r=4.46,
        name_html='arbopedia<span class="mark-dot" aria-hidden="true">.</span>',
        line="An open archive of the trees of Mexico.",
        state_idx=3, state_word="Live", state=f"{num(AR['sheets'])} sheets on {AR['read']}. In progress, and it says so.",
        challenge="Every tree of Mexico, with a source behind every fact.",
        answer=f"One sheet per species, read from printed field guides page by page. What is not verified prints {pend_then(".")}",
        read=AR["read"], months=AR["worked"],
        months_note=f"{word(TREE['arbopedia']['months'], True)} months with work in all: "
                    + ", ".join(f"{word(n)} in {y}" for y, n in AR["months_by_year"].items()) + ".",
        counts=[(num(AR["sheets"]), "sheets"), (num(AR["pages_read"]), "pages read"), (num(AR["printed_works"]), "printed works"),
                (num(AR["decisions"]), "decisions written"), (PEND, "species still to go")],
        where="The web. Server-rendered pages, no build step, works without JavaScript.",
        sources='<a class="src" href="https://arbopedia.mx">arbopedia.mx (in Spanish)</a>.',
        notes="""<p>arbopedia is an open archive of the trees of Mexico. Every species gets a sheet: its scientific name, the names people use where it grows, its height drawn next to a person, where it has been found and the months it flowers. Every fact cites the page it came from. What is not verified prints """ + pend_then(".") + """</p>
""" + dated([
            ("2023", "2023", "The first version."),
            ("2026-07", "July to September 2026", "Rebuilt as an open archive with its own design system."),
            (AR["read"], AR["read"], f"{num(AR['sheets'])} sheets, {num(AR['pages_read'])} pages read across {num(AR['printed_works'])} printed works."),
        ]) + """
<p>Checked against GBIF, the IUCN Red List and POWO. Indigenous names are never translated and always carry their language. Colour contrast is recomputed from the CSS on every CI run. One Instagram post a day. Texts are CC BY-SA 4.0.</p>""",
    ),
    dict(
        id="vim-puzzles", cls="vim", ref="Plate 1, tree 6", tree=6, kind="Trainer", name="vim-puzzles", r=4.9,
        name_html='<span class="mark-cursor">v</span>im-puzzles',
        line="Vim puzzles, scored against par.",
        state_idx=3, state_word="Live", state="At vim.herrada.me. Never announced.",
        challenge="I use vim all day, and this is the trainer I wanted.",
        answer=f"{num(VP['puzzles'])} short puzzles in a real vim emulation, each scored against par. No accounts and no backend.",
        read=VP["read"], months=VP["worked"], months_note=f"First commit {TREE['vim-puzzles']['planted']}.",
        counts=[(num(VP["puzzles"]), "puzzles"), (num(VP["categories"]), "categories"), (num(VP["lessons"]), "lessons"),
                (num(VP["decisions"]), "decisions written")],
        where="The browser, no server side.",
        sources='<a class="src" href="https://vim.herrada.me">vim.herrada.me</a>.',
        notes=f"""<p>vim-puzzles is a trainer for vim: {num(VP['puzzles'])} short editing puzzles in a real vim emulation in the browser, each scored against par like golf. No accounts and no backend. Progress stays in your browser.</p>
""" + dated([
            (TREE["vim-puzzles"]["planted"], TREE["vim-puzzles"]["planted"], "First commit."),
            ("2026-10", "October 2026", f"The corpus reaches {num(VP['puzzles'])} puzzles, and the app becomes Smithy&rsquo;s first outside pilot."),
        ]) + """
<p>Three stars at or under par. Every solution is replayed by the real engine in CI, so no puzzle ships unless it is solvable at its par. It looks like tmux panes in Solarized Dark because that is what my terminal looks like.</p>""",
    ),
    dict(
        id="lichess-irl", cls="lichess", ref="Plate 1, tree 7", tree=7, kind="One-desk tool", name="lichess-irl", r=4.01,
        line="Online chess on a real board.",
        state_idx=2, state_word="Pre-launch", state="Code complete. The first full game on the board is still ahead.",
        challenge="Chess is better on a real board.",
        answer="A webcam above the board, four printed markers at its corners, a voice for the opponent&rsquo;s move, and the space bar as the clock.",
        read=LI["read"], months=LI["worked"], months_note="The piece set came earlier, in December 2025.",
        counts=[(num(LI["markers"]), "printed markers"), (num(LI["decisions"]), "decisions written"), (PEND, "first full game on the board")],
        where="One desk.",
        sources='Private repository. The piece set is public: <a href="https://github.com/luisehk/flutter-chessground/tree/add-cubesandpi-3d-piece-set">a branch on my fork of flutter-chessground (GitHub)</a>.',
        notes="""<p>lichess-irl lets me play Lichess on a physical board. A webcam looks straight down, the app reads my opponent&rsquo;s moves out loud, I make my move on the board and press the space bar like a chess clock. Built for exactly one desk.</p>
""" + dated([
            ("2025-12", "December 2025", "A 3D piece set for the board package behind the Lichess mobile app. A branch on a public fork, not merged upstream."),
            ("2026-08", "August 2026", "lichess-irl."),
        ]) + """
<p>Rapid games at 15+10. Moves go through the official Lichess Board API. A terminal interface shows the board, both clocks and a running log. The four markers sit just outside the board&rsquo;s corners, numbered 0 to 3 clockwise from the top left as the camera sees them.</p>""",
    ),
    dict(
        id="minigames", cls="games", ref="Plate 1, trees 4 and 5", tree=5, kind="Games", name="minigames", r=4.52,
        line=f"{word(MG['games'], True)} tiny games, one architecture.",
        state_idx=4, state_word="Done", state="Built in one week, August 2026. Private.",
        challenge=f"{word(MG['games'], True)} games without {word(MG['games'])} architectures.",
        answer="One pure function steps every world. The same seed and the same inputs give the same game, so every game is tested without a screen.",
        read=MG["read"], months=MG["worked"], months_note=f"{word(MG['games'], True)} games from {MG['first_game']} to {MG['last_game']}.",
        counts=[(num(MG["games"]), "games"), (num(MG["tests_at_least"]) + "+", "tests"), (num(MG["weeks"]), "week" if MG["weeks"] == 1 else "weeks"),
                (num(MG["decisions"]), "decisions written")],
        where="A desktop window, in Python.",
        sources="Private repository.",
        notes=f"""<p>minigames is a family of {num(MG['games'])} tiny 2D games in Python: catch, snake, breakout, a platformer, air hockey, a nine-car racer. They share one architecture and one quality gate, and each has its own generated 8-bit tune.</p>
""" + dated([
            (TREE_N[4]["planted"], TREE_N[4]["planted"], "pyplatformer, the sketch: a window, a cloud and a collision box. It is tree 4 on the plate."),
            (MG["first_game"], f"{MG['first_game']} to {MG['last_game']}", f"{word(MG['games'], True)} games."),
        ]) + """
<p>Every shape is a placeholder that can be swapped for a drawing in two lines. The menu gives each game a hook of a few words: &ldquo;catch what falls&rdquo;, &ldquo;grow long, don&rsquo;t crash&rdquo;, &ldquo;thread the gaps&rdquo;, &ldquo;run, jump, dash&rdquo;, &ldquo;two players, one keyboard&rdquo;.</p>""",
    ),
]

SHORTS = [
    dict(
        id="budgeter", cls="slate", short=True, ref="Plate 1, tree 3", tree=3, kind="Personal tool", name="budgeter", r=3.7,
        line="A budget that stays in your browser. Bank statements in, a budget out, nothing uploaded.",
        state_idx=3, state_word="Live", state="In Spanish.",
        read=BU["read"], months=BU["worked"], months_note=f"First commit {TREE['budgeter']['planted']}.",
        facts=f"At least my third try at this since 2015. Decisions written: {word(BU['decisions'])}.",
        sources='<a class="src" href="https://budgeter.herrada.me">budgeter.herrada.me (in Spanish)</a>.',
    ),
    dict(
        id="rentaventa-meet", cls="slate", short=True, ref="Plate 1, tree 9", tree=9, kind="Team tool", name="rentaventa-meet", r=6.9,
        line="Video calls that file their own action items.",
        state_idx=3, state_word="In use", state="Used by the Rentaventa team. Private.",
        read=MT["read"], months=MT["worked"], months_note=f"First commit {TREE['rentaventa-meet']['planted']}.",
        facts=f"After a call an agent writes the notes and files the action items on my board. {num(MT['decisions'])} decisions written.",
        sources="Private repository.",
    ),
    dict(
        id="the-desk", cls="slate", short=True, ref=None, kind="Working setup", name="The desk", r=3.7,
        line="i3, tmux and vim. Keyboard first, distractions blocked.",
        state_idx=3, state_word="In use", state="Where I work. On Smithy&rsquo;s board.",
        facts=f"Months with work: {pend_then('.')} So it has no tree on the plate.",
        sources="Private repository.",
    ),
    dict(
        id="crispy-wookie", cls="slate", short=True, ref=None, kind="Earlier", name="crispy-wookie", r=5.81,
        line="I have wanted one place for everything since 2015.",
        state_idx=5, state_word="Relic", state="2015. Public.",
        facts="Its README: &ldquo;I want everything in one single place instead of using 30 different apps.&rdquo; The ancestor of budgeter and, in spirit, of Smithy.",
        sources='<a class="src" href="https://github.com/luisehk/crispy-wookie">crispy-wookie (GitHub)</a>.',
    ),
]


# ---------------------------------------------------------------- the plate and its key
def key_table():
    rows = []
    for n, name, months, planted, board, cls, href in plate.TREES:
        board_html = {"yes": '<span class="key__root" aria-hidden="true"></span>yes',
                      "no": '<span class="key__free" aria-hidden="true"></span>no',
                      "own": '<span class="key__root" aria-hidden="true"></span>its own'}[board]
        when = f'<time datetime="{planted}">{planted}</time>'
        rows.append(f"""<tr class="k{n} c-{cls}">
  <td><span class="chip">{n}</span></td>
  <th scope="row"><a href="{href}">{name}</a> <span class="key__when">planted {when}</span></th>
  <td class="num">{months}</td>
  <td class="num key__planted">{when}</td>
  <td>{board_html}</td>
</tr>""")
    body = "\n".join(rows)
    return f"""<table class="key">
  <caption>Key to Plate 1</caption>
  <thead>
    <tr><th scope="col"><abbr title="Number">No.</abbr></th><th scope="col">Tree</th><th scope="col" class="num">Months</th><th scope="col" class="num key__planted">Planted</th><th scope="col"><span class="vh">On Smithy&rsquo;s </span>Board</th></tr>
  </thead>
  <tbody>
{ind(body, 4)}
  </tbody>
</table>"""


def tree_anchors():
    """Ten empty anchors at the top of the plate. A link to #tree-8 lands on the plate, and the
    stylesheet rings tree 8 and marks its row in the key. No script is involved."""
    return "".join(f'<span class="plate__at at{n}" id="tree-{n}"></span>' for n in range(1, 11))


def mini_status():
    return ('<span class="status__bar" aria-hidden="true">'
            + "".join('<i class="on"></i>' if i == 3 else "<i></i>" for i in range(6)) + "</span>")


def mini_months():
    cells = "".join('<i class="on"></i>' if m in SM["worked"] else ('<i class="soon"></i>' if m > READ_MONTH else "<i></i>")
                    for m in range(1, 13))
    return f'<span class="months months--mini" aria-hidden="true">{cells}</span>'


def front():
    """The front of the guide, written in the order a phone reads it: the cover line, the plate,
    the paragraph that says what the plate holds, the key, how to read a sheet. On a desk the
    same five blocks stand in two columns (see section 10 of style.css). On a phone the key and
    the legend fold, so the first sheet starts on the second screen."""
    on_board = [t for t in DATA["plate"] if t["board"] == "yes"]
    together = plate.planted_together()
    month = month_name(together[0]["planted"][:7]) if together else ""
    together_sentence = f" {word(len(together), True)} of them were planted in {month}." if together else ""
    free = [t for t in together if t["board"] == "no"]
    fed = [t for t in together if t["board"] == "yes"]
    key_note = "Trees stand from left to right in the order of their first commit."
    if together:
        key_note += (f" {word(len(together), True)} were planted in {month}, before the workshop existed."
                     f" {word(len(free), True)} of them stand free.")
        if len(fed) == 1:
            key_note += f" The {['first', 'second', 'third', 'fourth', 'fifth', 'sixth'][len(together) - 1]}, {fed[0]['name']}, became Smithy&rsquo;s first outside pilot."
    key_html = f"""{key_table()}
<p class="key__note">{key_note}</p>"""
    howto_html = f"""<section aria-labelledby="howto-title">
  <h2 class="label fold__title" id="howto-title">How to read a sheet</h2>
  <p>Every project gets one sheet, in the form my tree archive gives a species.</p>
  <dl class="howto__list">
    <div><dt>{mini_status()}Status</dt><dd>Six states, in order: sketch, in dev, pre-launch, live, done, relic. One is filled. A private tool in daily use reads &ldquo;in use&rdquo; where a public one reads &ldquo;live&rdquo;.</dd></div>
    <div><dt>{mini_months()}Worked on in {READ_YEAR}</dt><dd>Twelve dots, one per month. A filled dot is a month with at least one commit. {dashed_sentence()}</dd></div>
    <div><dt>{PEND}</dt><dd>Not verified yet. The word is the archive&rsquo;s.</dd></div>
  </dl>
</section>"""
    return f"""<div class="front">
  <section class="cover" aria-labelledby="cover-title">
    <h1 id="cover-title">A field guide to what I build.</h1>
    <p class="cover__by">Luis Herrada, software engineer in Monterrey, shipping since {DATA["shipping_since"]}.</p>
  </section>

  <section class="plate" id="plate" aria-labelledby="plate-title">
    {tree_anchors()}
    <div class="plate__head">
      <h2 class="label" id="plate-title">Plate 1&thinsp;&middot;&thinsp;The stand</h2>
      <p class="label">Counted {COUNTED}</p>
    </div>
    <figure>
      <p class="vh">{word(len(plate.TREES), True)} projects drawn as trees on one ground line, planted from left to right in the order of their first commit. Each tree is as tall as the months with work in it.{together_sentence} Under the ground line Smithy&rsquo;s roots run to the {word(len(on_board))} projects on its board. The key below lists all {word(len(plate.TREES))}.</p>
      <div class="stand">
{plate.plate_svg("        ")}
        <span class="stand__sentinel" aria-hidden="true"></span>
      </div>
      <figcaption>
        <p class="plate__say">The tall one is Rentaventa. The sprout {word(TREE["smithy"]["months"])} month{"s" if TREE["smithy"]["months"] != 1 else ""} tall is Smithy, and its roots already reach {word(len(on_board))} of the others.</p>
        <p>Height: months with work, counted {COUNTED}. One figure is one month. Below the line: Smithy&rsquo;s roots, drawn only to the projects on its board.</p>
      </figcaption>
    </figure>
  </section>

  <div class="cover__more">
    <p class="cover__lede">With a partner I build <a href="#rentaventa">Rentaventa</a>, a real-estate platform for the city&rsquo;s brokers. On my own I build <a href="#smithy">Smithy</a>, the workshop where AI agents do most of my building and I keep the decisions.</p>
    <p class="cover__next">Read <a href="how-i-build.html">how I build with agents</a>, or <a href="#key">pick a tree</a>.</p>
    <dl class="cover__small">
      <div><dt>Creed</dt><dd>Simple, maintainable solutions to complex problems.</dd></div>
      <div><dt>Note</dt><dd>What I have not verified prints {pend_then(":")} pending.</dd></div>
      <div><dt>Edition</dt><dd>{DATA["edition"]}.</dd></div>
    </dl>
  </div>

{ind(fold("Key to Plate 1", key_html, "keywrap", word(len(plate.TREES), True) + " trees", fid="key"), 2)}

{ind(fold("How to read a sheet", howto_html, "howto"), 2)}
</div>"""


# ---------------------------------------------------------------- the author's sheet
def author():
    DX = DATA["decisions_across_projects"]
    return f"""<article class="sheet sheet--author c-site" id="author" aria-labelledby="author-name">
  <header class="sheet__head">
    <p class="sheet__kicker"><span>The author</span> <span>Software engineer</span></p>
    <h2 class="sheet__name" id="author-name" style="--r:5.46">Luis Herrada</h2>
    <p class="sheet__line">I build software, and the workshop that builds it with me.</p>
    <img class="author__face" src="assets/avatar.webp" width="96" height="96" alt="An illustrated portrait of Luis: dark hair, a beard and glasses." loading="lazy" decoding="async">
  </header>
  <div class="sheet__body">
    <dl class="fields author__facts">
      <div class="field field--half">
        <dt>Based in</dt>
        <dd>Monterrey, Mexico.</dd>
      </div>
      <div class="field field--half">
        <dt>Shipping since</dt>
        <dd>{DATA["shipping_since"]}. {YEARS}+ years.</dd>
      </div>
      <div class="field">
        <dt>Now <span class="field__note">{DATA["edition"]}</span></dt>
        <dd>Getting Rentaventa ready for launch, and handing Smithy more of the work.</dd>
      </div>
    </dl>
    <div class="author__cols">
      <div class="author__col">
        <section class="prose" aria-labelledby="about-title">
          <h3 class="label" id="about-title">About</h3>
          <p>I&rsquo;m Luis, a software engineer in Monterrey, Mexico. I have spent {YEARS}+ years taking products from the first idea to production, and I still like the simple solution best. Today I build Rentaventa, a real-estate platform for the city&rsquo;s brokers, with a partner. I also build Smithy, the workshop where AI agents do most of my building and I keep the decisions. The rest is for the love of it: an archive of Mexico&rsquo;s trees, a vim trainer, chess on a real board, a box of tiny games.</p>
        </section>
        <details class="fold fold--prose">
        <summary><span>How I work</span></summary>
        <section class="prose" aria-labelledby="work-title">
          <h3 class="label fold__title" id="work-title">How I work</h3>
          <p>From 2016 to 2019 I ran Vordem, a digital product agency. Its home page had a heading I still work by: &ldquo;A balanced approach.&rdquo; Strategists, developers, designers and product managers on one problem, looking for the simple answer. Today agents hold some of those seats. One shapes the work with me. One argues with the design before any code exists. One builds. A panel of reviewers reads the result and never sees the plan. The decisions stay with me.</p>
          <p>I work in a terminal: i3, tmux, vim. Every project I own has one command that has to pass before anything ships, and a written record of why things are the way they are. That holds for the real-estate platform and for the tiny games.</p>
          <p><a href="how-i-build.html">How I build with agents</a> has the whole method.</p>
        </section>
        </details>
      </div>
      <div class="author__col">
        <details class="fold fold--prose">
        <summary><span>Habits</span></summary>
        <section class="prose" aria-labelledby="habits-title">
          <h3 class="label fold__title" id="habits-title">Habits</h3>
          <ul class="habits">
            <li>One command gates every repo. Nothing ships that does not pass.</li>
            <li>I write down why. More than {num(DX["more_than"])} decision records across {word(DX["projects"])} projects, {word(MG["decisions"])} of them for {word(MG["games"])} tiny games.</li>
            <li>Status is stated as it is. Pre-launch means pre-launch.</li>
            <li>Machines check the work. Every vim puzzle is replayed in CI. Every game is replayed from a seed.</li>
          </ul>
        </section>
        </details>
        <details class="fold fold--prose">
        <summary><span>Beyond code</span></summary>
        <section class="prose" aria-labelledby="beyond-title">
          <h3 class="label fold__title" id="beyond-title">Beyond code</h3>
          <p>Away from the keyboard: guitar, chess, science articles and a good book.</p>
          <dl class="beyond">
            <div><dt>Guitar</dt><dd>Self-taught as a teenager. Mostly leads where a few notes carry the line. My pedal settings sheet has two songs filled in. The rows for Shine On You Crazy Diamond are still blank.</dd></div>
            <div><dt>Chess</dt><dd>Rapid, 15+10. Soon on a real board.</dd></div>
          </dl>
        </section>
        </details>
        <p class="motto">My advice has been the same since 2019: just start and keep practicing.</p>
      </div>
    </div>
    <section class="prose author__record" id="record" aria-labelledby="record-title">
      <h3 class="label" id="record-title">Before <span class="field__note">The record, 2008 to 2019</span></h3>
      <ol class="record">
        <li><time datetime="2008">2008</time> <span>First software job. Mobile, web and games at four companies until 2014.</span></li>
        <li><time datetime="2013">2013</time> <span>B.S. in Software Development, Universidad Tec Milenio, Monterrey.</span></li>
        <li><time datetime="2014">2014 to 2016</time> <span>Tech lead at BanregioLABS, Monterrey. Banking APIs and mobile banking. Led the move to service-oriented architecture and brought in continuous integration.</span></li>
        <li><time datetime="2016">2016 to 2019</time> <span>Founder and head of tech at Vordem, a remote-first digital product agency in Monterrey. A team of ten, 10+ products shipped, for startups and big companies in finance, retail, transportation and education.</span></li>
        <li><time datetime="2019">2019</time> <span>Talks at local meetups and three posts on my site. &ldquo;Just start and keep practicing.&rdquo;</span></li>
      </ol>
      <p class="record__rest">The rest of the record is on <a href="https://www.linkedin.com/in/luisehk">LinkedIn</a>.</p>
    </section>
  </div>
</article>"""


def index():
    sheets = "\n\n".join(ind(sheet(s), 6) for s in SHEETS)
    shorts = "\n\n".join(ind(sheet(s), 6) for s in SHORTS)
    return f"""{head("Luis Herrada, software engineer", "Luis Herrada is a software engineer in Monterrey. He builds Rentaventa, Smithy and a few things for the love of it.")}
<body class="page-guide">
{masthead("guide")}
<main id="main">
{ind(front(), 2)}

  <section class="sheets" id="sheets" aria-labelledby="sheets-title">
    <div class="rule">
      <h2 class="label" id="sheets-title">The sheets</h2>
      <p class="label">{word(len(SHEETS), True)} projects</p>
    </div>
    <div class="sheets__grid">
{sheets}
    </div>
  </section>

  <section class="sheets sheets--short" aria-labelledby="shorts-title">
    <div class="rule">
      <h2 class="label" id="shorts-title">One line each</h2>
      <p class="label">{word(len(SHORTS), True)} more</p>
    </div>
    <div class="sheets__grid sheets__grid--short">
{shorts}
    </div>
  </section>

  <section class="sheets sheets--author" aria-label="The author">
    <div class="rule">
      <p class="label">The last sheet</p>
      <p class="label">Who wrote this</p>
    </div>
    <div class="sheets__grid sheets__grid--one">
{ind(author(), 6)}
    </div>
  </section>
</main>
{footer()}
</body>
</html>
"""


# ---------------------------------------------------------------- the method page
COLUMNS = ["Grooming", "Backlog", "Next up", "In dev", "In QA", "In code review", "To be deployed", "Done"]

# VP-0010, one real item: its dates and minutes come from counts.json ("vp0010").
VP10 = DATA["vp0010"]
VP10_MIN = VP10["minutes_after_decision"]
EVENTS = [
    ("Filed", f", {VP10['filed']}.", None),
    ("Groomed", " the same day. Its definition is complete: a small item, copy only, gates ci and review, one question open.", None),
    ("Decided", f", {VP10['decided']}: the recommended answer, drop the promise. The item is ranked.", None),
    ("Claimed and built", f", {duration(VP10_MIN['built'])} later. A branch and a pull request.", "ci: pass"),
    None,
    ("Reviewed", f", {duration(VP10_MIN['reviewed'])} after the decision.", "review: pass"),
    ("Merged", f", {duration(VP10_MIN['merged'])} after the decision.", None),
    ("Deployed", f", {duration(VP10_MIN['deployed'])} after the decision.", "deploy: pass"),
]

STEPS = [
    ("Shape", "An idea becomes a work item with a problem, context, acceptance criteria and a test plan. Its mode is set here: autonomous or review."),
    ("Review the design", "Bigger items get a written design and an adversarial review before any code exists."),
    ("Build", "An agent claims the item, works in its own copy of the repo and opens a pull request."),
    ("Pass the gates", "<code>make ci</code> on the exact commit. A gauntlet of reviewers for correctness, security, QA and UX, who see the diff and the evidence and never the plan. An end-to-end run against a real local stack. Each gate leaves a stamp: a verdict tied to a commit."),
    ("Land", "An autonomous item merges and deploys when every stamp is green, and leaves a summary to read later. A review item stops at a ready pull request and waits for me."),
    ("Ask only what matters", "Critical questions arrive with options, a recommended answer, the cost to reverse and what happens if I do nothing. The agent then moves to other work. Every other judgment call is made, logged with its reason and reviewed later."),
    ("Learn", "On a fixed rhythm each session turns what it learned into a skill, a note or a new work item."),
    ("Pace", "A governor starts new runs only when there is headroom, so a long night of work never hits a wall."),
]

RULES = [
    "Record decisions as short records. Bodies never change. A new record supersedes an old one.",
    "Columns are derived from facts.",
    "Convention over configuration: the standard make targets are the contract with every project.",
    "An item&rsquo;s mode is set at grooming: autonomous items land and deploy when green, review items wait for me.",
    "The window is a viewer. Every change goes through a session and the API.",
    "Reports are a first-class record.",
    "Every working session turns its lessons into skills.",
    "Gated pull requests land by default.",
    "Nothing waits for me unless it is destructive.",
    "Everything that waits on me lives in one list.",
    "Pace the agents with a governor.",
    "Calls feed the record: each transcript becomes a summary and work items.",
]

ITEMS = [
    ("HM-0001", "site", "This site", "Five design directions for herrada.me, each a working prototype, critiqued, refined and curated.", "Autonomous", "In dev", "Filed 2026-11-25."),
    ("HM-0002", "site", "This site", "Build the herrada.me direction Luis picks.", "Review", "Held", ""),
    ("VP-0002", "vim", "vim-puzzles", "Readability pass on the Solarized palette: every text pair at WCAG AA, a visible visual-mode selection.", "Autonomous", "Done", ""),
    ("VP-0003", "vim", "vim-puzzles", "About page as window 3, a vim-style 404 and error boundary, per-route document titles.", "Autonomous", "Done", ""),
    ("VP-0006", "vim", "vim-puzzles", "Twelve puzzles for the unused tags and six one-key motion warm-ups (corpus to 200).", "Autonomous", "Done", ""),
    ("VP-0007", "vim", "vim-puzzles", "Phones and touch: a desktop-keyboard notice in the player, a status bar that never clips.", "Autonomous", "Done", ""),
    ("VP-0008", "vim", "vim-puzzles", "Keyboard flow: Enter and r after a solve, ex commands for reset, skip, give up and quit.", "Autonomous", "Done", ""),
    ("VP-0010", "vim", "vim-puzzles", "Copy fix: stop promising a daily set until one exists.", "Autonomous", "Done", ""),
    ("AR-0001", "arbopedia", "arbopedia", "Stop posting Instagram stories, keep the daily feature posts.", "Autonomous", "Done", ""),
]

SEATS = [
    ("Strategy", "A strategist.", "An agent and I shape an idea into a work item with a problem, context, acceptance criteria and a test plan."),
    ("Design", "Designers.", "Bigger items get a written design, and an agent argues with it before any code exists."),
    ("Development", "Developers.", "The smiths. Each claims an item, works in its own copy of the repo and opens a pull request."),
    ("Product", "Product managers.", "A board that moves only on facts, and one list of what needs me."),
]

PARTS = [
    ("The shop floor", "A board of work items. Columns change only through events."),
    ("The ledger", "Decision records. Short, numbered, never rewritten, only superseded."),
    ("The tools on the wall", "Reusable skills and harnesses the agents pick up: a design review, the gauntlet, end-to-end runs, reports."),
    ("The smiths", "Claude Code sessions on my own machines."),
    ("Needs you", "The one list of what waits on me: questions, steps for my hands, reviews."),
    ("The window", "The web view of the record. It reads. I steer through a session."),
]


def strip(states):
    """A strip of eight stages with one dot each, the way a sheet shows flowering months."""
    cells = "".join(f'<span><i class="dot{(" " + s) if s else ""}">{i + 1}</i></span>' for i, s in enumerate(states))
    return f'<div class="strip" aria-hidden="true">{cells}</div>'


def strip_form():
    lis = "\n".join(f"  <li>{c}</li>" for c in COLUMNS)
    return strip([""] * 8) + f'\n<ol class="stages">\n{lis}\n</ol>'


def strip_item():
    lis = []
    for i, (col, ev) in enumerate(zip(COLUMNS, EVENTS)):
        if ev is None:
            lis.append(f"""  <li class="is-empty">
    <i class="dot empty" aria-hidden="true">{i + 1}</i>
    <span class="label">{col}</span>
    <p>No stop. A copy fix has no QA gate.</p>
  </li>""")
        else:
            verb, rest, stamp = ev
            stamp_html = f' <span class="stamp">{stamp}</span>' if stamp else ""
            lis.append(f"""  <li>
    <i class="dot on" aria-hidden="true">{i + 1}</i>
    <span class="label">{col}</span>
    <p><b>{verb}</b>{rest}{stamp_html}</p>
  </li>""")
    states = ["empty" if ev is None else "on" for ev in EVENTS]
    return strip(states) + '\n<ol class="events">\n' + "\n".join(lis) + "\n</ol>"


# Elapsed minutes from the decision, for the one line that is drawn to scale (brief, 4.8).
TOTAL_MIN = VP10_MIN["deployed"]
# the column each event landed in, and its minute
MARKS = [(3, 0), (4, VP10_MIN["built"]), (6, VP10_MIN["reviewed"]), (7, VP10_MIN["merged"]), (8, VP10_MIN["deployed"])]


def hm(minutes, sep="&nbsp;"):
    """4 h 30 min, for the figure that stands beside the story."""
    h, m = divmod(minutes, 60)
    return f"{h}{sep}h {m}{sep}min" if m else f"{h}{sep}h"


def time_scale():
    """Plate 3, second row: the same item on one line drawn to scale, 4 hours 30 minutes long."""
    def at(minute):
        return f"{100 * minute / TOTAL_MIN:.2f}%"
    ticks = "".join(f'<i class="tick" style="--at:{at(60 * h)}"><span>{h}&nbsp;h</span></i>' for h in range(1, TOTAL_MIN // 60 + 1))
    marks = "".join(f'<i class="mark" style="--at:{at(m)}"><b>{n}</b></i>' for n, m in MARKS)
    return f"""<div class="tscale">
  <p class="label tscale__title"><span>The same item, to scale</span> <span>One line, {duration(TOTAL_MIN)} long</span></p>
  <div class="tscale__line" aria-hidden="true"><i class="tick" style="--at:0%"><span>0</span></i>{ticks}{marks}</div>
</div>"""


def section(sid, n, title, body):
    return f"""<section class="chapter" id="{sid}" aria-labelledby="{sid}-title">
  <header class="chapter__head">
    <p class="label">Method, {n} of 8</p>
    <h2 id="{sid}-title">{title}</h2>
  </header>
  <div class="chapter__body">
{ind(body, 4)}
  </div>
</section>"""


def method():
    seats = "\n".join(f"""  <div class="seat">
    <dt>{name}</dt>
    <dd><span class="label">Then</span> {then}</dd>
    <dd><span class="label">Now</span> {now}</dd>
  </div>""" for name, then, now in SEATS)
    parts = "\n".join(f"  <div><dt>{n}</dt><dd>{d}</dd></div>" for n, d in PARTS)
    steps = "\n".join(f"  <li><h3>{n}</h3><p>{d}</p></li>" for n, d in STEPS)
    rules = "\n".join(f"  <li>{r}</li>" for r in RULES)
    cards = []
    for iid, cls, project, title, mode, state, extra in ITEMS:
        extra_html = f' <span class="card__extra">{extra}</span>' if extra else ""
        cards.append(f"""  <li class="card c-{cls}" id="{iid.lower()}">
    <div class="card__head"><span class="label">{project}</span><b>{iid}</b></div>
    <p class="card__title">{title}{extra_html}</p>
    <dl class="card__meta"><div><dt>Mode</dt><dd>{mode}</dd></div><div><dt>State</dt><dd>{state}</dd></div></dl>
  </li>""")
    cards = "\n".join(cards)
    toc = [("approach", "A balanced approach"), ("parts", "The parts"), ("life", "The life of a work item"),
           ("loop", "The loop, in eight steps"), ("item", "One real item, start to finish"), ("conventions", "Conventions"),
           ("board", "On the board"), ("numbers", "The record so far")]
    toc_html = "\n".join(f'      <li><a href="#{a}"><span class="chip" aria-hidden="true">{i}</span><span>{t}</span></a></li>'
                         for i, (a, t) in enumerate(toc, 1))

    s_approach = section("approach", 1, "A balanced approach, ten years on", f"""<div class="thennow">
  <div>
    <p class="label">Then, 2016</p>
    <p>In 2016 I started an agency called Vordem. Its home page put our way of working under one heading, &ldquo;A balanced approach&rdquo;: strategists, developers, designers and product managers on the same problem, looking for a simple and elegant answer. We were ten people and shipped 10+ products.</p>
  </div>
  <div>
    <p class="label">Now, 2026</p>
    <p>The workshop I run today works the same way, with agents in most of the seats. One shapes an idea into a work item with me. One argues with the design before any code exists. One builds. A panel of reviewers checks correctness, security, QA and UX from the diff and the evidence, and never sees the plan. The decisions stay with me.</p>
  </div>
</div>
<h3 class="label sub">The seats, then and now</h3>
<dl class="seats">
{seats}
</dl>""")

    s_parts = section("parts", 2, "The parts", f"""<p>Smithy has four parts named after a forge, and two more I use every day.</p>
<dl class="parts">
{parts}
</dl>""")

    s_life = section("life", 3, "The life of a work item", f"""<figure class="plate plate--strip" aria-labelledby="plate-2-title">
  <div class="plate__head">
    <h3 class="label" id="plate-2-title">Plate 2&thinsp;&middot;&thinsp;The eight columns</h3>
    <p class="label">The form</p>
  </div>
{ind(strip_form(), 2)}
</figure>
<div class="trio">
  <p>A card moves only when something real happens: a claim, a gate verdict, a pull request marked ready, a merge, a deploy, an answer. There is no command to move a card.</p>
  <p>Needs input is a flag over any column. It is raised only for a blocker, a design decision, a destructive action or a question of intent.</p>
  <p>An item leaves grooming only when its definition is complete for its size: a problem, context and acceptance criteria, then a design, a test plan and risks for bigger items, plus a diagram and a design review for the biggest.</p>
</div>""")

    s_loop = section("loop", 4, "The loop, in eight steps", f"""<ol class="steps">
{steps}
</ol>
<div class="after">
  <p class="aside-line">Calls feed the record. After a call with my partner an agent writes the notes and files the action items.</p>
  <dl class="stamps">
    <div><dt>Gates</dt><dd><span class="stamp">ci</span> <span class="stamp">review</span> <span class="stamp">qa</span> <span class="stamp">design-review</span> <span class="stamp">deploy</span></dd></div>
    <div><dt>Verdicts</dt><dd><span class="stamp">pass</span> <span class="stamp">pass with notes</span> <span class="stamp">blocked</span> <span class="stamp">needs human</span> <span class="stamp">skipped</span> <span class="stamp">error</span></dd></div>
  </dl>
</div>""")

    s_item = section("item", 5, "One real item, start to finish", f"""<div class="spread">
  <p><b>VP-0010</b>, &ldquo;Copy fix: stop promising a daily set until one exists&rdquo;. The vim-puzzles dashboard still said &ldquo;Daily vim puzzles&rdquo; after the daily set was gone. An agent found the gap while grooming the app&rsquo;s backlog: the new About page would have repeated a promise the product no longer kept. It raised one question for me, with two options and a recommended answer. I had told the agents not to get blocked, so the recommended answer was taken and logged for me to read. {word(VP10_MIN["built"], True)} minutes later the fix was built and had passed CI. {word(VP10_MIN["reviewed"] - VP10_MIN["built"], True)} minutes after that it had passed review. It was deployed {"four and a half hours" if TOTAL_MIN == 270 else duration(TOTAL_MIN)} after the decision. The line it left on the dashboard is the app&rsquo;s line today: &ldquo;Vim puzzles, scored against par.&rdquo;</p>
  <p class="bigfact"><b>{hm(TOTAL_MIN)}</b> <span>from the decision to production</span></p>
</div>
<figure class="plate plate--strip plate--item" aria-labelledby="plate-3-title">
  <div class="plate__head">
    <h3 class="label" id="plate-3-title">Plate 3&thinsp;&middot;&thinsp;VP-0010</h3>
    <p class="label">Seven of eight</p>
  </div>
{ind(strip_item(), 2)}
{ind(time_scale(), 2)}
  <figcaption>
    <p>The card visits seven of the eight columns. It never stops in In QA: a copy fix has no QA gate.</p>
    <p>To scale, the line runs from the decision (3) to the deploy (8). The build (4) and the review (6) fall inside its first {VP10_MIN["reviewed"]} minutes. The merge (7) comes at {duration(VP10_MIN["merged"])}.</p>
    <p>Private record, simplified from the item&rsquo;s own log. Dates are UTC. Elapsed times count from the decision.</p>
  </figcaption>
</figure>""")

    s_conv = section("conventions", 6, "Conventions", f"""<p>Twelve rules from the ledger, shortened.</p>
<ol class="conventions">
{rules}
</ol>""")

    s_board = section("board", 7, "On the board", f"""<p>{word(len(ITEMS), True)} real work items that are safe to show, with mode and state.</p>
<ul class="board">
{cards}
</ul>""")

    SM, DX = P["smithy"], DATA["decisions_across_projects"]
    began = TREE["smithy"]["planted"]
    s_numbers = section("numbers", 8, "The record so far", f"""<p>Smithy began on <time datetime="{began}">{began}</time>. Private record, read {SM["read"]}.</p>
<ul class="counts">
  <li><b>{num(SM["projects_on_board"])}</b> <span>projects on one board</span></li>
  <li><b>{num(SM["work_items"])}</b> <span>work items, {num(SM["work_items_done"])} of them done</span></li>
  <li><b>{num(SM["gate_verdicts"])}</b> <span>gate verdicts</span></li>
  <li><b>{num(SM["decisions"])}</b> <span>decision records in Smithy&rsquo;s own ledger, more than {num(DX["more_than"])} across {word(DX["projects"])} of my projects</span></li>
  <li><b>{num(SM["reports"])}</b> <span>reports</span></li>
  <li><b>{num(SM["age_days"])}</b> <span>days old on the day it was read</span></li>
</ul>""")

    return f"""{head("How I build with agents &middot; Luis Herrada", "How Luis Herrada builds software with AI agents: Smithy, a board that moves only on facts, a ledger of decisions and one short list of what needs him.")}
<body class="page-method">
{masthead("method")}
<main id="main">
  <header class="chapter-head c-smithy">
    <div class="chapter-head__in">
      <p class="sheet__kicker"><span>The method chapter</span> <a href="index.html#smithy">Smithy&rsquo;s sheet</a></p>
      <h1>How I build with agents</h1>
      <dl class="chapter-head__pair">
        <div><dt>The complex challenge</dt><dd>AI agents can write code faster than one person can follow.</dd></div>
        <div><dt>The simple answer</dt><dd>Smithy is my answer: a personal system where agents do the building and I can still see the design, the decisions and the state of everything.</dd></div>
      </dl>
    </div>
  </header>

  <nav class="toc" aria-labelledby="toc-title">
    <h2 class="label" id="toc-title">In this chapter</h2>
    <ol>
{toc_html}
    </ol>
  </nav>

{ind(s_approach, 2)}

{ind(s_parts, 2)}

{ind(s_life, 2)}

{ind(s_loop, 2)}

{ind(s_item, 2)}

{ind(s_conv, 2)}

{ind(s_board, 2)}

{ind(s_numbers, 2)}

  <section class="close" aria-label="The close">
    <p>Smithy is its own first project: it was built with itself from the first day. This site is on the board too.</p>
    <p class="close__links"><a href="index.html#smithy">Back to Smithy&rsquo;s sheet</a> <a href="index.html#plate">See the plate</a></p>
  </section>
</main>
{footer("index.html")}
</body>
</html>
"""


# ---------------------------------------------------------------- the missing sheet
def missing():
    s = dict(
        id="missing", cls="slate", ref=None, kind="Not found", name="No sheet", r=4.1,
        line="This address has no sheet in the guide.",
        state_idx=-1, state_word=PEND, state="Nobody has written this page.",
        challenge="You asked for a page this guide does not have.",
        answer='Go back to <a href="/index.html">the cover</a> and pick a tree.',
        months=[], months_words="No months with work.",
        sources='<a class="src" href="/index.html">The guide</a>.',
    )
    body = sheet(s, level=1, folds=False).replace("<span>Not on the plate</span>", "<span>Error 404</span>")
    return f"""{head("No sheet at this address &middot; Luis Herrada", "This address has no sheet in the guide.", base="/")}
<body class="page-missing">
{masthead("none", base="/")}
<main id="main">
  <div class="missing">
{ind(body, 4)}
  </div>
</main>
{footer("/index.html")}
</body>
</html>
"""


ISO_DATE = re.compile(r"(?<![\w-])(\d{4}-\d{2}-\d{2})(?![\w-])")


def keep_dates_whole(text):
    """A date such as 2026-11-25 never breaks at a hyphen: every one that sits in running text
    is wrapped in a no-break span. Tags, attributes and comments are left alone."""
    parts = re.split(r"(<[^>]+>)", text)
    for i in range(0, len(parts), 2):
        parts[i] = ISO_DATE.sub(r'<span class="nb">\1</span>', parts[i])
    return "".join(parts)


def render():
    """The three pages, as they are written to disk."""
    out = {}
    for name, text in (("index.html", index()), ("how-i-build.html", method()), ("404.html", missing())):
        text = keep_dates_whole(text)
        out[name] = re.sub(r"[ \t]+\n", "\n", text)
    return out


def main(argv):
    pages = render()
    if argv[1:] == ["--check"]:
        stale = []
        for name, text in pages.items():
            try:
                with open(os.path.join(OUT, name), encoding="utf-8") as fh:
                    on_disk = fh.read()
            except FileNotFoundError:
                on_disk = None
            if on_disk != text:
                stale.append(name)
        if stale:
            print(f"build: {', '.join(stale)} differ from a rebuild of build/counts.json; run python3 build/build.py and commit")
            return 1
        print(f"build: {len(pages)} pages match a rebuild of build/counts.json (read {COUNTED})")
        return 0
    if argv[1:]:
        print("usage: python3 build/build.py [--check]")
        return 2
    for name, text in pages.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"{name}: {len(text.encode('utf-8')) / 1000:.1f} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
