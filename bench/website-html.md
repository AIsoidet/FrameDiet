# `fdiet html` on real marketing pages

Date fetched: 2026-11-08 (curl, desktop Chrome user agent, `Accept-Language: en-US`, server-rendered HTML only, no JS executed).
Reproduce: `python bench/website_html.py <dir with linear.app.html, vercel.com.html, stripe.com.html>`.
Downloaded HTML is not committed. Tokens are cl100k_base, a proxy and not Claude's tokenizer.

## What the "website to video" skill actually does

Checked: `heygen-com/hyperframes` (https://github.com/heygen-com/hyperframes, commit b764a5f, read via `gh api`).
There is no `/website-to-hyperframes` skill in that tree any more. The workflow is `skills/hyperframes/references/film.md`
section "From a website": run `npx hyperframes capture <url> --json` (code in `packages/cli/src/capture/`).
That is a headless-browser capture (Puppeteer), and the model is **not** fed raw HTML. The generated `AGENTS.md`/`CLAUDE.md`
(`agentPromptGenerator.ts`) points the agent at:

- `screenshots/contact-sheet.jpg`, `screenshots/full-page.png`, `scroll-*.png` (view first; the skill says to reuse screenshots rather than rebuild the page in HTML),
- `extracted/tokens.json`, `extracted/design-styles.json` (computed styles from the live DOM),
- `extracted/visible-text.txt` (page text in DOM order, prefixed `[h1]`, `[p]`, `[a]`),
- `extracted/asset-descriptions.md` (vision captions of downloaded assets).

A full `extracted/page.html` (stylesheets inlined, fonts kept) is written to disk, but it is not the primary input and the prompt does not list it.
The other video skills listed in awesome-claude-video-skills (URL to video) were not audited one by one; I only read the HyperFrames one.

**Consequence for the claim:** `fdiet html` does not shrink anything this skill sends to the model, because the skill already
replaces raw HTML with screenshots plus extracted text/tokens. It only helps when an agent is told to read a saved page itself
(`Read page.html`, `curl` output, or the inlined `extracted/page.html`). Do not market it as "cuts website-to-video cost".

## Numbers

| page | raw | default | `--strip-classes` | `+ --strip-styles` | visible text only |
|---|---:|---:|---:|---:|---:|
| linear.app | 573,506 | 128,332 | 122,878 | 117,818 | 2,516 |
| stripe.com | 292,330 | 78,658 | 77,493 | 75,865 | 3,075 |
| vercel.com | 209,461 | 56,031 | 30,238 | 29,734 | 1,896 |

Default already removes 73-78% (scripts, styles, base64, long SVG paths). `--strip-classes` adds 4% (Linear), 1% (Stripe), 46% (Vercel, Tailwind-style
class lists). Even after both flags the page is 12-47x larger than its visible text.

## What still dominates (after both flags)

Inline SVG icon markup (`svg`, `path`, `circle`, `rect`, `symbol` tags: about 40% of Linear's remaining characters, 30% of Stripe's), `<link>` tags,
`srcset` (about 13% of Stripe's characters), `href`/`src` URLs, and short class lists below the threshold. A `--strip-svg` flag would be the next candidate;
not added (needs care: SVG `<title>`/`<text>` is visible text).

## New opt-in flags (default output unchanged)

- `--strip-classes`: `class` values of at least 60 chars become `class="[CLASSES_OMITTED:<n classes>]"`.
- `--strip-styles`: same for inline `style`, marker `[STYLE_OMITTED]`.
- `--attr-min N`: change the 60-char threshold.

## What is lost / limits

- Class names and inline styles (so no layout or brand-colour reading from them; use screenshots or computed styles for that). Visible text, tags, ids, hrefs and `data-*` are kept; the bench asserts the stripped-tag text equals the default's.
- Only the first HTML response was measured. These are client-rendered sites in part: the curl HTML lacks what JS adds later, so a browser-captured DOM would differ.
- Three pages, one day; sizes change with deploys and A/B tests. Regex-based, not an HTML parser: a `>` inside an unquoted attribute or malformed markup may be skipped (left uncollapsed, never corrupted).
