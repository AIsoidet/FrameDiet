"""HyperFrames render log: default vs `--quiet` vs `fdiet exec` (current logs.py).

Usage: python bench/hyperframes_columns.py
Fixtures in bench/fixtures/ are raw stdout+stderr of `npx hyperframes render` (v0.9.23)
on the blank example. Token counts use cl100k_base (a proxy, not Claude's tokenizer).
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
CMD = ["npx", "hyperframes", "render"]


def tok(text: str) -> int:
    return len(ENC.encode(text))


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8", errors="replace")


def main() -> None:
    raw = read("hyperframes-render.raw.log")
    quiet = read("hyperframes-render.quiet.log")
    print("| Run | Default output | `--quiet` | `fdiet exec` (default) | `fdiet exec` (+ `--quiet`) |")
    print("|---|---:|---:|---:|---:|")
    print(f"| `hyperframes render`, 10 s blank | {tok(raw)} | {tok(quiet)} | "
          f"{tok(compress_output(CMD, 0, raw, ''))} | {tok(compress_output(CMD, 0, quiet, ''))} |")
    print(f"\nLines: raw {len(raw.splitlines())}, quiet {len(quiet.splitlines())}")
    print("\nWhat `fdiet exec` keeps on the default log:\n")
    print(compress_output(CMD, 0, raw, ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
