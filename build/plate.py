"""Plate 1, the stand: ten projects drawn as trees, and Smithy's roots under them.

Every mark is a count or a fact, read from counts.json ("plate"). Units are SVG user units:
at a 390 px phone the plate is 350 wide and one month of work is 10 units tall.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "counts.json"), encoding="utf-8") as fh:
    PLATE = json.load(fh)["plate"]

U = 10.0                # one month
X0, PITCH = 34.0, 31.2  # first column edge, column pitch
W = 350.0               # viewBox width
# The ground line sits 300 units down, or lower once the tallest tree needs the room.
G = max(300.0, U * max(t["months"] for t in PLATE) + 30.0)
H = G + 60.0

# n, name, months, planted, on the board, colour class, link
TREES = [(t["n"], t["name"], t["months"], t["planted"], t["board"], t["colour"], "#" + t["sheet"]) for t in PLATE]

# The roots below are drawn by hand for this stand: Smithy is tree 8, runners end at trees 1
# and 10, and risers leave them for trees 2, 3, 6 and 9. A change of the board flags in
# counts.json stops the build here, so the drawing never shows a root the record does not hold.
ROOTS_DRAWN_FOR = {"own": [8], "yes": [1, 2, 3, 6, 9, 10], "no": [4, 5, 7]}
_flags = {k: sorted(t["n"] for t in PLATE if t["board"] == k) for k in ROOTS_DRAWN_FOR}
if _flags != ROOTS_DRAWN_FOR or len(PLATE) != 10:
    raise SystemExit(f"plate.py: the roots were drawn for {ROOTS_DRAWN_FOR}, counts.json says {_flags}; redraw roots()")


def tx(n):
    return X0 + PITCH * (n - 0.5)


def f(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


# ---------------------------------------------------------------- tree shapes
def ell(cx, cy, rx, ry):
    return f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}"/>'


def trunk(top, w0, w1):
    a, b = w0 / 2, w1 / 2
    return f'<path d="M{f(-a)} 0L{f(-b)} {f(-top)}h{f(w1)}L{f(a)} 0z"/>'


def sprout(h):
    """One or two months: a stem and two leaves. The taller leaf tip is exactly h up."""
    k = h / 10.0
    sw = 1.5 + 0.35 * k
    s = 4.2 * k                      # where the leaves leave the stem
    def leaf(sign, tip_x, tip_y):
        return (f'<path d="M0 {f(-s)}C{f(sign*0.1*k)} {f(-s-0.55*(tip_y-s))} {f(sign*0.42*tip_x)} {f(-tip_y+0.2*k)} '
                f'{f(sign*tip_x)} {f(-tip_y)}C{f(sign*(tip_x+0.5*k))} {f(-s-0.55*(tip_y-s))} '
                f'{f(sign*0.62*tip_x)} {f(-s+0.1*k)} 0 {f(-s)}z"/>')
    return [
        f'<path d="M{f(-sw/2)} 0V{f(-s-0.6*k)}h{f(sw)}V0z"/>',
        leaf(-1, 5.0 * k, 8.9 * k),
        leaf(1, 5.6 * k, 10.0 * k),
    ]


# The four shapes drawn by hand: a trunk (top, base width, top width) and three ellipses
# (cx, cy, rx, ry). Each one's crown tops out at exactly its months times U.
SHAPES = {
    3: ((18, 2.6, 2.0), ((0, -19.6, 8.0, 10.4), (-3.7, -15.4, 6.0, 6.2), (3.9, -16.6, 6.0, 6.8))),      # a sapling
    6: ((40, 3.6, 2.4), ((0, -41.5, 9.2, 18.5), (-4.3, -32.5, 7.6, 10.6), (4.5, -35.0, 7.6, 11.6))),
    9: ((60, 4.4, 2.8), ((0, -63.5, 11.2, 26.5), (-5.3, -51.0, 9.2, 14.6), (5.6, -54.5, 9.2, 15.8))),
    27: ((124, 7.6, 4.6), ((0, -192, 12.2, 78), (-5.5, -159, 10.6, 44), (5.7, -169, 10.4, 46))),  # a poplar
}


def tree_shapes(months):
    """A tree exactly months * U tall. One or two months is a sprout. Any other count takes
    the nearest hand-drawn shape at or below it, stretched upward to its height."""
    h = months * U
    if months <= 2:
        return sprout(h)
    ref = max(m for m in SHAPES if m <= months)
    k = months / ref
    (top, w0, w1), ells = SHAPES[ref]
    return [trunk(top * k, w0, w1)] + [ell(cx, cy * k, rx, ry * k) for cx, cy, rx, ry in ells]


# ---------------------------------------------------------------- roots
def catmull(points):
    """Uniform Catmull-Rom through points, as cubic Bezier segments."""
    p = [points[0]] + list(points) + [points[-1]]
    segs = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append((p1, c1, c2, p2))
    return segs


def bez(seg, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    m = 1 - t
    x = m**3 * x0 + 3 * m * m * t * x1 + 3 * m * t * t * x2 + t**3 * x3
    y = m**3 * y0 + 3 * m * m * t * y1 + 3 * m * t * t * y2 + t**3 * y3
    dx = 3 * m * m * (x1 - x0) + 6 * m * t * (x2 - x1) + 3 * t * t * (x3 - x2)
    dy = 3 * m * m * (y1 - y0) + 6 * m * t * (y2 - y1) + 3 * t * t * (y3 - y2)
    return x, y, dx, dy


def sample(segs, step=1.7):
    pts = []
    for seg in segs:
        (x0, y0), _, _, (x3, y3) = seg
        n = max(4, int(math.hypot(x3 - x0, y3 - y0) / step) + 1)
        for i in range(n):
            pts.append(bez(seg, i / n))
    pts.append(bez(segs[-1], 1))
    out, s = [], 0.0
    for i, (x, y, dx, dy) in enumerate(pts):
        if i:
            s += math.hypot(x - pts[i - 1][0], y - pts[i - 1][1])
        out.append((x, y, dx, dy, s))
    return out


def centre_d(segs):
    d = f"M{f(segs[0][0][0])} {f(segs[0][0][1])}"
    for _, c1, c2, p in segs:
        d += f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p[0])} {f(p[1])}"
    return d


def taper_d(pts, w0, w1, power=0.9):
    """A root as a filled shape: w0 wide where it starts, w1 where it ends."""
    total = pts[-1][4]
    left, right = [], []
    for x, y, dx, dy, s in pts:
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        w = (w0 + (w1 - w0) * (s / total) ** power) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    poly = left + right[::-1]
    return "M" + "L".join(f"{f(x)} {f(y)}" for x, y in poly) + "z"


def at_x(pts, x_target):
    """Arc length and y where a sampled root crosses x."""
    best = min(pts, key=lambda p: abs(p[0] - x_target))
    return best[4], best[1]


def roots():
    """Smithy's roots. A root rises only to a tree whose record says 'on the board: yes',
    so the drawing holds six roots and six nodes and nothing else below the line."""
    sx = tx(8)
    yo = lambda pts: [(x, G + dy) for x, dy in pts]
    # the left runner dips a little deeper under the three trees it does not feed (7, 5, 4)
    left = catmull(yo([
        (sx, 1.5), (sx - 0.5, 11), (sx - 4.6, 21.5), (sx - 15, 28.5), (tx(7), 33), (tx(7) - 15.6, 31),
        (tx(6) + 3, 26.6), (tx(6) - 14, 28.4), (tx(5), 33), (tx(5) - 15.6, 34.4), (tx(4), 33),
        (tx(4) - 15.6, 29), (tx(3) + 2, 26.2), (tx(3) - 15, 27.6), (tx(2) + 2, 25.6), (tx(2) - 13.5, 25),
        (tx(1) + 7.5, 20.6), (tx(1) + 1.7, 11.8), (tx(1), 3.6),
    ]))
    right = catmull(yo([
        (sx, 1.5), (sx + 0.6, 11), (sx + 5, 21), (sx + 15, 26.4), (tx(9) - 1, 27.4), (tx(9) + 12, 26.4),
        (tx(10) - 9, 22.6), (tx(10) - 2.6, 14.6), (tx(10) - 0.2, 8), (tx(10), 3.6),
    ]))
    lp, rp = sample(left), sample(right)

    def riser(runner_pts, target, direction):
        """Leaves the runner about 14 units before the tree and bends up to its base."""
        x = tx(target)
        s0, y0 = at_x(runner_pts, x - direction * 14.5)
        y0 -= G
        segs = catmull(yo([
            (x - direction * 14.5, y0), (x - direction * 8.2, y0 - 2.6), (x - direction * 3.0, y0 - 9.0),
            (x - direction * 0.5, y0 - 17.0), (x, 3.4),
        ]))
        return segs, s0

    art, reveal, nodes = [], [], []
    art.append(taper_d(lp, 4.2, 1.5))
    art.append(taper_d(rp, 3.6, 1.5, 0.8))
    speed = 0.31                                   # units per millisecond
    t_left = lp[-1][4] / speed
    t_right = rp[-1][4] / speed
    reveal.append((centre_d(left), 0, t_left, "linear"))
    reveal.append((centre_d(right), 0, t_right, "linear"))
    nodes.append((tx(1), t_left))
    nodes.append((tx(10), t_right))
    for target in (6, 3, 2):
        segs, s0 = riser(lp, target, -1)
        pts = sample(segs)
        art.append(taper_d(pts, 2.0, 1.35))
        t0 = s0 / speed
        reveal.append((centre_d(segs), t0, pts[-1][4] / speed, "ease-out"))
        nodes.append((tx(target), t0 + pts[-1][4] / speed))
    segs, s0 = riser(rp, 9, 1)
    pts = sample(segs)
    art.append(taper_d(pts, 2.0, 1.35))
    reveal.append((centre_d(segs), s0 / speed, pts[-1][4] / speed, "ease-out"))
    nodes.append((tx(9), s0 / speed + pts[-1][4] / speed))
    return art, reveal, nodes, max(t_left, t_right)


# ---------------------------------------------------------------- the drawing
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


def planted_together():
    """The trees planted in the month with the most first commits, when that is three or more."""
    by_month = {}
    for t in PLATE:
        if len(t["planted"]) >= 7:
            by_month.setdefault(t["planted"][:7], []).append(t)
    best = max(by_month.values(), key=len, default=[])
    return best if len(best) >= 3 else []


def bracket():
    group = planted_together()
    if not group:
        return None
    year, month = group[0]["planted"][:7].split("-")
    return group[0]["n"], group[-1]["n"], f"PLANTED {MONTH_NAMES[int(month) - 1].upper()} {year}"


def plate_svg(indent="        "):
    """The plate as inline SVG. It is hidden from assistive tech: the key table under it
    carries the same facts, and its links are the ones a keyboard reaches."""
    o = []
    a = o.append
    a(f'<svg class="stand__svg" viewBox="0 0 {f(W)} {f(H)}" width="{f(W)}" height="{f(H)}" aria-hidden="true" focusable="false">')
    art, reveal, nodes, t_roots = roots()
    a('  <defs>')
    a(f'    <mask id="roots-reveal" maskUnits="userSpaceOnUse" x="0" y="{f(G - 2)}" width="{f(W)}" height="{f(H - G + 2)}">')
    for d, t0, dur, ease in reveal:
        a(f'      <path class="rv" pathLength="1" d="{d}" style="--t:{t0:.0f}ms;--d:{dur:.0f}ms;--e:{ease}"/>')
    a('    </mask>')
    a('  </defs>')
    a('  <g class="scale">')
    for months in range(6, int(G / U) - 2, 6):
        y = G - months * U
        a(f'    <line x1="22" y1="{f(y)}" x2="{f(W)}" y2="{f(y)}"/><text x="0" y="{f(y)}" dominant-baseline="central">{months}</text>')
    a(f'    <text class="scale__unit" x="0" y="{f(G - 24 * U - 16)}" dominant-baseline="central">MONTHS</text>')
    a('  </g>')
    # The month with the most first commits (three or more) gets one bracket on the drawing.
    b = bracket()
    if b:
        first, last, label = b
        bx0, bx1, by = tx(first) - 11, tx(last) + 11, G - 72
        a('  <g class="bracket">')
        a(f'    <path d="M{f(bx0)} {f(by + 6)}V{f(by)}H{f(bx1)}V{f(by + 6)}"/>')
        a(f'    <text x="{f((bx0 + bx1) / 2)}" y="{f(by - 8.5)}" dominant-baseline="central">{label}</text>')
        a('  </g>')
    a('  <a class="roots" href="#smithy" tabindex="-1">')
    a("    <title>Smithy’s roots, drawn to the six projects on its board. Go to Smithy’s sheet.</title>")
    a('    <g class="roots__art" mask="url(#roots-reveal)">')
    for d in art:
        a(f'      <path d="{d}"/>')
    a('    </g>')
    for x, t0 in nodes:
        a(f'    <circle class="node" cx="{f(x)}" cy="{f(G + 3.6)}" r="2.4" style="--t:{t0:.0f}ms"/>')
    a(f'    <text class="roots__label" x="{f(W)}" y="{f(G + 48)}" dominant-baseline="central" style="--t:{t_roots:.0f}ms">SMITHY’S ROOTS</text>')
    a('  </a>')
    for n, name, months, planted, board, cls, href in TREES:
        x = tx(n)
        h = months * U
        shapes = "".join(tree_shapes(months))
        unit = "month" if months == 1 else "months"
        small = " is-sprout" if months <= 2 else ""
        a(f'  <a class="tree t{n} c-{cls}{small}" href="{href}" tabindex="-1" transform="translate({f(x)} {f(G)})">')
        a(f'    <title>{n}. {name}, {months} {unit}</title>')
        top = max(h + 21, 48)        # the smallest sprout still gets a target 52 units tall
        a(f'    <rect class="hit" x="{f(-PITCH / 2)}" y="{f(-top)}" width="{f(PITCH)}" height="{f(top + 4)}"/>')
        a(f'    <g class="grow" style="--i:{n - 1};--m:{months}"><g class="edge">{shapes}</g><g class="fill">{shapes}</g></g>')
        a(f'    <circle class="ring" cy="{f(-h - 10.5)}" r="8.8"/>')
        a(f'    <text class="num" y="{f(-h - 10.5)}" dominant-baseline="central" style="--i:{n - 1};--m:{months}">{n}</text>')
        if n == 2:
            # The one tree that is named on the drawing: the tall one. The roots carry the other name.
            a(f'    <text class="tag" x="23" y="{f(-h + 60)}" dominant-baseline="central" style="--i:{n - 1};--m:{months}">{name.upper()}</text>')
        a('  </a>')
    # One line at the top right names the tree under the pointer, the row with the keyboard,
    # or the tree a sheet's link pointed at. Only one of the ten ever shows.
    a('  <g class="readouts">')
    for n, name, months, planted, board, cls, href in TREES:
        unit = "month" if months == 1 else "months"
        a(f'    <text class="readout r{n}" x="{f(W)}" y="{f(G - 24 * U - 16)}" dominant-baseline="central">'
          f'<tspan class="readout__n">{n}</tspan><tspan dx="5">{name}</tspan><tspan class="readout__m" dx="5">{months} {unit}</tspan></text>')
    a('  </g>')
    a(f'  <line class="ground" x1="0" y1="{f(G)}" x2="{f(W)}" y2="{f(G)}"/>')
    gx = 13.5
    a('  <g class="figure">')
    a(f'    <circle cx="{f(gx)}" cy="{f(G - 8.45)}" r="1.55"/><rect x="{f(gx - 1.75)}" y="{f(G - 6.55)}" width="3.5" height="3.9" rx="1.1"/>'
      f'<rect x="{f(gx - 1.6)}" y="{f(G - 3.4)}" width="1.3" height="2.4"/><rect x="{f(gx + 0.3)}" y="{f(G - 3.4)}" width="1.3" height="2.4"/>')
    a('  </g>')
    a('</svg>')
    return "\n".join(indent + line for line in o)


if __name__ == "__main__":
    print(plate_svg(""))
