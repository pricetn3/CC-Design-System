#!/usr/bin/env python3
"""Design system drift check.

Compares every prototype page in this repo against the design system in
design-system/tokens.css and design-system/components.css, and reports
anything that has drifted:

  * token values that differ from the source of truth (or are missing)
  * colors typed out by hand instead of using a token
  * colors that aren't in the system at all
  * corner radii and button heights that are off the scale
  * buttons smaller than the WCAG 2.2 AA 24px target minimum
  * typefaces other than Inter / Roboto Mono

Usage:
    python3 tools/drift_check.py            # check every page
    python3 tools/drift_check.py "~/Documents/GitHub/CC-Prototype/external.html"

With no arguments it checks every page listed in prototypes.json.

Exit code is 1 when there are errors (token mismatches or off-system colors),
so the same script can later run automatically on GitHub before publishing.
"""
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKENS_CSS = os.path.join(ROOT, "tokens.css")
ALLOWLIST = os.path.join(ROOT, "drift-allowlist.json")
REGISTRY = os.path.join(ROOT, "prototypes.json")


BUTTON_HEIGHTS = {32, 36, 40, 44}   # xs / sm / md / lg, see components.css
MIN_TARGET = 24                     # WCAG 2.2 AA, 2.5.8 Target Size (Minimum)
ICON_BUTTON_SIZES = {32, 36, 40}
ALLOWED_FONTS = {"inter", "roboto mono", "system-ui", "-apple-system", "blinkmacsystemfont",
                 "sans-serif", "monospace", "ui-monospace", "sfmono-regular", "menlo", "inherit"}

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([\d.]+)\s*)?\)")
ROOT_BLOCK_RE = re.compile(r":root\s*\{[^}]*\}")
TOKEN_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


# ---------------------------------------------------------------- helpers
def norm_value(v):
    return re.sub(r"\s+", " ", v.strip()).lower().replace(", ", ",")


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def load_tokens(css):
    return {k: v.strip() for k, v in TOKEN_RE.findall(" ".join(ROOT_BLOCK_RE.findall(css)))}


def unpack(path):
    """Return the page's real HTML. Claude Design exports keep it JSON-encoded
    inside a <script type="__bundler/template"> tag; plain pages are returned as-is."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    m = re.search(r'<script type="__bundler/template">\s*(".*?")\s*</script>', raw, re.S)
    html = json.loads(m.group(1)) if m else raw
    # Drop embedded images/fonts so they can't produce false matches.
    html = re.sub(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+", "data:", html)
    return html, bool(m)


def line_hint(text, pos):
    """A short, readable snippet around a match, used to point at where it is."""
    start = max(text.rfind("\n", 0, pos) + 1, pos - 70)
    end = text.find("\n", pos)
    end = min(end if end != -1 else len(text), pos + 70)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def style_name_at(text, pos):
    """Name of the style object a match sits in, e.g. 'orderBtnStyle'."""
    names = list(re.finditer(r"\b(\w+Style)\s*[:=]\s*\{", text[max(0, pos - 1500):pos]))
    return names[-1].group(1) if names else None


# Where a color appears decides how it's reported.
CONTEXT_GROUPS = [
    ("theme", "Theme / dark-mode palette defined in the page",
     "If dark mode is part of the product, add these as dark tokens in tokens.css."),
    ("institution", "Partner institution brand colors (sample data)",
     "Expected. Add to drift-allowlist.json to silence."),
    ("canvas", "Drawn artwork (canvas)",
     "Fine for illustrations; use tokens if it's UI."),
    ("svg", "Inline icon / logo artwork",
     "Fine for third-party logos; product icons should use currentColor or tokens."),
]


def iter_colors(text):
    for m in HEX_RE.finditer(text):
        if text[m.end():m.end() + 1].isalnum():
            continue
        yield m.group(0), hex_to_rgb(m.group(0)), m.start()
    for m in RGB_RE.finditer(text):
        if m.group(4) is not None and float(m.group(4)) < 1:
            continue  # translucent overlays and shadows are expected
        yield m.group(0), tuple(int(m.group(i)) for i in (1, 2, 3)), m.start()


def color_context(text, pos):
    before = text[max(0, pos - 220):pos]
    near = text[max(0, pos - 40):pos]
    if re.search(r"[\"']--[\w-]+[\"']\s*:\s*(?:\w+\()?[\"']?$", near):
        return "theme"
    if re.search(r"registrar|estYear|seal\s*:|headerBg|logo\s*:", before + text[pos:pos + 160]):
        return "institution"
    if re.search(r"(fill|stroke)Style\s*=\s*[\"']?$|createLinearGradient|addColorStop\([^)]*$", near):
        return "canvas"
    if re.search(r"\b(fill|stroke|stop-color)\s*=\s*\\?[\"']$", near):
        return "svg"
    return "style"


# ---------------------------------------------------------------- checks
def check_page(path, canon, color_to_token, allowed_colors):
    html, is_export = unpack(path)
    is_email = os.sep + "emails" + os.sep in path
    errors, warnings, notes = [], [], []

    if is_export and "data-cc-shared-tokens" not in html:
        errors.append("Not linked to the shared tokens file. Run: python3 tools/link_tokens.py")
    for old in load_registry().get("oldAddresses", []):
        if old in html:
            errors.append(f"Loads the design system from its old address ({old}). Run: python3 tools/link_tokens.py, "
                          "and update the address in Claude Design so the next export doesn't bring it back.")

    # 1. Token values ------------------------------------------------------
    page_tokens = load_tokens(html)
    if not is_email:
        if not page_tokens:
            errors.append("No design tokens found on this page. It isn't using the design system.")
        else:
            changed = [(k, canon[k], v) for k, v in page_tokens.items()
                       if k in canon and norm_value(v) != norm_value(canon[k])]
            missing = [k for k in canon if k not in page_tokens]
            extra = [k for k in page_tokens if k not in canon]
            for k, want, got in changed:
                errors.append(f"Token {k} is {got} here but {want} in the system.")
            if missing:
                errors.append(f"{len(missing)} tokens missing: {', '.join(missing[:6])}{' …' if len(missing) > 6 else ''}")
            for k in extra:
                warnings.append(f"Defines {k} = {page_tokens[k]}, which isn't in the system. Add it to tokens.css or replace it.")

    # Everything below looks only at the page's own styles, not the token block
    # or comments (comments often mention colors without using them).
    body = ROOT_BLOCK_RE.sub("", html)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"(?m)^\s*//.*$", "", body)

    # 2. Hard-coded colors --------------------------------------------------
    by_token = collections.defaultdict(list)                       # token -> [literal, ...]
    found = collections.defaultdict(lambda: collections.defaultdict(list))  # kind -> hex -> [snippet]
    for literal, rgb, pos in iter_colors(body):
        full = rgb_to_hex(rgb)
        if literal.lower() in allowed_colors or full in allowed_colors:
            continue
        kind = color_context(body, pos)
        if rgb in color_to_token and kind == "style":
            by_token[color_to_token[rgb]].append(literal)
        elif rgb not in color_to_token:
            found[kind][full].append(line_hint(body, pos))

    for hx, hits in sorted(found["style"].items(), key=lambda kv: -len(kv[1])):
        near = nearest_token(hex_to_rgb(hx), color_to_token)
        msg = f"Off-system color {hx} used {len(hits)}× (closest token: {near})."
        msg += f"\n        e.g. …{hits[0][:110]}…"
        (warnings if is_email else errors).append(msg)
    for kind, label, advice in CONTEXT_GROUPS:
        if found[kind]:
            sample = ", ".join(list(found[kind])[:6]) + (" …" if len(found[kind]) > 6 else "")
            warnings.append(f"{label}: {len(found[kind])} colors not in tokens.css ({sample}). {advice}")
    if by_token and not is_email:
        parts = [f"{hits[0]}→{tok} ×{len(hits)}" for tok, hits in sorted(by_token.items(), key=lambda kv: -len(kv[1]))]
        warnings.append(f"Token colors typed by hand instead of var(--…): " + ", ".join(parts))

    if is_email:
        notes.append("Email template: checked colors only (email clients can't use CSS tokens).")
        return errors, warnings, notes, is_export

    # 3. Radius --------------------------------------------------------------
    radius_tokens = {v.strip(): k for k, v in canon.items() if k.startswith("--radius-")}
    radius_hits = collections.Counter()
    for m in re.finditer(r"border-?[rR]adius\s*:\s*[\"']?(\d+)(px)?(?![\d%])", body):
        n = int(m.group(1))
        if n == 0:
            continue
        radius_hits["9999px" if n >= 999 else f"{n}px"] += 1
    on_scale = [(px, n) for px, n in radius_hits.most_common() if px in radius_tokens]
    off_scale = [(px, n) for px, n in radius_hits.most_common() if px not in radius_tokens]
    if off_scale:
        warnings.append("Radii off the scale: " + ", ".join(f"{px} ×{n}" for px, n in off_scale)
                        + ". The scale is 2 / 4 / 6 / 8 / 10 / 12 / 16 / 20 / 24 / full.")
    if on_scale:
        warnings.append("Radii typed by hand instead of var(--radius-…): "
                        + ", ".join(f"{px}→{radius_tokens[px]} ×{n}" for px, n in on_scale))

    # 4. Button heights --------------------------------------------------------
    odd = collections.defaultdict(set)
    tiny = collections.defaultdict(set)   # below the WCAG target minimum
    for m in re.finditer(r"\b(?:min[hH]eight|height)\s*:\s*[\"']?(\d+)(?:px)?[\"']?", body):
        name = style_name_at(body, m.start())
        if not name or not re.search(r"Btn|Button", name):
            continue
        h = int(m.group(1))
        if h == 0 or h > 56:      # collapsed/animated states and large tiles aren't buttons sizes
            continue
        if h < MIN_TARGET:
            tiny[h].add(name)
            continue
        sizes = ICON_BUTTON_SIZES if re.search(r"Icon|Menu|Close|Collapse|Avatar|support", name, re.I) else BUTTON_HEIGHTS
        if h not in sizes:
            odd[h].add(name)
    if odd:
        parts = [f"{h}px ({', '.join(sorted(names)[:3])}{' …' if len(names) > 3 else ''})" for h, names in sorted(odd.items())]
        warnings.append("Button heights off the 32 / 36 / 40 / 44 scale: " + "; ".join(parts))
    for h, names in sorted(tiny.items()):
        errors.append(f"Button only {h}px tall: below the 24px WCAG 2.2 AA target minimum (2.5.8): "
                      + ", ".join(sorted(names)[:4]) + (" …" if len(names) > 4 else ""))

    # 5. Typefaces ----------------------------------------------------------------
    fonts = set()
    for m in re.finditer(r"font-?[fF]amily\s*:\s*([^;\"}\n]+)", body):
        for fam in m.group(1).split(","):
            fam = fam.strip().strip("'\"").lower()
            if fam and not fam.startswith("var(") and fam not in ALLOWED_FONTS:
                fonts.add(fam)
    for fam in sorted(fonts):
        warnings.append(f"Typeface '{fam}' isn't part of the system (Inter / Roboto Mono).")

    return errors, warnings, notes, is_export


def nearest_token(rgb, color_to_token):
    best = min(color_to_token.items(), key=lambda kv: sum((a - b) ** 2 for a, b in zip(kv[0], rgb)))
    return f"var({best[1]}) {rgb_to_hex(best[0])}"


# ---------------------------------------------------------------- pages
def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def registry_pages():
    """Every prototype page listed in prototypes.json that exists on this Mac."""
    reg = load_registry()
    base = os.path.expanduser(reg["base"])
    pages = []
    for repo, patterns in reg["repos"].items():
        for pattern in patterns:
            pages += glob.glob(os.path.join(base, repo, pattern))
    return sorted(set(pages))


def display_name(path):
    base = os.path.expanduser(load_registry()["base"])
    rel = os.path.relpath(path, base)
    return path if rel.startswith("..") else rel


# ---------------------------------------------------------------- main
def main(argv):
    with open(TOKENS_CSS, encoding="utf-8") as f:
        canon = load_tokens(f.read())
    with open(ALLOWLIST, encoding="utf-8") as f:
        allowed_colors = {k.lower() for k in json.load(f)["colors"]}

    # Map every literal color token to its name (first, i.e. most specific, wins).
    color_to_token = {}
    for k, v in canon.items():
        v = v.strip()
        rgb = None
        if HEX_RE.fullmatch(v):
            rgb = hex_to_rgb(v)
        else:
            m = RGB_RE.fullmatch(v)
            if m and m.group(4) is None:
                rgb = tuple(int(m.group(i)) for i in (1, 2, 3))
        if rgb and rgb not in color_to_token:
            color_to_token[rgb] = k

    if argv:
        pages = [os.path.abspath(os.path.expanduser(p)) for p in argv]
    else:
        pages = registry_pages()

    total_err = total_warn = 0
    print(f"\nDesign system drift check · {len(canon)} tokens · {len(pages)} pages\n")
    for p in pages:
        errors, warnings, notes, is_export = check_page(p, canon, color_to_token, allowed_colors)
        total_err += len(errors)
        total_warn += len(warnings)
        status = "✗" if errors else ("!" if warnings else "✓")
        print(f"{status} {display_name(p)}  ({len(errors)} errors, {len(warnings)} warnings)")
        for e in errors:
            print(f"    ERROR  {e}")
        for w in warnings:
            print(f"    warn   {w}")
        for n in notes:
            print(f"    note   {n}")
        print()

    print(f"Total: {total_err} errors, {total_warn} warnings.")
    print("Errors = differs from the system. Warnings = works, but should use a token or the standard size.\n")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
