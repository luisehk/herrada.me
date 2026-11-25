#!/usr/bin/env python3
"""Write herrada.me's three pages from src/site.json (HM-0002, direction E).

    python3 scripts/build.py            write index.html, how-i-build.html and 404.html
    python3 scripts/build.py --check    exit 1 when a committed page differs from what
                                        the data and the templates write (`make ci`)
    python3 scripts/build.py --out DIR  write the pages into DIR instead

Every word and number lives in src/site.json. The drawings live in src/art/ and the
page skeletons in src/templates/. The pages are committed, so the nginx image and
GitHub Pages serve them with no build step at run time. Standard library only.
"""

import argparse
import datetime
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ("index.html", "how-i-build.html", "404.html")

# Text values are HTML fragments. These are the only tags and attributes they may use.
ALLOWED_TAGS = {"a", "b", "code", "span", "time"}
ALLOWED_ATTRS = {"href", "lang", "class", "datetime", "aria-hidden"}
# A link goes to this site ("/", "#") or to another site over https, never to a script.
ALLOWED_HREF = ("/", "#", "https://")
WORDS = {7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen"}
PLACEHOLDER = re.compile(r"\{(n|over|read|date):([A-Za-z0-9_-]+)\}")
# Under a section opened from the menu: the Esc key for a keyboard, a link for a touch
# screen. style.css shows one of them, and script.js gives the link the same path as Esc.
SEC_ESC = ('      <p class="sec-esc"><span class="sec-esc-key">Esc goes back to the menu</span>'
           ' <a class="sec-back" href="#menu">back to the menu</a></p>')
# Ids land in id="...", class names and file names, and a block colour in a style attribute.
ID = re.compile(r"^[A-Za-z0-9-]+$")
BLOCK = re.compile(r"^#[0-9A-Fa-f]{6}$")


class FragmentError(ValueError):
    pass


class _Fragment(HTMLParser):
    """Checks one text value: allowed tags only, allowed attributes only, every tag closed.

    Comments, declarations, CDATA and processing instructions are refused, since they can
    hide a tag from this parser and not from a browser. `tags` counts what was parsed, so
    Site.text can refuse a '<' this parser read as plain text (an unfinished tag)."""

    def __init__(self, where):
        super().__init__(convert_charrefs=True)
        self.where = where
        self.stack = []
        self.tags = 0

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            raise FragmentError(f"{self.where}: tag <{tag}> is not allowed in a text value")
        for name, value in attrs:
            if name not in ALLOWED_ATTRS:
                raise FragmentError(f"{self.where}: attribute {name} on <{tag}> is not allowed in a text value")
            if name == "href":
                check_href(value, self.where)
        self.stack.append(tag)
        self.tags += 1

    def handle_startendtag(self, tag, attrs):
        raise FragmentError(f"{self.where}: <{tag}/> is not allowed in a text value; close the tag instead")

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise FragmentError(f"{self.where}: </{tag}> does not close the open tag")
        self.tags += 1

    def _refuse(self, what):
        raise FragmentError(f"{self.where}: {what} is not allowed in a text value")

    def handle_comment(self, data):
        self._refuse("a comment")

    def handle_decl(self, decl):
        self._refuse("a declaration")

    def unknown_decl(self, data):
        self._refuse("a CDATA section or declaration")

    def handle_pi(self, data):
        self._refuse("a processing instruction")

    def close(self):
        super().close()
        if self.stack:
            raise FragmentError(f"{self.where}: <{self.stack[-1]}> is never closed")


def esc(value):
    return html.escape(str(value), quote=True)


def check_href(value, where):
    """A link may leave only for this site or an https address (no javascript:, data: or //host)."""
    value = value or ""
    if not value.startswith(ALLOWED_HREF) or value.startswith("//"):
        raise FragmentError(f"{where}: href {value[:40]!r} must start with /, # or https://")
    return value


def time_tag(day):
    datetime.date.fromisoformat(day)  # a read date must be a real date
    return f'<time datetime="{day}">{day}</time>'


class Site:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.data = json.loads((self.root / "src" / "site.json").read_text(encoding="utf-8"))
        self.site = self.data["site"]
        self.counts = self.data["counts"]
        self.used = set()
        for key, count in self.counts.items():
            if not isinstance(count.get("value"), int) or isinstance(count.get("value"), bool):
                raise ValueError(f"counts.{key}: value must be a whole number")
            time_tag(count.get("read", ""))
            if not count.get("from"):
                raise ValueError(f"counts.{key}: say where the number was read from")
        self.check_ids()

    def check_ids(self):
        """Ids, colours and the year go into pages unchanged, so each must be plain."""
        home, board = self.data["home"], self.data["how_i_build"]["board"]
        ids = [(f"rows.{r['id']}", r["id"]) for r in self.data["rows"]]
        ids += [(f"home.projects.{p['id']}", p["id"]) for p in home["projects"]]
        ids += [(f"home.lines.{line['id']}", line["id"]) for line in home["lines"]]
        ids += [("how_i_build.board.held", i) for i in board["held"]]
        ids += [(f"how_i_build.board.placed.{col}", i) for col, items in board["placed"].items() for i in items]
        ids += [("how_i_build.board.on_the_way", i["id"]) for i in board["on_the_way"]]
        ids += [("how_i_build.board.done", i["id"]) for i in board["done"]]
        for where, value in ids:
            if not isinstance(value, str) or not ID.match(value):
                raise ValueError(f"{where}: id {str(value)[:40]!r} may use only letters, digits and '-'")
        for p in home["projects"]:
            if not isinstance(p.get("block"), str) or not BLOCK.match(p["block"]):
                raise ValueError(f"home.projects.{p['id']}.block: {str(p.get('block'))[:40]!r} is not a colour like #E65A5A")
        year = self.site.get("year")
        if not isinstance(year, int) or isinstance(year, bool):
            raise ValueError("site.year must be a whole number")
        hrefs = [(f"rows.{r['id']}.open", r["open"]) for r in self.data["rows"]]
        hrefs += [(f"home.projects.{p['id']}.link", p["link"]["href"]) for p in home["projects"]]
        hrefs += [("site.links", link["href"]) for link in self.site["links"]]
        for where, value in hrefs:
            check_href(value, where)

    # ---------- text ----------

    def text(self, value, where="text"):
        """Expands the placeholders in one text value and checks it as a fragment."""

        def expand(match):
            kind, key = match.groups()
            if kind == "date":
                return time_tag(key)
            if key not in self.counts:
                raise ValueError(f"{where}: no count named {key}")
            self.used.add(key)
            count = self.counts[key]
            if kind == "read":
                return time_tag(count["read"])
            if kind == "over":
                # the largest multiple of 50 below the count, so "more than" stays true
                if count["value"] <= 50:
                    raise ValueError(f"{where}: {{over:{key}}} needs a count above 50, not {count['value']}")
                return f"{(count['value'] - 1) // 50 * 50:,}"
            return f"{count['value']:,}"

        out = PLACEHOLDER.sub(expand, value)
        if re.search(r"\{[a-z]+:", out):
            raise ValueError(f"{where}: unknown placeholder in {value!r}")
        if "<!" in out or "<?" in out:
            raise FragmentError(f"{where}: a comment, declaration or processing instruction is not allowed in a text value")
        checker = _Fragment(where)
        checker.feed(out)
        checker.close()
        if out.count("<") != checker.tags:
            raise FragmentError(f"{where}: a '<' that opens no allowed tag; write &lt; for a literal one")
        return out

    def art(self, name):
        return (self.root / "src" / "art" / name).read_text(encoding="utf-8").rstrip("\n")

    def template(self, page_name, /, **slots):
        name = page_name
        page = (self.root / "src" / "templates" / name).read_text(encoding="utf-8")

        def fill(match):
            key = match.group(1)
            if key not in slots:
                raise ValueError(f"src/templates/{name}: no value for {{{{{key}}}}}")
            return slots.pop(key)

        page = re.sub(r"\{\{([a-z_]+)\}\}", fill, page)
        if slots:
            raise ValueError(f"src/templates/{name}: unused slots {sorted(slots)}")
        return page

    # ---------- parts every page shares ----------

    @property
    def bumpy(self):
        return bool(self.site["bumpy"])

    def head(self, title, description, body_class, noindex=False, home=False):
        icon = self.art("favicon-bumpy.txt") if self.bumpy else self.art("favicon-block.txt")
        lines = [
            "<!doctype html>",
            f'<html lang="en"{"" if self.bumpy else " class=" + chr(34) + "no-bumpy" + chr(34)}>',
            "<!-- Written by scripts/build.py from src/site.json. Edit those and run it, not this file. -->",
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{esc(title)}</title>",
            f'<meta name="description" content="{esc(description)}">',
        ]
        if noindex or self.site["preview"]:
            lines.append('<meta name="robots" content="noindex">')
        lines += [
            '<meta name="color-scheme" content="dark light">',
            '<meta name="theme-color" content="#181A2E" media="(prefers-color-scheme: dark)">',
            '<meta name="theme-color" content="#F0C85A" media="(prefers-color-scheme: light)">',
            f'<link rel="icon" href="data:image/svg+xml,{icon}">',
            '<link rel="preload" href="/fonts/bricolage-grotesque-latin.woff2" as="font" type="font/woff2" crossorigin>',
            '<link rel="stylesheet" href="/style.css">',
            '<script src="/script.js" defer></script>',
        ]
        if home and self.bumpy:
            lines.append("<noscript><style>.bumpy{visibility:visible}</style></noscript>")
        lines += ["</head>", f'<body class="{body_class}">']
        return "\n".join(lines)

    def top(self, current):
        menu_href = "#menu" if current == "home" else "/"
        record_href = "#record" if current == "home" else "/#record"

        def item(href, label, here):
            mark = ' aria-current="page"' if here else ""
            return f'      <li><a href="{href}"{mark}>{label}</a></li>'

        return "\n".join([
            '<header class="top wrap">',
            '  <a class="top-site" href="/">herrada.me</a>',
            '  <nav aria-label="Site">',
            "    <ul>",
            item(menu_href, "Menu", current == "home"),
            item("/how-i-build.html", "How I build", current == "how"),
            item(record_href, "Record", False),
            "    </ul>",
            "  </nav>",
            "</header>",
        ])

    def foot(self, back_href):
        links = ' <span aria-hidden="true">&middot;</span> '.join(
            f'<a href="{esc(link["href"])}">{esc(link["label"])}</a>' for link in self.site["links"]
        )
        colophon = self.site["colophon_preview"] if self.site["preview"] else self.site["colophon"]
        return "\n".join([
            '<footer class="foot wrap">',
            f'  <p class="foot-line"><span class="foot-c">&copy; {self.site["year"]} {esc(self.site["name"])}</span>'
            f' <span class="foot-links">{links} <span aria-hidden="true">&middot;</span>'
            f' <a href="{back_href}">back to the menu</a></span></p>',
            f'  <p class="foot-note">{self.text(colophon, "site.colophon")}</p>',
            "</footer>",
        ])

    # ---------- the home page ----------

    def rows_html(self):
        out = []
        for i, row in enumerate(self.data["rows"]):
            rid = row["id"]
            checked = " checked" if i == 0 else ""
            still = " data-still" if row["motion"] == "still" else ""
            label = esc(row["label"])
            label_class = "row-label"
            if row.get("note"):
                label_class += " row-label-two"
                label += f' <span class="row-note">{esc(row["note"])}</span>'
            acts = []
            if row["motion"] == "game":
                acts.append('<button class="row-go row-play" type="button" data-play hidden>'
                            '<span data-play-word>play</span><span class="vh"> catch</span></button>')
            acts.append(f'<a class="row-go" href="{esc(row["open"])}">open<span class="vh"> {esc(row["open_name"])}</span></a>')
            out += [
                '      <div class="row">',
                f'        <input class="row-radio" type="radio" name="row" id="s-{rid}" value="{rid}"'
                f' aria-describedby="fact-{rid} hook-{rid}"{still}{checked}>',
                f'        <label class="{label_class}" for="s-{rid}">{label}</label>',
                f'        <span class="row-acts">{"".join(acts)}</span>',
                "      </div>",
            ]
        if self.bumpy:
            out += [
                "",
                "      <!-- Bumpy, the cursor. 16 by 11 pixels, drawn three to one. Four poses on one canvas. -->",
                '      <span class="bumpy" data-bumpy data-pose="base" aria-hidden="true">',
                self.art("bumpy.svg"),
                "      </span>",
            ]
        return "\n".join(out)

    def panes_html(self):
        out = []
        for row in self.data["rows"]:
            rid = row["id"]
            where = f"rows.{rid}"
            game = row["motion"] == "game"
            desc = " data-game-desc" if game else ""
            art = "\n".join("          " + line if line else line for line in self.art(f"pane-{rid}.html").split("\n"))
            out += [
                f'      <figure class="pv pv-{rid}">',
                f'        <figcaption class="fact" id="fact-{rid}"><span{desc}>{self.text(row["fact"], where + ".fact")}</span></figcaption>',
                f'        <div class="screen"{" data-game" if game else ""}>',
                f'          <span class="screen-title" aria-hidden="true">{esc(row["label"])}</span>',
                art,
                "        </div>",
                f'        <p class="hook" id="hook-{rid}">{self.text(row["hook"], where + ".hook")}</p>',
            ]
            if row.get("alt"):
                out.append(f'        <p class="vh" data-alt>{esc(row["alt"])}</p>')
            out += ["      </figure>", ""]
        controls = []
        if self.bumpy:
            controls.append('        <button class="pane-btn" type="button" data-bumpy-toggle hidden>Hide Bumpy</button>')
        controls.append('        <button class="pane-btn pane-pause" type="button" data-pause hidden>'
                        '<span data-pause-word>pause</span><span class="vh"> the pane</span></button>')
        out += ['      <div class="pane-ctl">', *controls, "      </div>"]
        return "\n".join(out)

    def section_head(self, tag, sid, name, kind, esc_line=False, extra=""):
        lines = ['    <div class="sec-head">', f'      <{tag} class="sec-name" id="h-{sid}">{name}</{tag}>']
        if kind:
            lines.append(f'      <p class="sec-kind">{kind}</p>')
        if esc_line:
            lines.append(SEC_ESC)
        if extra:
            lines.append(extra)
        lines.append("    </div>")
        return lines

    def projects_html(self):
        out = []
        for p in self.data["home"]["projects"]:
            pid = p["id"]
            w = f"home.projects.{pid}"
            stat = "\n".join([
                '      <dl class="stat">',
                f'        <div><dt>state</dt><dd>{self.text(p["state"], w + ".state")}</dd></div>',
                f'        <div><dt>score</dt><dd>{self.text(p["score"], w + ".score")}</dd></div>',
                "      </dl>",
            ])
            out.append(f'  <section class="sec sec-project" id="{esc(pid)}" tabindex="-1" style="--block:{esc(p["block"])}">')
            out += self.section_head("h3", pid, esc(p["name"]), self.text(p["kind"], w + ".kind"), True, stat)
            body = [
                '    <div class="sec-body">',
                f'      <p class="lead">{self.text(p["lead"], w + ".lead")}</p>',
                '      <dl class="pair">',
                f'        <div><dt>the complex challenge</dt><dd>{self.text(p["challenge"], w + ".challenge")}</dd></div>',
                f'        <div><dt>the simple answer</dt><dd>{self.text(p["answer"], w + ".answer")}</dd></div>',
                "      </dl>",
            ]
            body += [f"      <p>{self.text(para, w + '.body')}</p>" for para in p["body"]]
            if p.get("frames"):
                body.append('      <ul class="frames">')
                body += [
                    f'        <li><img src="{esc(f["src"])}" width="360" height="270" alt="{esc(f["alt"])}" loading="lazy" decoding="async"></li>'
                    for f in p["frames"]
                ]
                body += ["      </ul>", f'      <p class="cap">{self.text(p["frames_caption"], w + ".frames_caption")}</p>']
            link = p["link"]
            note = f' <span class="btn-note">{esc(link["note"])}</span>' if link.get("note") else ""
            select = f' data-select="{esc(link["select"])}"' if link.get("select") else ""
            body += [
                f'      <p class="go"><a class="btn" href="{esc(link["href"])}"{select}>{esc(link["label"])}{note}</a></p>',
                "    </div>",
                "  </section>",
                "",
            ]
            out += body
        return "\n".join(out).rstrip("\n")

    def lines_html(self):
        out = []
        for line in self.data["home"]["lines"]:
            lid = line["id"]
            opened = line.get("open", False)
            tab = ' tabindex="-1"' if opened else ""
            out.append(f'  <section class="sec sec-line" id="{esc(lid)}"{tab}>')
            out += self.section_head("h3", lid, esc(line["name"]), self.text(line["kind"], f"home.lines.{lid}.kind"), opened)
            out += [
                '    <div class="sec-body">',
                f'      <p>{self.text(line["text"], f"home.lines.{lid}.text")}</p>',
                "    </div>",
                "  </section>",
                "",
            ]
        return "\n".join(out).rstrip("\n")

    def rows_dl(self, rows, where, cls="years rows"):
        out = [f'    <dl class="{cls}">']
        out += [
            f'      <div><dt>{self.text(r["term"], where)}</dt><dd>{self.text(r["text"], where)}</dd></div>' for r in rows
        ]
        out.append("    </dl>")
        return "\n".join(out)

    def index(self):
        s, home = self.site, self.data["home"]
        work, beyond, record = home["how_i_work"], home["beyond"], home["record"]
        about_face = ('      <img class="face" src="/assets/avatar-128.webp" srcset="/assets/avatar-128.webp 2x, '
                      '/assets/avatar-192.webp 3x" width="64" height="64" alt="Illustrated portrait of Luis Herrada" '
                      'loading="lazy" decoding="async">')
        return self.template(
            "index.html",
            head=self.head(s["title"], s["description"], "home", home=True),
            top=self.top("home"),
            name=esc(s["name"]),
            label=esc(s["label"]),
            city=esc(s["city"]),
            since=esc(s["since"]),
            lede=self.text(s["lede"], "site.lede"),
            rows=self.rows_html(),
            panes=self.panes_html(),
            hero=self.text(home["hero"], "home.hero"),
            creed=self.text(home["creed"], "home.creed"),
            about=self.text(home["about"]["body"], "home.about.body"),
            about_kind=self.text(home["about"]["kind"], "home.about.kind"),
            about_face=about_face,
            now_kind=self.text(home["now"]["kind"], "home.now.kind"),
            now=self.text(home["now"]["lead"], "home.now.lead"),
            projects=self.projects_html(),
            lines=self.lines_html(),
            work_kind=self.text(work["kind"], "home.how_i_work.kind"),
            work_body="\n".join(f"      <p>{self.text(p, 'home.how_i_work.body')}</p>" for p in work["body"]),
            work_rules="\n".join(f"        <li>{self.text(r, 'home.how_i_work.rules')}</li>" for r in work["rules"]),
            beyond_kind=self.text(beyond["kind"], "home.beyond.kind"),
            beyond_body=self.text(beyond["body"], "home.beyond.body"),
            beyond_rows=self.rows_dl(beyond["rows"], "home.beyond.rows"),
            motto=self.text(beyond["motto"], "home.beyond.motto"),
            record_kind=self.text(record["kind"], "home.record.kind"),
            record_years=self.rows_dl(record["years"], "home.record.years"),
            record_after=self.text(record["after"], "home.record.after"),
            foot=self.foot("#menu"),
        )

    # ---------- How I build with agents ----------

    def board_html(self):
        b = self.data["how_i_build"]["board"]
        out = []

        def col(name, step, items, held=False):
            cls = "map-col map-held" if held else "map-col"
            lines = [f'          <li class="{cls}" style="--s:{step}">']
            if items:
                chip = "chip chip-held" if held else ("chip chip-dev" if name == "In dev" else "chip")
                inner = "".join(f'<li class="{chip}">{esc(i)}</li>' for i in items)
                if len(items) > 3:
                    lines += ['            <ul class="map-items">', f"              {inner}", "            </ul>"]
                else:
                    lines.append(f'            <ul class="map-items">{inner}</ul>')
            else:
                lines.append('            <span class="vh">No item shown.</span>')
            lines += [
                '            <span class="map-step" aria-hidden="true"></span>',
                f'            <span class="map-name">{esc(name)}</span>',
                "          </li>",
            ]
            return lines

        out += col("Held", 0, b["held"], held=True)
        for step, name in enumerate(b["columns"]):
            out += col(name, step, b["placed"].get(name, []))
        return "\n".join(out)

    def levels_html(self):
        out = []
        for n, level in enumerate(self.data["how_i_build"]["levels"], start=1):
            w = f"how_i_build.levels.{n}"
            svg = "\n".join("          " + line for line in self.art(f"level-{n}.svg").split("\n"))
            out += [
                '  <div class="level">',
                '    <figure class="lv-fig">',
                '      <div class="screen">',
                f'        <span class="screen-title" aria-hidden="true">level {n}</span>',
                f'        <svg viewBox="0 0 400 300" role="img" aria-label="{esc(level["alt"])}">',
                svg,
                "        </svg>",
                "      </div>",
                "    </figure>",
                f'    <h3 class="lv-name" id="lv-{n}">{self.text(level["name"], w)}</h3>',
                f'    <p class="lv-text">{self.text(level["text"], w)}</p>',
            ]
            if level.get("note"):
                out.append(f'    <p class="lv-note">{self.text(level["note"], w)}</p>')
            out += ["  </div>", ""]
        return "\n".join(out).rstrip("\n")

    def splits_html(self):
        story = self.data["how_i_build"]["story"]
        total = story["splits"][-1]["minutes"]
        out = []
        for split in story["splits"]:
            m = split["minutes"]
            hours, mins = divmod(m, 60)
            spoken = f"{mins} minutes" if not hours else f"{hours} hour{'s' if hours > 1 else ''} {mins} minutes"
            share = f"{m / total * 100:.1f}".removesuffix(".0")
            out += [
                f'          <li style="--t:{share}%">',
                f'            <span class="split-name">{esc(split["name"])}</span>',
                f'            <span class="split-time"><span aria-hidden="true">{hours}:{mins:02d}</span><span class="vh">{spoken}</span></span>',
                '            <span class="split-bar" aria-hidden="true"></span>',
                f'            <span class="split-note">{self.text(split["note"], "how_i_build.story.splits")}</span>',
                "          </li>",
            ]
        return "\n".join(out)

    def how(self):
        h = self.data["how_i_build"]
        b, story, rules, score = h["board"], h["story"], h["rules"]["items"], h["score"]
        w = "how_i_build"
        sub = ' <span class="sep" aria-hidden="true">&middot;</span> '.join(
            f'<span class="nb">{self.text(part, w + ".sub")}</span>' for part in h["sub"]
        )
        seats = []
        for seat in h["seats"]:
            seats += [
                "      <div>",
                f"        <dt>{esc(seat['seat'])}</dt>",
                f'        <dd class="then"><span class="tag">then</span> {self.text(seat["then"], w + ".seats")}</dd>',
                f'        <dd class="now"><span class="tag tag-now">now</span> {self.text(seat["now"], w + ".seats")}</dd>',
                "      </div>",
            ]
        on_way = "\n".join(
            f'        <li><b>{esc(i["id"])}</b><span>{self.text(i["title"], w + ".board")}</span><i>{self.text(i["state"], w + ".board")}</i></li>'
            for i in b["on_the_way"]
        )
        done = "\n".join(
            f'        <li><b>{esc(i["id"])}</b><span>{self.text(i["title"], w + ".board")}</span></li>' for i in b["done"]
        )
        score_rows = [f'      <div><dt>{time_tag(score["began"])}</dt><dd>Smithy began.</dd></div>']
        score_rows += [
            f'      <div><dt>{self.text(r["n"], w + ".score")}</dt><dd>{self.text(r["text"], w + ".score")}</dd></div>'
            for r in score["rows"]
        ]
        return self.template(
            "how-i-build.html",
            head=self.head(f"{h['title']} · {self.site['name']}", h["description"], "inner"),
            top=self.top("how"),
            kicker=esc(h["kicker"]),
            title=esc(h["title"]),
            sub=sub,
            idea_kind=self.text(h["idea"]["kind"], w + ".idea"),
            idea=self.text(h["idea"]["lead"], w + ".idea"),
            balanced_kind=self.text(h["balanced"]["kind"], w + ".balanced"),
            balanced="\n".join(f"      <p>{self.text(p, w + '.balanced')}</p>" for p in h["balanced"]["body"]),
            seats="\n".join(seats),
            parts_kind=self.text(h["parts"]["kind"], w + ".parts"),
            parts_intro=self.text(h["parts"]["intro"], w + ".parts"),
            parts=self.rows_dl(h["parts"]["rows"], w + ".parts", "parts rows"),
            board_kind=self.text(b["kind"], w + ".board"),
            columns="".join(f"<li>{esc(c)}</li>" for c in b["columns"]),
            board_body="\n".join(f"      <p>{self.text(p, w + '.board')}</p>" for p in b["body"]),
            board_caption=self.text(b["caption"], w + ".board"),
            board=self.board_html(),
            on_the_way=on_way,
            done_note=self.text(b["done_note"], w + ".board"),
            done=done,
            loop_kind=self.text(h["loop"]["kind"], w + ".loop"),
            loop_intro=self.text(h["loop"]["intro"], w + ".loop"),
            levels=self.levels_html(),
            after=self.text(h["after"], w + ".after"),
            story_kind=self.text(story["kind"], w + ".story"),
            story="\n".join(f"      <p>{self.text(p, w + '.story')}</p>" for p in story["paragraphs"]),
            story_item=esc(story["item"]),
            story_before="\n".join(f"          <li>{self.text(p, w + '.story.before')}</li>" for p in story["before"]),
            splits_start=str(len(story["before"]) + 1),
            splits=self.splits_html(),
            story_close=self.text(story["close"], w + ".story"),
            rules_kind=self.text(h["rules"]["kind"], w + ".rules"),
            rules_first="\n".join(f"        <li>{self.text(r, w + '.rules')}</li>" for r in rules[:4]),
            rules_more_start="5",
            rules_more="\n".join(f"        <li>{self.text(r, w + '.rules')}</li>" for r in rules[4:]),
            score_kind=self.text(score["kind"], w + ".score"),
            score="\n".join(score_rows),
            began=time_tag(score["began"]),
            close=self.text(h["close"]["lead"], w + ".close"),
            foot=self.foot("/"),
        )

    # ---------- the 404 ----------

    def not_found(self):
        nf = self.data["not_found"]
        rows = len(self.data["rows"])
        lead = nf["lead"].replace("{rows}", WORDS.get(rows, str(rows)))
        if self.bumpy:
            cursor = "\n".join([
                '        <span class="bumpy" data-pose="sleep" aria-hidden="true">',
                self.art("bumpy-sleep.svg"),
                "        </span>",
            ])
            line = nf["bumpy_line"]
        else:
            cursor = '        <span class="row-missing-block" aria-hidden="true"></span>'
            line = nf["plain_line"]
        return self.template(
            "404.html",
            head=self.head(f"{nf['title']} · {self.site['name']}", nf["description"], "inner lost", noindex=True),
            top=self.top("lost"),
            title=esc(nf["title"]),
            sub=self.text(nf["sub"], "not_found.sub"),
            cursor=cursor,
            label=esc(nf["label"]),
            lead=self.text(lead, "not_found.lead"),
            line=self.text(line, "not_found.line"),
            foot=self.foot("/"),
        )

    def pages(self):
        pages = {"index.html": self.index(), "how-i-build.html": self.how(), "404.html": self.not_found()}
        unused = sorted(set(self.counts) - self.used)
        if unused:
            raise ValueError(f"counts never shown on a page: {', '.join(unused)}")
        return pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail when a committed page is out of date")
    parser.add_argument("--out", type=Path, help="write the pages here instead of the repo root")
    args = parser.parse_args(argv)
    try:
        pages = Site().pages()
    except (ValueError, KeyError, OSError) as err:
        print(f"build: {err}", file=sys.stderr)
        return 1
    if args.check:
        stale = [name for name, body in pages.items()
                 if not (ROOT / name).exists() or (ROOT / name).read_text(encoding="utf-8") != body]
        for name in stale:
            print(f"FAILED  {name} is not what src/site.json writes; run python3 scripts/build.py and commit it")
        if not stale:
            print(f"ok      {', '.join(pages)} match src/site.json")
        return 1 if stale else 0
    out = args.out or ROOT
    out.mkdir(parents=True, exist_ok=True)
    for name, body in pages.items():
        (out / name).write_text(body, encoding="utf-8")
        print(f"wrote {out / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
