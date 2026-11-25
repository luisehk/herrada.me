"""Site tests for `make ci` (HM-0002). Python's standard library only.

    python3 -B -m unittest discover -s build -p 'test_*.py'

They read the committed files: the three pages, style.css, script.js, fonts/, assets/ and
build/counts.json. Nothing here starts a server: scripts/smoke.sh checks what nginx serves.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit

import build

ROOT = build.OUT
PAGES = build.PAGES
ROBOTS = '<meta name="robots" content="noindex">'

# Hosts a page may link to (never load from). Under herrada.me only the site itself,
# vim.herrada.me and budgeter.herrada.me may be named (the brief's content rules).
LINK_HOSTS = {"github.com", "www.linkedin.com", "rentaventa.mx", "arbopedia.mx", "vim.herrada.me", "budgeter.herrada.me"}
NAMED_HOSTS = {"herrada.me", "vim.herrada.me", "budgeter.herrada.me"}
# The excluded employer's name never appears. Only its SHA-256 is kept here, so this file
# does not name it either: every word of every page and of the build is hashed and compared.
EXCLUDED = {"68416e05c11caecd29ca6ed1d7cf2647568eb85df313c3eaea173da806d7fd09"}


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


class Page(HTMLParser):
    """The parts of a page the tests look at."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.loads, self.text = set(), [], [], []
        self.stack, self.tags = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a, list(self.stack)))
        if tag not in ("meta", "link", "img", "br", "input", "source"):
            self.stack.append((tag, a.get("class", ""), a.get("id", "")))
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.links.append(a["href"])
        if tag in ("script", "img", "source") and "src" in a:
            self.loads.append(a["src"])
        if tag == "link" and "href" in a:
            self.loads.append(a["href"])

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.text.append(data)


PARSED = {name: Page(read(name)) for name in PAGES}


def local_path(page, url):
    """The repo file a local URL names, from the page that holds it."""
    path = urlsplit(url).path
    if path in ("", "/"):
        return "index.html"
    if path.startswith("/"):
        return path.lstrip("/")
    return os.path.normpath(os.path.join(os.path.dirname(page), path))


class TestPages(unittest.TestCase):
    def test_pages_match_a_rebuild_of_the_data_file(self):
        rendered = build.render()
        for name in PAGES:
            self.assertTrue(read(name) == rendered[name], f"{name} differs from a rebuild: python3 build/build.py")

    def test_every_page_says_preview_and_is_never_indexed(self):
        for name in PAGES:
            text = read(name)
            self.assertEqual(text.count(ROBOTS), 1, name)
            self.assertTrue("<span>Preview.</span>" in text, name)
            self.assertTrue("<p>Preview. Drawn by AI agents" in text, name)
            # HM-0001's own card may call its five designs prototypes; the site never calls itself one.
            for gone in ("Prototype.", "Direction D of five", "direction D of five", "?grow"):
                self.assertFalse(gone in text, f"{name} still says {gone!r}")

    def test_nothing_loads_from_another_host(self):
        for name in PAGES:
            for url in PARSED[name].loads:
                parts = urlsplit(url)
                if parts.scheme == "data":      # the favicon is inline: no request
                    continue
                self.assertFalse(parts.scheme or parts.netloc, f"{name} loads {url[:80]}")
                self.assertTrue(os.path.isfile(os.path.join(ROOT, local_path(name, url))), f"{name} loads {url}, not in the repo")
        css = read("style.css")
        urls = re.findall(r'url\(\s*["\']?([^"\')]+)', css)
        self.assertEqual(sorted(urls), sorted(build.FONT_FILES), "style.css loads only the two font files")
        for url in urls:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, url)), url)
        self.assertNotIn("@import", css)
        for name in PAGES + ("style.css", "script.js"):
            for host in ("gstatic", "googleapis", "fonts.google"):
                self.assertFalse(host in read(name), f"{name} names {host}")

    def test_the_missing_sheet_links_root_relative(self):
        """nginx serves 404.html at any depth, so its own files and links start at /."""
        p = PARSED["404.html"]
        for url in p.loads + p.links:
            if not urlsplit(url).scheme and not url.startswith("#"):
                self.assertTrue(url.startswith("/"), f"404.html links {url} relative")

    def test_links_resolve(self):
        for name in PAGES:
            for url in PARSED[name].links:
                parts = urlsplit(url)
                if parts.scheme:
                    self.assertEqual(parts.scheme, "https", url)
                    self.assertIn(parts.netloc, LINK_HOSTS, f"{name} links {url}")
                    continue
                target = name if not parts.path else local_path(name, url)
                self.assertIn(target, PAGES, f"{name} links {url}")
                if parts.fragment:
                    self.assertIn(parts.fragment, PARSED[target].ids, f"{name} links {url}: no such anchor")

    def test_content_rules(self):
        files = list(PAGES) + ["style.css", "script.js", "build/build.py", "build/plate.py", "build/counts.json"]
        for name in files:
            text = read(name)
            words = re.findall(r"[a-z0-9]+", text.lower())
            for w in set(words):
                self.assertNotIn(hashlib.sha256(w.encode()).hexdigest(), EXCLUDED, f"{name} names the excluded employer")
            for host in set(re.findall(r"\b((?:[a-z0-9-]+\.)+herrada\.me)\b", text.lower())):
                self.assertIn(host, NAMED_HOSTS, f"{name} names {host}")
            self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)*\.[a-z]{2,}\b", text, re.I), f"{name} holds an email address")
        for name in PAGES:
            text = " | ".join(PARSED[name].text)      # a run never spans two elements
            # a phone number: ten digits or more, in groups or not (a date has eight)
            for run in re.findall(r"(?<![\d,])\+?\d[\d ()-]{8,}\d(?![\d,])", text):
                self.assertLess(len(re.sub(r"\D", "", run)), 10, f"{name} holds a phone number")

    def test_every_count_in_the_data_file_is_on_a_page(self):
        pages = read("index.html") + read("how-i-build.html")
        for key, project in build.P.items():
            for field, value in project.items():
                if isinstance(value, int) and field != "decisions" or field == "decisions" and value:
                    self.assertTrue(build.num(value) in pages, f"{key}.{field} = {value} is not on a page")
        for tree in build.DATA["plate"]:
            self.assertTrue(f'<td class="num">{tree["months"]}</td>' in read("index.html"), tree["name"])

    def test_sheets_stand_in_the_brief_order(self):
        order = [i for i in re.findall(r'<article class="sheet[^"]*" id="([^"]+)"', read("index.html"))]
        self.assertEqual(order, ["smithy", "rentaventa", "arbopedia", "vim-puzzles", "lichess-irl", "minigames",
                                 "budgeter", "rentaventa-meet", "the-desk", "crispy-wookie", "author"])

    def test_a_phone_folds_the_front_and_the_sheets(self):
        """HM-0002 D: the key and the legend fold, each main sheet folds its months and sources
        (and keeps its field notes closed), and a short sheet is its name and its line."""
        tags = PARSED["index.html"].tags

        def folds_in(sheet_id, cls):
            return [t for t in tags if t[0] == "details" and cls in t[1].get("class", "").split()
                    and any(s[2] == sheet_id for s in t[2])]

        top = [t[1] for t in tags if t[0] == "details" and not any(s[0] == "article" for s in t[2])]
        self.assertIn({"class": "fold keywrap", "id": "key"}, top)
        self.assertIn({"class": "fold howto"}, top)
        for s in build.SHEETS:
            self.assertEqual(len(folds_in(s["id"], "fold")), 1, s["id"])
            self.assertEqual(len(folds_in(s["id"], "notes")), 1, s["id"])
        for s in build.SHORTS:
            self.assertEqual(len(folds_in(s["id"], "fold--sheet")), 1, s["id"])
        self.assertEqual(len(folds_in("author", "fold--prose")), 3)
        for t in tags:
            if t[0] == "details":
                self.assertNotIn("open", t[1], "a fold is closed in the page; a desk opens it in CSS")
        self.assertTrue("@supports selector(::details-content)" in read("style.css"))

    def test_preview_answers_to_the_open_questions(self):
        index = read("index.html")
        for want in ('href="https://budgeter.herrada.me"', "software engineer in Monterrey",
                     'src="assets/avatar.webp"', "Shine On You Crazy Diamond"):
            self.assertTrue(want in index, want)
        self.assertTrue("VP-0010" in read("how-i-build.html"))


class TestFonts(unittest.TestCase):
    def test_fonts_are_woff2_with_their_licences(self):
        fonts = sorted(f for f in os.listdir(os.path.join(ROOT, "fonts")) if f.endswith(".woff2"))
        self.assertEqual(["fonts/" + f for f in fonts], sorted(build.FONT_FILES))
        for f in fonts:
            with open(os.path.join(ROOT, "fonts", f), "rb") as fh:
                self.assertEqual(fh.read(4), b"wOF2", f)
        for family in ("Fraunces", "InstrumentSans"):
            text = read(f"fonts/OFL-{family}.txt")
            self.assertIn("SIL OPEN FONT LICENSE Version 1.1", text)
            self.assertIn("Copyright", text)


class TestBuildRules(unittest.TestCase):
    def test_months_as_words(self):
        self.assertEqual(build.months_words([10, 11]), "October and November")
        self.assertEqual(build.months_words([1, 2, 3, 4, 6, 10]), "January to April, June and October")
        self.assertEqual(build.months_words([8]), "August")
        self.assertEqual(build.months_words(list(range(1, 12))), "January to November")

    def test_durations(self):
        self.assertEqual(build.duration(13), "13 minutes")
        self.assertEqual(build.duration(159), "2 hours 39 minutes")
        self.assertEqual(build.duration(270), "4 hours 30 minutes")
        self.assertEqual(build.hm(270), "4&nbsp;h 30&nbsp;min")

    def test_a_tree_is_as_tall_as_its_months(self):
        import plate
        for months in (3, 4, 6, 7, 9, 10, 26, 27, 28, 40):
            shapes = "".join(plate.tree_shapes(months))
            tops = [float(cy) - float(ry) for cy, ry in re.findall(r'cy="(-?[\d.]+)" rx="[\d.]+" ry="([\d.]+)"', shapes)]
            self.assertAlmostEqual(-min(tops), months * plate.U, delta=0.6, msg=months)


def rebuild_with(change):
    """Copies the build and the pages to a temporary repo, changes counts.json there and runs
    the build. Returns the process and the new home page."""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(ROOT, "build"), os.path.join(tmp, "build"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        path = os.path.join(tmp, "build", "counts.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        change(data)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        run = subprocess.run([sys.executable, "-B", os.path.join(tmp, "build", "build.py")],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        index = ""
        if os.path.isfile(os.path.join(tmp, "index.html")):
            with open(os.path.join(tmp, "index.html"), encoding="utf-8") as fh:
                index = fh.read()
        return run, index
    finally:
        shutil.rmtree(tmp)


class TestKeepingItTrue(unittest.TestCase):
    def test_a_new_month_redraws_the_stand(self):
        def grow(data):
            data["plate"][1]["months"] = 31
            data["projects"]["smithy"]["work_items"] = 700
        run, index = rebuild_with(grow)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        for want in ('<td class="num">31</td>', "31 months with work in all", "<b>700</b>"):
            self.assertTrue(want in index, want)

    def test_a_root_the_drawing_does_not_hold_stops_the_build(self):
        def flip(data):
            data["plate"][6]["board"] = "yes"
        run, _ = rebuild_with(flip)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("redraw roots()", run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
