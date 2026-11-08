"""Remotion log: default output vs `--log=error` vs `fdiet exec` (current logs.py).

Usage: python bench/three_columns.py
Fixtures in bench/fixtures/ are raw stdout+stderr captured from real runs. Token counts
use cl100k_base (a proxy, not Claude's tokenizer).
"""
from __future__ import annotations

import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from framediet.logs import compress_output  # noqa: E402

ENC = tiktoken.get_encoding("cl100k_base")
FIX = ROOT / "bench" / "fixtures"


def tok(text: str) -> int:
    return len(ENC.encode(text))


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8", errors="replace")


def main() -> None:
    rows = [
        ("remotion render, 90 frames", "remotion-render-90f.raw.log", ["npx", "remotion", "render"],
         "remotion-render-90f.log-error.log"),
        ("remotion bundle", "remotion-bundle.raw.log", ["npx", "remotion", "bundle"], None),
    ]
    print("| Run | Default output | `--log=error` | `fdiet exec` |")
    print("|---|---:|---:|---:|")
    for label, raw_name, cmd, err_name in rows:
        raw = read(raw_name)
        compact = compress_output(cmd, 0, raw, "")
        err = f"{tok(read(err_name))}" if err_name else "n/a"
        print(f"| {label} | {tok(raw)} | {err} | {tok(compact)} |")
    print("\nWhat the compact render summary keeps:\n")
    print(compress_output(rows[0][2], 0, read(rows[0][1]), ""))


if __name__ == "__main__":
    main()
