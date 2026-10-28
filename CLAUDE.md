# CC Design System

The coded source of truth for the Credential Connections design system, published with GitHub Pages at https://pricetn3.github.io/CC-Design-System/. The owner is a designer, not a developer: explain things in plain language and preview changes before publishing.

The master is the **Credential Connections Design System in Claude Design**. Change tokens and components there first, then mirror the change here. Don't make design changes only in this repo.

## What's here
- `tokens.css`: the canonical token values (colors, type, spacing, radius, shadows). Every linked prototype loads it from https://pricetn3.github.io/CC-Design-System/tokens.css.
- `components.css`: the standard recipes for buttons (xs 32 / sm 36 / md 40 / lg 44), inputs, badges, cards and links. Exports don't load it (their components are built in); the style guide and the React handoff components do.
- `index.html`: the living style guide (the site's home page), rendered live from the two files above.
- `prototypes.json`: which prototype pages use this system (repos in `~/Documents/GitHub`, with file patterns). Both tools read it. Add new prototype repos here.
- `drift-allowlist.json`: non-token colors that are allowed (partner brands, third-party buttons). Each entry has a note.
- `tools/link_tokens.py` and `tools/drift_check.py`: see below.

## Accessibility standard
Everything must meet the **most recent WCAG version at level AA**. Today that's **WCAG 2.2 AA**. When a newer WCAG version is published, adopt it, check the design system and prototypes against it, and update this note, the style guide badge, and the drift check.

It applies to tokens, components, the style guide, every prototype, and every review or suggestion you make. Criteria that come up most often:
- **Contrast (1.4.3, 1.4.11):** 4.5:1 for body text; 3:1 for large text (18px+, or 14px+ bold), icons, input borders, and focus indicators.
- **Focus (2.4.7, 2.4.11):** a visible focus ring on every interactive element (`--ring-focus`, 2px solid), never hidden behind sticky headers or overlays.
- **Target size (2.5.8):** interactive targets at least 24 × 24px. The smallest button is xs at 32px.
- **Not color alone (1.4.1):** status badges pair color with a text label.
- **Reflow (1.4.10):** layouts work at 320px wide without horizontal scrolling.

When something in the system or a prototype doesn't meet the standard, flag it to the owner in plain language with the criterion number, even when it wasn't asked about.

## How the shared tokens work
Each Claude Design export carries its own copy of the tokens. `tools/link_tokens.py` adds one `<link data-cc-shared-tokens>` to the shared `tokens.css`, right after that copy, so the shared file wins and the built-in copy is only a fallback. Changing a token here and pushing this repo updates every linked page on every site. Components are built into each export, so component changes need a re-export from Claude Design.

Some exports (CC-Prototype so far) also link `components.css` themselves, with `<link data-cc-shared-components>` added in Claude Design. `link_tokens.py` keeps those pointed at this site too. The design system's address used to be `https://pricetn3.github.io/The-Store/design-system/` (until 2026-10-28). The drift check flags any page still using it, and the Claude Design project needs updating if new exports bring it back.

Linked prototype repos (see `prototypes.json`):
- `The Store/The-Store`: all `*.dc.html` exports and `index.html`; `emails/` is drift-checked only (email can't load CSS tokens). Its `handoff/` React components load `tokens.css` and `components.css` from this site.
- `CC-Prototype`: `external.html`, `internal.html` (`index.html` is a plain menu page).

`Implementation Tool` is intentionally **not** on this system: it's built in the existing Client Implementation tool's style (Blazor, Telerik, Bootstrap 5.1) to match the live product.

The focus ring standard is the 2px solid `--ring-focus` (the owner chose it over the older 4px soft halo for accessibility).

## After every new export, before publishing
1. Link it to the shared tokens (covers every page in `prototypes.json`, skips pages already linked):
   ```
   python3 tools/link_tokens.py
   ```
2. Run the drift check and summarize the results for the owner in plain language:
   ```
   python3 tools/drift_check.py
   ```
   Errors mean something differs from the system (including an unlinked export or one below the 24px target size); warnings mean it works but should use a token or a standard size.

A new prototype repo gets added to `prototypes.json` first.

## Publishing
This terminal has no GitHub sign-in (company-managed Mac, no admin rights, so GitHub CLI can't be installed). Commit on a branch, merge it into `main`, then ask the owner to click **Push origin** in GitHub Desktop for each repo that changed. GitHub Pages goes live about 30 seconds later. When a change touches several repos, push this one first, so linked pages never point at a file that isn't live yet.

## Previewing
The style guide fetches `tokens.css`, so serve it over HTTP rather than opening the file. Use the `site` launch configuration (`python3 -m http.server 8000`).
