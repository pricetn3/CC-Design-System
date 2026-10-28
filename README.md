# CC Design System

The Credential Connections design system in code: tokens, component recipes, and a living style guide.

**Style guide:** https://pricetn3.github.io/CC-Design-System/

The master design system lives in Claude Design. This repo mirrors it, and every Credential Connections prototype loads its tokens from here, so a token change pushed here updates them all.

## Use it

Load both stylesheets once, globally, plus Inter (400–700):

```html
<link rel="stylesheet" href="https://pricetn3.github.io/CC-Design-System/tokens.css">
<link rel="stylesheet" href="https://pricetn3.github.io/CC-Design-System/components.css">
```

Then style with tokens (`var(--blue-600)`, `var(--space-4)`, `var(--radius-md)`) and the shared component classes (`cc-btn cc-btn--primary`, `cc-input`, `cc-badge cc-badge--success`, `cc-card`, `cc-link`). The style guide shows every token and component.

## Files

| File | What it is |
|---|---|
| `tokens.css` | Colors, type, spacing, radius, shadows |
| `components.css` | Buttons (xs 32 / sm 36 / md 40 / lg 44), inputs, badges, cards, links |
| `index.html` | The living style guide |
| `prototypes.json` | Which prototype pages use this system |
| `drift-allowlist.json` | Non-token colors that are allowed (partner brands, third-party buttons) |
| `tools/link_tokens.py` | Links Claude Design exports to the shared `tokens.css` |
| `tools/drift_check.py` | Reports where prototypes drift from the system |

## Standard

Everything meets the latest WCAG at level AA, currently **WCAG 2.2 AA**.
