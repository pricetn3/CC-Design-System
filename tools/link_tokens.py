#!/usr/bin/env python3
"""Link exported prototype pages to the shared design tokens.

Each Claude Design export carries its own copy of the tokens. This script adds
one <link> to the shared tokens.css (published from this repo) right after that
copy, so the shared file wins: change a token here, push this repo, and every
linked page picks it up. The page's own copy stays as a fallback if the shared
file can't load.

Some exports also link the shared components.css themselves (marked
data-cc-shared-components, added in Claude Design). Those are kept pointing at
the current address too.

Run it after every new export. With no arguments it covers every page listed in
prototypes.json; pages already linked are skipped, and pages linked to an old
address are moved to the current one.

    python3 tools/link_tokens.py                 # link every listed page
    python3 tools/link_tokens.py <page> ...      # link specific pages
    python3 tools/link_tokens.py --check         # only report status
    python3 tools/link_tokens.py --unlink        # undo, restoring the original exports
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drift_check import display_name, load_registry, registry_pages  # noqa: E402

SHARED_URL = load_registry()["sharedTokensUrl"]
COMPONENTS_URL = load_registry()["sharedComponentsUrl"]
COMPONENTS_RE = re.compile(r'<link rel="stylesheet" href="([^"]*)" data-cc-shared-components>')
MARKER = "data-cc-shared-tokens"
TEMPLATE_RE = re.compile(r'(<script type="__bundler/template">\s*)(".*?")(\s*</script>)', re.S)
LINK_RE = re.compile(r'\n?<link rel="stylesheet" href="([^"]*)" ' + MARKER + r'>')


def encode(template):
    # Same encoding Claude Design uses, so untouched parts of a page stay byte-identical.
    return json.dumps(template, ensure_ascii=False).replace("</", "<\\u002F")


def process(path, mode):
    with open(path, encoding="utf-8") as f:
        page = f.read()
    m = TEMPLATE_RE.search(page)
    if not m:
        return "not a Claude Design export, skipped"
    template = json.loads(m.group(2))
    current = LINK_RE.search(template)

    old_components = [c.group(1) for c in COMPONENTS_RE.finditer(template) if c.group(1) != COMPONENTS_URL]
    if mode == "check":
        if not current:
            return "NOT linked"
        if current.group(1) != SHARED_URL:
            return f"linked to an OLD address: {current.group(1)}"
        return f"components linked to an OLD address: {old_components[0]}" if old_components else "linked"
    if mode == "unlink":
        if not current:
            return "not linked"
        template = LINK_RE.sub("", template)
        result = "unlinked"
    elif current:
        if current.group(1) == SHARED_URL and not old_components:
            return "already linked"
        template = template[:current.start(1)] + SHARED_URL + template[current.end(1):]
        template = COMPONENTS_RE.sub(f'<link rel="stylesheet" href="{COMPONENTS_URL}" data-cc-shared-components>', template)
        result = "moved to the current address"
    else:
        root = template.find(":root")
        close = template.find("</style>", root) if root != -1 else -1
        if close == -1:
            return "no token block found, skipped"
        at = close + len("</style>")
        template = template[:at] + f'\n<link rel="stylesheet" href="{SHARED_URL}" {MARKER}>' + template[at:]
        result = "linked"

    page = page[:m.start(2)] + encode(template) + page[m.end(2):]
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return result


def main(argv):
    mode = "check" if "--check" in argv else "unlink" if "--unlink" in argv else "link"
    files = [a for a in argv if not a.startswith("--")]
    pages = [os.path.abspath(os.path.expanduser(p)) for p in files] if files else registry_pages()
    for p in pages:
        print(f"{display_name(p):55} {process(p, mode)}")


if __name__ == "__main__":
    main(sys.argv[1:])
