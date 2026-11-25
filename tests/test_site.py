"""Checks on the built site for `make ci` (HM-0002, direction E). Standard library only.

    python3 -B -m unittest discover -s tests -p 'test_*.py'

T-HM-2-1  the pages are what src/site.json writes, and every count has a read date
T-HM-2-2  the content rules: no excluded employer, no email, no phone number, no
          internal hostname, links only to the brief's public list
T-HM-2-3  no request to another host: fonts, styles, scripts and images are the site's own
T-HM-2-4  a preview is never indexed and says "Preview"
T-HM-2-5  every internal link and fragment resolves
T-HM-2-6  the first screen informs before it plays: the lede, and each fact above its loop
T-HM-2-7  Bumpy is one switch in the data file
T-HM-2-8  the font is self-hosted under the OFL
T-HM-2-9  the stylesheet knows every row
"""

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402

PAGES = build.PAGES
# The brief's public links (HM-0001 brief 4.7), and budgeter (open question 7, recommended yes).
ALLOWED_LINKS = {
    "https://github.com/luisehk",
    "https://www.linkedin.com/in/luisehk",
    "https://rentaventa.mx",
    "https://arbopedia.mx",
    "https://www.instagram.com/arbopedia",
    "https://vim.herrada.me",
    "https://budgeter.herrada.me",
    "https://github.com/luisehk/flutter-chessground/tree/add-cubesandpi-3d-piece-set",
    "https://github.com/luisehk/crispy-wookie",
}
ALLOWED_SUBDOMAINS = {"vim.herrada.me", "budgeter.herrada.me"}
# Words that must never appear in this public repo, stored as hashes so the check does
# not print them itself: the employer the house rules exclude.
BANNED_WORD_HASHES = {"68416e05c11caecd29ca6ed1d7cf2647568eb85df313c3eaea173da806d7fd09"}


class Page(HTMLParser):
    """Collects what the checks need from one page: its text (drawings left out), tags and ids."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.tags = []  # (tag, attrs dict)
        self.ids = set()
        self._skip = 0
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag in ("script", "style", "svg"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)

    @property
    def words(self):
        return " ".join(self.text)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def tracked_text_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    files = []
    for name in out:
        path = ROOT / name
        if path.suffix in (".woff2", ".png", ".webp") or not path.is_file():
            continue
        files.append(path)
    return files


class TestBuild(unittest.TestCase):
    """T-HM-2-1"""

    def test_pages_match_the_data(self):
        pages = build.Site().pages()
        for name in PAGES:
            with self.subTest(page=name):
                self.assertEqual(read(name), pages[name], f"{name} is stale: run python3 scripts/build.py")

    def test_every_count_is_a_whole_number_with_a_read_date(self):
        data = json.loads(read("src/site.json"))
        self.assertTrue(data["counts"])
        for key, count in data["counts"].items():
            with self.subTest(count=key):
                self.assertIsInstance(count["value"], int)
                self.assertNotIsInstance(count["value"], bool)
                self.assertRegex(count["read"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(count["from"])

    def test_a_count_shown_on_a_page_carries_its_value_from_the_data(self):
        site = build.Site()
        self.assertEqual(site.text("{n:smithy_verdicts}"), f"{site.counts['smithy_verdicts']['value']:,}")
        adrs = site.counts["adrs_all"]["value"]
        self.assertEqual(site.text("{over:adrs_all}"), f"{(adrs - 1) // 50 * 50:,}")
        self.assertIn('datetime="2026-11-25"', site.text("{read:smithy_items}"))

    def test_over_is_the_largest_multiple_of_50_below_the_count(self):
        # the copy says "more than {over:key}", so an exact multiple of 50 must not print itself
        site = build.Site()
        for value, shown in ((51, "50"), (99, "50"), (100, "50"), (101, "100"), (300, "250"), (570, "550"), (1201, "1,200")):
            site.counts["probe"] = {"value": value, "read": "2026-11-25", "from": "a test"}
            with self.subTest(value=value):
                self.assertEqual(site.text("{over:probe}"), shown)
                self.assertLess(int(shown.replace(",", "")), value)
        for value in (0, 49, 50):
            site.counts["probe"] = {"value": value, "read": "2026-11-25", "from": "a test"}
            with self.subTest(value=value), self.assertRaises(ValueError):
                site.text("{over:probe}")

    def test_every_more_than_uses_over(self):
        # a read value printed after "more than" would be false: it is the count itself
        source = read("src/site.json")
        self.assertNotRegex(source, r"more than \{n:")
        self.assertIn("more than {over:minigames_tests} tests", source)

    def test_an_unknown_count_or_placeholder_fails_the_build(self):
        site = build.Site()
        with self.assertRaises(ValueError):
            site.text("{n:no_such_count}")
        with self.assertRaises(ValueError):
            site.text("{count:smithy_items}")

    def test_a_text_value_may_not_carry_markup_outside_the_allowlist(self):
        site = build.Site()
        bad_values = (
            '<script>x</script>', '<img src="/x.png">', '<a onclick="x">y</a>', "<b>open",
            # wrappers that hide a tag from the parser and not from a browser
            "<!--><script>x</script>", "<![CDATA[><script>x</script>", "<?x><script>y</script>",
            "<b>x</b><!x>", "<!-- a comment -->",
            # an unfinished tag the parser reads as text, which a browser finishes with the page
            "hello <script src=/x.js", "a <img src=x onerror=y",
            # a link may not run a script or leave for another host without https
            '<a href="javascript:alert(1)">x</a>', '<a href="&#106;avascript:x">x</a>',
            '<a href="//example.com">x</a>', '<a href="http://example.com">x</a>', '<a href="data:text/html,x">x</a>',
            "<b/>",
        )
        for bad in bad_values:
            with self.subTest(value=bad), self.assertRaises(build.FragmentError):
                site.text(bad)

    def test_the_allowlist_still_takes_what_the_pages_use(self):
        site = build.Site()
        for good in ('<a href="https://arbopedia.mx">a</a>', '<a href="/how-i-build.html">b</a>', '<a href="#menu">c</a>',
                     '<span lang="es">[pendiente]</span>', "<b>x</b> &lt; y", "<code>make ci</code>"):
            with self.subTest(value=good):
                self.assertEqual(site.text(good), good)

    def with_data(self, change):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "src", root / "src")
            data = json.loads((root / "src" / "site.json").read_text(encoding="utf-8"))
            change(data)
            (root / "src" / "site.json").write_text(json.dumps(data), encoding="utf-8")
            return build.Site(root).pages()

    def test_an_id_or_a_colour_may_not_carry_markup(self):
        # ids go into id="...", class names and file names; a block colour goes into style="..."
        hostile = '"><script>x</script>'
        changes = {
            "rows id": lambda d: d["rows"][0].update(id=hostile),
            "project id": lambda d: d["home"]["projects"][0].update(id=hostile),
            "line id": lambda d: d["home"]["lines"][0].update(id=hostile),
            "map item": lambda d: d["how_i_build"]["board"]["held"].append(hostile),
            "placed item": lambda d: d["how_i_build"]["board"]["placed"]["Done"].append("../x"),
            "done id": lambda d: d["how_i_build"]["board"]["done"][0].update(id=hostile),
            "block": lambda d: d["home"]["projects"][0].update(block='red;}</style><script>x</script>'),
            "row link": lambda d: d["rows"][0].update(open="javascript:alert(1)"),
            "project link": lambda d: d["home"]["projects"][0]["link"].update(href="javascript:alert(1)"),
            "site link": lambda d: d["site"]["links"][0].update(href="javascript:alert(1)"),
        }
        for name, change in changes.items():
            with self.subTest(change=name), self.assertRaises(ValueError):
                self.with_data(change)

    def test_a_count_never_shown_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "src", root / "src")
            data = json.loads((root / "src" / "site.json").read_text(encoding="utf-8"))
            data["counts"]["unused"] = {"value": 1, "read": "2026-11-25", "from": "a test"}
            (root / "src" / "site.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unused"):
                build.Site(root).pages()


class TestContentRules(unittest.TestCase):
    """T-HM-2-2"""

    def test_no_excluded_employer_in_any_tracked_file(self):
        for path in tracked_text_files():
            words = set(re.findall(r"[a-z0-9]+", path.read_text(encoding="utf-8", errors="replace").lower()))
            hits = {hashlib.sha256(w.encode()).hexdigest() for w in words} & BANNED_WORD_HASHES
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertFalse(hits, "a word the house rules exclude is in this file")

    def test_no_email_in_any_tracked_file(self):
        for path in tracked_text_files():
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", path.read_text(encoding="utf-8")))

    def test_no_phone_number_on_a_page(self):
        for name in PAGES + ("src/site.json",):
            text = Page(read(name)).words if name.endswith(".html") else read(name)
            text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)  # dates are not phone numbers
            with self.subTest(page=name):
                self.assertIsNone(re.search(r"\+?\d(?:[\s.()-]?\d){7,}", text))

    def test_only_public_hostnames_under_herrada_me(self):
        for name in PAGES + ("src/site.json",):
            found = set(re.findall(r"\b((?:[a-z0-9-]+\.)+herrada\.me)\b", read(name).lower()))
            with self.subTest(page=name):
                self.assertLessEqual(found, ALLOWED_SUBDOMAINS)

    def test_links_leave_only_for_the_public_list(self):
        for name in PAGES:
            for tag, attrs in Page(read(name)).tags:
                href = attrs.get("href") or ""
                if tag == "a" and href.startswith(("http:", "https:", "//")):
                    with self.subTest(page=name, href=href):
                        self.assertIn(href, ALLOWED_LINKS)


class TestNoThirdParty(unittest.TestCase):
    """T-HM-2-3"""

    def test_every_resource_is_the_sites_own(self):
        for name in PAGES:
            for tag, attrs in Page(read(name)).tags:
                urls = []
                if tag in ("img", "script", "source"):
                    urls.append(attrs.get("src") or "")
                    urls += [part.split()[0] for part in (attrs.get("srcset") or "").split(",") if part.strip()]
                if tag == "link":
                    urls.append(attrs.get("href") or "")
                for url in filter(None, urls):
                    with self.subTest(page=name, tag=tag, url=url[:60]):
                        self.assertTrue(url.startswith("data:") or (url.startswith("/") and not url.startswith("//")))

    def test_the_stylesheet_and_script_name_no_other_host(self):
        css = read("style.css")
        for url in re.findall(r"url\(([^)]*)\)", css):
            url = url.strip("\"' ")
            with self.subTest(url=url):
                self.assertTrue(url.startswith("/") and not url.startswith("//"))
        self.assertNotRegex(css, r"@import")
        self.assertNotRegex(read("script.js"), r"https?://|fetch\(|XMLHttpRequest")


class TestPreview(unittest.TestCase):
    """T-HM-2-4"""

    def test_a_preview_is_noindex_and_says_preview(self):
        data = json.loads(read("src/site.json"))
        if not data["site"]["preview"]:
            self.skipTest("site.preview is off")
        for name in PAGES:
            source = read(name)
            with self.subTest(page=name):
                self.assertIn('<meta name="robots" content="noindex">', source)
                self.assertIn('<p class="foot-note">Preview.', source)
                self.assertNotIn("Prototype", source)
                self.assertNotIn("Direction E", source)

    def test_the_404_is_noindex_on_the_real_site_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "src", root / "src")
            data = json.loads((root / "src" / "site.json").read_text(encoding="utf-8"))
            data["site"]["preview"] = False
            (root / "src" / "site.json").write_text(json.dumps(data), encoding="utf-8")
            pages = build.Site(root).pages()
        self.assertNotIn("noindex", pages["index.html"])
        self.assertNotIn("Preview.", pages["index.html"])
        self.assertIn('<meta name="robots" content="noindex">', pages["404.html"])


class TestLinks(unittest.TestCase):
    """T-HM-2-5"""

    def test_internal_links_and_fragments_resolve(self):
        parsed = {name: Page(read(name)) for name in PAGES}
        targets = {"/": "index.html", "/index.html": "index.html", "/how-i-build.html": "how-i-build.html", "/404.html": "404.html"}
        for name, page in parsed.items():
            for tag, attrs in page.tags:
                href = attrs.get("href")
                if tag != "a" or not href or href.startswith(("http:", "https:")):
                    continue
                with self.subTest(page=name, href=href):
                    path, _, fragment = href.partition("#")
                    target = name if not path else targets.get(path)
                    self.assertIsNotNone(target, f"{href} is not a page of this site")
                    if fragment:
                        self.assertIn(fragment, parsed[target].ids)

    def test_the_404_uses_root_links_only(self):
        # it is served at any missing path, so a relative link would point nowhere
        for tag, attrs in Page(read("404.html")).tags:
            for key in ("href", "src"):
                url = attrs.get(key)
                if url and not url.startswith(("http:", "https:", "data:", "#")):
                    with self.subTest(url=url):
                        self.assertTrue(url.startswith("/"))

    def test_the_images_the_pages_use_exist(self):
        for name in PAGES:
            for tag, attrs in Page(read(name)).tags:
                if tag == "img":
                    for url in [attrs["src"]] + [p.split()[0] for p in (attrs.get("srcset") or "").split(",") if p.strip()]:
                        with self.subTest(page=name, url=url):
                            self.assertTrue((ROOT / url.lstrip("/")).is_file())


class TestFirstScreen(unittest.TestCase):
    """T-HM-2-6: it says who Luis is and what each thing is before anything plays."""

    def test_the_marquee_says_who_and_what_he_builds(self):
        source = read("index.html")
        marquee = re.search(r'<header class="marquee">(.*?)</header>', source, re.S).group(1)
        self.assertIn("<h1", marquee)
        lede = re.search(r'<p class="lede">(.*?)</p>', marquee, re.S)
        self.assertIsNotNone(lede, "the marquee has no lede")
        for name in ("Rentaventa", "Smithy"):
            self.assertIn(name, lede.group(1))

    def test_each_pane_states_its_fact_before_its_loop(self):
        source = read("index.html")
        rows = json.loads(read("src/site.json"))["rows"]
        figures = re.findall(r'<figure class="pv pv-([a-z-]+)">\s*(<[^>]+>)(.*?)</figure>', source, re.S)
        self.assertEqual([f[0] for f in figures], [r["id"] for r in rows])
        for rid, first, rest in figures:
            with self.subTest(row=rid):
                self.assertEqual(first, f'<figcaption class="fact" id="fact-{rid}">')
                fact_text = re.sub(r"<[^>]+>", "", rest.split("</figcaption>")[0]).strip()
                self.assertGreater(len(fact_text), 20)
                self.assertLess(rest.index("</figcaption>"), rest.index('<div class="screen"'))

    def test_a_section_opened_from_the_menu_has_a_way_back_for_touch(self):
        # Esc is for a keyboard. A touch screen shows the link instead (style.css), and
        # script.js gives it the same path back to the chosen row.
        source = read("index.html")
        notes = re.findall(r'<p class="sec-esc">(.*?)</p>', source, re.S)
        self.assertTrue(notes)
        opened = re.findall(r'<section class="sec[^"]*" id="([a-z-]+)" tabindex="-1"', source)
        self.assertEqual(len(notes), len(opened))
        for note in notes:
            with self.subTest(note=note[:40]):
                self.assertIn('<span class="sec-esc-key">Esc goes back to the menu</span>', note)
                self.assertIn('<a class="sec-back" href="#menu">back to the menu</a>', note)
        css = read("style.css")
        self.assertIn(".js .sec.is-open .sec-back { display: inline-block; }", css)
        self.assertIn("closest('a.sec-back')", read("script.js"))

    def test_the_touch_hint_says_tap_stop(self):
        self.assertIn("tap stop to leave", read("index.html"))

    def test_each_row_is_described_by_its_fact_first(self):
        source = read("index.html")
        for row in json.loads(read("src/site.json"))["rows"]:
            with self.subTest(row=row["id"]):
                self.assertIn(f'aria-describedby="fact-{row["id"]} hook-{row["id"]}"', source)


class TestBumpySwitch(unittest.TestCase):
    """T-HM-2-7"""

    def build_with(self, bumpy):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "src", root / "src")
            data = json.loads((root / "src" / "site.json").read_text(encoding="utf-8"))
            data["site"]["bumpy"] = bumpy
            (root / "src" / "site.json").write_text(json.dumps(data), encoding="utf-8")
            return build.Site(root).pages()

    def test_bumpy_on(self):
        pages = self.build_with(True)
        self.assertIn("data-bumpy", pages["index.html"])
        self.assertIn("data-bumpy-toggle", pages["index.html"])
        self.assertIn('class="bumpy" data-pose="sleep"', pages["404.html"])
        self.assertIn("Bumpy, the menu's cursor,", Page(pages["404.html"]).words)
        self.assertNotIn('class="no-bumpy"', pages["index.html"])

    def test_bumpy_off(self):
        pages = self.build_with(False)
        for name, source in pages.items():
            with self.subTest(page=name):
                self.assertIn('<html lang="en" class="no-bumpy">', source)
                self.assertNotIn('class="bumpy"', source)
                self.assertNotIn("Bumpy", Page(source).words)
                self.assertNotIn("Hide Bumpy", source)
        self.assertIn("row-missing-block", pages["404.html"])

    def test_the_preview_keeps_bumpy(self):
        self.assertTrue(json.loads(read("src/site.json"))["site"]["bumpy"])
        self.assertIn("data-bumpy-toggle", read("index.html"))


class TestFont(unittest.TestCase):
    """T-HM-2-8"""

    def test_font_files_are_woff2_under_the_ofl(self):
        license_text = read("fonts/OFL.txt")
        self.assertIn("SIL Open Font License, Version 1.1", license_text)
        self.assertIn("Bricolage Grotesque", license_text)
        css_urls = re.findall(r'src: url\("(/fonts/[^"]+)"\) format\("woff2"\)', read("style.css"))
        self.assertTrue(css_urls)
        for url in css_urls:
            with self.subTest(font=url):
                self.assertEqual((ROOT / url.lstrip("/")).read_bytes()[:4], b"wOF2")

    def test_the_preload_is_the_file_the_stylesheet_asks_for(self):
        css_urls = set(re.findall(r'src: url\("(/fonts/[^"]+)"\)', read("style.css")))
        for name in PAGES:
            preloads = re.findall(r'<link rel="preload" href="([^"]+)" as="font" type="font/woff2" crossorigin>', read(name))
            with self.subTest(page=name):
                self.assertEqual(len(preloads), 1)
                self.assertIn(preloads[0], css_urls)


class TestStylesheetKnowsEveryRow(unittest.TestCase):
    """T-HM-2-9: the menu works without JavaScript because the stylesheet names each row."""

    def test_each_row_has_its_pane_rule_and_cursor_index(self):
        css = read("style.css")
        rows = json.loads(read("src/site.json"))["rows"]
        self.assertIn(f".pv-{rows[0]['id']} {{ display: block; }}", css)
        for i, row in enumerate(rows[1:], start=1):
            rid = row["id"]
            with self.subTest(row=rid):
                self.assertIn(f".select:has(#s-{rid}:checked) .pv-{rid}", css)
                self.assertIn(f".list:has(#s-{rid}:checked) {{ --i: {i}; }}", css)


if __name__ == "__main__":
    unittest.main()
