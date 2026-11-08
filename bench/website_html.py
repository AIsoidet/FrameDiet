"""Token table for `fdiet html` on saved marketing pages.

Usage: python bench/website_html.py <dir-with-html-files>
Downloaded third-party HTML is NOT stored in the repo; fetch it yourself, e.g.
  curl -sL -A "Mozilla/5.0 ..." https://linear.app -o web/linear.app.html
cl100k_base is a proxy, not Claude's tokenizer.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from framediet.toon import slim_html_dom  # noqa: E402

ENC = tiktoken.get_encoding("cl100k_base")


def tok(text: str) -> int:
    return len(ENC.encode(text, disallowed_special=()))


def text_only(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print("| page | raw | default | --strip-classes | + --strip-styles | visible text only |")
    print("|---|---:|---:|---:|---:|---:|")
    for path in sorted(Path(sys.argv[1]).glob("*.html")):
        raw = path.read_text(encoding="utf-8", errors="replace")
        default = slim_html_dom(raw)
        classes = slim_html_dom(raw, strip_classes=True)
        both = slim_html_dom(raw, strip_classes=True, strip_styles=True)
        assert text_only(default) == text_only(both), "visible text changed"
        print(f"| {path.stem} | {tok(raw):,} | {tok(default):,} | {tok(classes):,} | {tok(both):,} | {tok(text_only(default)):,} |")


if __name__ == "__main__":
    main()
