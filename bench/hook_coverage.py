from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from framediet.cli import is_safe_media_command


def main():
    rows = []
    source = Path(__file__).with_name("hook-coverage-commands.txt")
    with source.open(encoding="utf-8", newline="") as stream:
      for row in csv.reader(stream, delimiter="|", quotechar='"'):
        if not row or row[0].startswith("#"):
            continue
        repo, stars, file, number, kind, command, target, reason = row
        result = "n/a" if target == "non-target" else (
            "rewrite" if command and is_safe_media_command(command) else "pass-through"
        )
        rows.append((repo, stars, file, number, kind, command, target, result, reason))
    print("| Skill (stars) | Source | Kind | Command | Scope | Hook | Reason |")
    print("|---|---|---|---|---|---|---|")
    for repo, stars, file, number, kind, command, target, result, reason in rows:
        escaped_command = command.replace("|", "\\|")
        escaped_reason = reason.replace("|", "\\|")
        print(f"| {repo} ({stars}) | {file}:{number} | {kind} | `{escaped_command}` | {target} | {result} | {escaped_reason} |")


if __name__ == "__main__":
    main()
