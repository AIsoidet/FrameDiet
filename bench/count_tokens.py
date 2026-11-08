"""Count skill-file tokens with cl100k_base, which is NOT Claude's tokenizer.

Usage: python bench/count_tokens.py <skill_dir> [<skill_dir> ...]
Prints SKILL.md, each references/*.md, and three load scenarios.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import tiktoken
except ImportError as exc:
    raise SystemExit(
        "tiktoken is not installed. Install the optional benchmark extra with "
        '`python -m pip install -e ".[benchmark]"` and retry.'
    ) from exc

ENC = tiktoken.get_encoding("cl100k_base")


def toks(path: Path) -> int:
    return len(ENC.encode(path.read_text(encoding="utf-8", errors="replace")))


def report(skill: Path) -> None:
    print(f"\n## {skill.name}")
    main = skill / "SKILL.md"
    base = toks(main) if main.exists() else 0
    print(f"SKILL.md: {base}")
    readme = skill / "README.md"
    if readme.is_file():
        print(f"README.md: {toks(readme)}")
    refs = sorted((skill / "references").glob("*.md")) if (skill / "references").exists() else []
    sizes = {r.name: toks(r) for r in refs}
    for name, n in sorted(sizes.items(), key=lambda kv: -kv[1]):
        print(f"  references/{name}: {n}")
    if refs:
        print(f"references total: {sum(sizes.values())}")
        print(
            "sum of per-file cl100k_base counts: "
            f"SKILL only = {base}; SKILL + all refs = {base + sum(sizes.values())}"
        )


if __name__ == "__main__":
    for arg in sys.argv[1:] or [str(Path.home() / ".claude" / "skills" / "anatomy")]:
        report(Path(arg))
