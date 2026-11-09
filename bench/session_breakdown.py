"""Break a Claude Code session transcript down by what filled the context.

Usage: python bench/session_breakdown.py <session.jsonl> [--json]

For every block that entered the main conversation it estimates tokens
(cl100k_base for text, the documented w*h/750 rule for images), then
reports per category:

  new      tokens that entered the context once
  carried  token-calls: tokens x number of later API calls that re-read them
           (until the next compaction)
  units    cost in "input-token equivalents": cache write x2 (1h TTL),
           cache read x0.1, output x5. Ratios, not dollars.

Ground truth from the API usage fields is printed next to the estimates so
the proxy error is visible. Only aggregate numbers are printed; no
transcript text leaves the file.
"""
from __future__ import annotations

import base64
import json
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def ntok(text: str) -> int:
        return len(_ENC.encode(text, disallowed_special=()))
except Exception:  # pragma: no cover - fallback without tiktoken
    def ntok(text: str) -> int:
        return len(text.encode("utf-8")) // 4

W_WRITE, W_WRITE_5M, W_READ, W_OUT = 2.0, 1.25, 0.1, 5.0
INLINE = re.compile(r"<<-?\s*['\"]?\w+|\bpython3?\s+-c\b|\bnode\s+(-e|--eval)\b|\bpwsh\b.*-Command")
RENDER = re.compile(r"\b(remotion\s+(render|still)|hyperframes\s+(render|snapshot)|ffmpeg|manim|playwright|puppeteer|screenshot)\b")
LISTING = {"skill_listing", "deferred_tools_delta", "agent_listing_delta", "mcp_instructions_delta",
           "instructions", "session_context"}
LOG_ONLY = {"prompt_snapshot", "deferred_tools_record", "credential_org", "command_permissions"}  # never sent as context


def _strings(o) -> str:
    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        return "\n".join(_strings(v) for k, v in o.items() if k not in ("type", "names", "digests", "addedNames"))
    if isinstance(o, list):
        return "\n".join(_strings(v) for v in o)
    return ""

CODE_EXT = {".tsx", ".ts", ".jsx", ".js", ".mjs", ".html", ".css", ".svg", ".py", ".json", ".sh", ".glsl"}
MEDIA_CMD = re.compile(r"\b(remotion|hyperframes|ffmpeg|ffprobe|manim|yt-dlp|framediet|fdiet|whisper)\b")
BUILD_CMD = re.compile(r"\b(tsc|npm|npx|pnpm|bun|node|vite|eslint|playwright|puppeteer)\b")
DOC_PATH = re.compile(r"(skills?[\\/]|references?[\\/]|SKILL\.md|CLAUDE\.md|AGENTS\.md|docs[\\/])", re.I)


def image_size(b64: str) -> tuple[int, int] | None:
    try:
        raw = base64.b64decode(b64[:120000] + "=" * (-len(b64[:120000]) % 4))
    except Exception:
        return None
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", raw[16:24])
    if raw[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", raw[i + 2:i + 4])[0]
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" and raw[12:16] == b"VP8X":
        w = int.from_bytes(raw[24:27], "little") + 1
        h = int.from_bytes(raw[27:30], "little") + 1
        return w, h
    return None


def image_tokens(b64: str) -> int:
    size = image_size(b64)
    if not size:
        return 1500
    w, h = size
    scale = min(1.0, 1568 / max(w, h), (1_150_000 / (w * h)) ** 0.5)
    return max(1, round(w * scale * h * scale / 750))


def classify_read(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".md" or DOC_PATH.search(path):
        return "docs: skill, reference and project .md read"
    if ext in CODE_EXT:
        return "source: own code read back"
    return "read: other files"


def classify_result(tool: str, inp: dict) -> str:
    if tool == "Read":
        return classify_read(str(inp.get("file_path", "")))
    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        if MEDIA_CMD.search(cmd):
            return "bash: render and media tool output"
        if BUILD_CMD.search(cmd):
            return "bash: build, typecheck, node output"
        return "bash: other output"
    if tool in ("Grep", "Glob"):
        return "search results"
    if tool in ("Edit", "Write", "NotebookEdit"):
        return "edit confirmations"
    if tool in ("Agent", "Task"):
        return "subagent reports"
    if tool == "Skill":
        return "docs: skill, reference and project .md read"
    if tool.startswith("mcp__") or tool.startswith("Web"):
        return "web, browser and MCP results"
    return "other tool results"


def classify_image(tool: str, inp: dict) -> str:
    if tool == "Read":
        return "images: frames and stills read from disk"
    if "rowser" in tool or "chrome" in tool or "computer" in tool:
        return "images: browser screenshots"
    return "images: other"


def classify_call(tool: str, inp: dict) -> tuple[str, str]:
    """Return (category, text that the model had to write)."""
    if tool in ("Write", "Edit", "NotebookEdit"):
        body = "".join(str(inp.get(k, "")) for k in ("content", "old_string", "new_string", "new_source"))
        ext = Path(str(inp.get("file_path", ""))).suffix.lower()
        kind = "code written (Write/Edit)" if ext in CODE_EXT else "text files written (Write/Edit)"
        return "output: " + kind, body
    if tool in ("Bash", "PowerShell"):
        return "output: shell commands and inline scripts", str(inp.get("command", ""))
    return "output: other tool calls", json.dumps(inp, ensure_ascii=False)


def analyse(path: Path) -> dict:
    calls: list[dict] = []          # one per API message id, in order
    seen_ids: dict[str, int] = {}
    blocks: list[tuple[int, str, int, bool]] = []   # (call_index_when_added, category, tokens, is_output)
    tools: dict[str, tuple[str, dict]] = {}
    compactions: list[int] = []
    side_lines = 0
    models: defaultdict[str, int] = defaultdict(int)

    def add(cat: str, tokens: int, out: bool = False) -> None:
        if tokens:
            blocks.append((len(calls), cat, tokens, out))

    det = {"sh_inline": [0, 0], "sh_short": [0, 0], "write": [0, 0], "edit": [0, 0],
           "rewrites": [0, 0], "reread": [0, 0], "img": [], "renders": 0}
    written: set[str] = set()
    read_paths: set[str] = set()

    def add_image(cat: str, b64: str) -> None:
        tok = image_tokens(b64)
        det["img"].append((image_size(b64) or (0, 0), tok))
        add(cat, tok)

    def attachment(a: dict) -> None:
        t = a.get("type")
        if t == "queued_command":
            human = (a.get("origin") or {}).get("kind") in ("human", "peer")
            cat = "user messages" if human else "harness: background task notifications"
            pr = a.get("prompt")
            if isinstance(pr, str):
                add(cat, ntok(pr))
            for b in pr if isinstance(pr, list) else []:
                if b.get("type") == "text":
                    add(cat, ntok(b.get("text", "")))
                elif b.get("type") == "image":
                    add_image("images: pasted by the user", (b.get("source") or {}).get("data", ""))
        elif t == "file":
            body = ((a.get("content") or {}).get("file") or {})
            if isinstance(body.get("content"), str):
                add(classify_read(str(a.get("filename", ""))), ntok(body["content"]))
            elif body.get("base64"):
                add_image("images: frames and stills read from disk", body["base64"])
        elif t == "invoked_skills":
            add("docs: skill bodies re-sent after compaction", ntok(_strings(a.get("skills"))))
        elif t in LOG_ONLY:
            return
        elif t in LISTING:
            if calls:   # the first copy is already inside the baseline
                add("harness: listings re-sent mid-session (tools, skills, MCP, CLAUDE.md)", ntok(_strings(a)))
        else:
            add("harness: reminders and state notes", ntok(_strings(a)))

    ctxs: list[int] = []

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = d.get("type")
            if kind == "attachment" and not d.get("isSidechain"):
                attachment(d.get("attachment") or {})
                continue
            if kind not in ("user", "assistant"):
                continue
            if d.get("isSidechain"):
                side_lines += 1
                continue
            msg = d.get("message") or {}
            content = msg.get("content")
            if kind == "assistant":
                mid = msg.get("id") or d.get("uuid")
                usage = msg.get("usage") or {}
                if mid not in seen_ids:
                    seen_ids[mid] = len(calls)
                    calls.append({})
                    models[msg.get("model", "?")] += 1
                calls[seen_ids[mid]] = usage
                for b in content or []:
                    bt = b.get("type")
                    if bt == "text":
                        blocks.append((seen_ids[mid], "output: replies to the user", ntok(b.get("text", "")), True))
                    elif bt == "tool_use":
                        tools[b.get("id")] = (b.get("name", ""), b.get("input") or {})
                        name, inp = b.get("name", ""), b.get("input") or {}
                        cat, body = classify_call(name, inp)
                        tok = ntok(body) + 20
                        blocks.append((seen_ids[mid], cat, tok, True))
                        if name in ("Bash", "PowerShell"):
                            k = "sh_inline" if INLINE.search(body) or len(body) > 600 else "sh_short"
                            det[k][0] += 1
                            det[k][1] += tok
                            det["renders"] += bool(RENDER.search(body))
                        elif name in ("Write", "Edit"):
                            fp = str(inp.get("file_path", ""))
                            k = name.lower()
                            det[k][0] += 1
                            det[k][1] += tok
                            if name == "Write":
                                if fp in written:
                                    det["rewrites"][0] += 1
                                    det["rewrites"][1] += tok
                                written.add(fp)
                continue
            # user side
            if d.get("isCompactSummary"):
                compactions.append(len(calls))
                text = content if isinstance(content, str) else " ".join(
                    b.get("text", "") for b in content or [] if b.get("type") == "text")
                add("compaction summaries", ntok(text))
                continue
            if isinstance(content, str):
                add("harness: injected context (skill bodies, reminders)" if d.get("isMeta") else "user messages", ntok(content))
                continue
            for b in content or []:
                bt = b.get("type")
                if bt == "text":
                    add("harness: injected context (skill bodies, reminders)" if d.get("isMeta") else "user messages",
                        ntok(b.get("text", "")))
                elif bt == "image":
                    add_image("images: pasted by the user", (b.get("source") or {}).get("data", ""))
                elif bt == "tool_result":
                    tool, inp = tools.get(b.get("tool_use_id"), ("?", {}))
                    inner = b.get("content")
                    if tool == "Read":
                        fp = str(inp.get("file_path", ""))
                        if fp in read_paths:
                            det["reread"][0] += 1
                            det["reread"][1] += ntok(inner if isinstance(inner, str) else _strings(
                                [x.get("text", "") for x in inner or []]))
                        read_paths.add(fp)
                    if isinstance(inner, str):
                        add(classify_result(tool, inp), ntok(inner))
                        continue
                    for x in inner or []:
                        if x.get("type") == "text":
                            add(classify_result(tool, inp), ntok(x.get("text", "")))
                        elif x.get("type") == "image":
                            add_image(classify_image(tool, inp), (x.get("source") or {}).get("data", ""))

    n = len(calls)
    bounds = sorted(set(compactions)) + [n]

    def calls_after(i: int) -> int:
        end = next(b for b in bounds if b >= i) if any(b >= i for b in bounds) else n
        return max(0, end - i)

    # Calibrate the proxies against real context growth between consecutive calls.
    ctx_of = [sum(u.get(k, 0) or 0 for k in ("cache_creation_input_tokens", "cache_read_input_tokens", "input_tokens"))
              for u in calls]
    feat = [[0.0, 0.0] for _ in range(n + 1)]
    for idx, cat, tok, out in blocks:
        step = idx + 1 if out else idx
        if step <= n:
            feat[step][1 if cat.startswith("images") else 0] += tok
    rows, ys = [], []
    for k in range(1, n):
        delta = ctx_of[k] - ctx_of[k - 1]
        if delta > 0 and k not in compactions and (feat[k][0] or feat[k][1]):
            rows.append(feat[k])
            ys.append(delta)
    k_text = k_img = 1.0
    try:
        import numpy as np
        if len(rows) > 10:
            a = np.array(rows)
            if a[:, 1].sum() > 0:
                sol = np.linalg.lstsq(a, np.array(ys, float), rcond=None)[0]
                k_text, k_img = float(sol[0]), float(sol[1])
            else:
                k_text = float(np.array(ys).sum() / a[:, 0].sum())
            if not (0.5 < k_text < 4):
                k_text = 1.0
            if not (0.3 < k_img < 6):
                k_img = 1.0
    except ImportError:
        pass
    blocks = [(i, c, round(t * (k_img if c.startswith("images") else k_text)), o) for i, c, t, o in blocks]

    cats: dict[str, dict] = defaultdict(lambda: {"count": 0, "new": 0, "carried": 0, "units": 0.0})
    if calls:
        base = ctx_of[0]
        segs = len(compactions) + 1
        cats["baseline: system prompt, tool and skill listings, memory, CLAUDE.md"] = {
            "count": 1, "new": base, "carried": base * n, "units": base * W_WRITE * segs + base * n * W_READ}
    for idx, cat, tok, out in blocks:
        c = cats[cat]
        carried = tok * calls_after(idx + (1 if out else 0))
        c["count"] += 1
        c["new"] += tok
        c["carried"] += carried
        c["units"] += tok * W_WRITE + carried * W_READ + (tok * W_OUT if out else 0)

    tot = defaultdict(int)
    rebuild = 0
    prev_ctx = 0
    for u in calls:
        tot["write_5m"] += (u.get("cache_creation") or {}).get("ephemeral_5m_input_tokens", 0) or 0
        cr, rd = u.get("cache_creation_input_tokens", 0) or 0, u.get("cache_read_input_tokens", 0) or 0
        inp, out = u.get("input_tokens", 0) or 0, u.get("output_tokens", 0) or 0
        think = (u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0
        ctx = cr + rd + inp
        tot["cache_creation"] += cr
        tot["cache_read"] += rd
        tot["input"] += inp
        tot["output"] += out
        tot["thinking"] += think
        tot["max_context"] = max(tot["max_context"], ctx)
        if prev_ctx and rd < 0.5 * prev_ctx and ctx > 0.5 * prev_ctx:
            rebuild += max(0, min(cr, prev_ctx) - 0)
        prev_ctx = ctx
    first_ctx = 0
    if calls:
        u = calls[0]
        first_ctx = sum(u.get(k, 0) or 0 for k in ("cache_creation_input_tokens", "cache_read_input_tokens", "input_tokens"))
    truth_units = (tot["cache_creation"] * W_WRITE - tot["write_5m"] * (W_WRITE - W_WRITE_5M)
                   + tot["cache_read"] * W_READ + tot["input"] + tot["output"] * W_OUT)
    if tot["thinking"]:
        cats["output: thinking (billed as output, not kept in context)"] = {
            "count": sum(1 for u in calls if (u.get("output_tokens_details") or {}).get("thinking_tokens")),
            "new": tot["thinking"], "carried": 0, "units": tot["thinking"] * W_OUT}
    if rebuild:
        cats["cache rebuilt after an idle gap (whole context written again)"] = {
            "count": 0, "new": rebuild, "carried": 0, "units": rebuild * W_WRITE}
    imgs = sorted(t for _, t in det["img"])
    det_out = {
        "shell_inline_scripts": det["sh_inline"], "shell_short_commands": det["sh_short"],
        "write_calls": det["write"], "edit_calls": det["edit"], "write_over_existing": det["rewrites"],
        "repeat_reads": det["reread"], "render_or_capture_commands": det["renders"],
        "images": len(imgs), "image_tokens_median": imgs[len(imgs) // 2] if imgs else 0,
        "image_tokens_max": imgs[-1] if imgs else 0,
        "images_over_1000_tokens": sum(1 for t in imgs if t > 1000),
        "image_long_side_median": sorted(max(sz) for sz, _ in det["img"])[len(imgs) // 2] if imgs else 0,
        "context_median": sorted(ctx_of)[n // 2] if n else 0,
    }
    return {
        "file": path.name,
        "api_calls": n,
        "compactions": len(compactions),
        "sidechain_lines_skipped": side_lines,
        "models": dict(models),
        "usage": dict(tot),
        "first_call_context": first_ctx,
        "cache_rebuild_tokens": rebuild,
        "truth_units": truth_units,
        "detail": det_out,
        "calibration": {"text": round(k_text, 2), "image": round(k_img, 2), "steps": len(rows)},
        "categories": {k: v for k, v in sorted(cats.items(), key=lambda kv: -kv[1]["units"])},
    }


def render(r: dict) -> str:
    u = r["usage"]
    est_new = sum(c["new"] for c in r["categories"].values())
    est_units = sum(c["units"] for c in r["categories"].values())
    out = [
        f"# {r['file']}",
        f"API calls {r['api_calls']}, compactions {r['compactions']}, models {r['models']}",
        f"usage (API truth): cache write {u.get('cache_creation', 0):,} | cache read {u.get('cache_read', 0):,} | "
        f"output {u.get('output', 0):,} (thinking {u.get('thinking', 0):,}) | uncached input {u.get('input', 0):,}",
        f"first-call context (system prompt, tools, memory, CLAUDE.md) {r['first_call_context']:,}; "
        f"largest context {u.get('max_context', 0):,}",
        f"cache rebuilt after expiry or compaction: about {r['cache_rebuild_tokens']:,} tokens "
        f"({100 * r['cache_rebuild_tokens'] / max(1, u.get('cache_creation', 0)):.0f}% of all cache writes)",
        f"truth cost units {r['truth_units']:,.0f}; of them write {100 * u.get('cache_creation', 0) * W_WRITE / r['truth_units']:.0f}% "
        f"read {100 * u.get('cache_read', 0) * W_READ / r['truth_units']:.0f}% output {100 * u.get('output', 0) * W_OUT / r['truth_units']:.0f}%",
        f"calibration vs real context growth: text x{r['calibration']['text']}, images x{r['calibration']['image']} "
        f"({r['calibration']['steps']} steps)",
        f"attributed units {est_units:,.0f} = {100 * est_units / r['truth_units']:.0f}% of truth",
        "",
        "| Category | Blocks | New tokens | Lives for (calls) | Units | Share of truth |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, c in sorted(r["categories"].items(), key=lambda kv: -kv[1]["units"]):
        out.append(f"| {name} | {c['count']:,} | {c['new']:,} | {c['carried'] / max(1, c['new']):.0f} | "
                   f"{c['units']:,.0f} | {100 * c['units'] / r['truth_units']:.1f}% |")
    d = r["detail"]
    out += [
        "",
        f"median context per call {d['context_median']:,}",
        f"shell: {d['shell_inline_scripts'][0]:,} inline scripts = {d['shell_inline_scripts'][1]:,} output tokens; "
        f"{d['shell_short_commands'][0]:,} short commands = {d['shell_short_commands'][1]:,}",
        f"files: Write {d['write_calls'][0]:,} calls = {d['write_calls'][1]:,} tokens "
        f"(over a file already written this session: {d['write_over_existing'][0]:,} = {d['write_over_existing'][1]:,}); "
        f"Edit {d['edit_calls'][0]:,} calls = {d['edit_calls'][1]:,}",
        f"repeat Read of a path already read: {d['repeat_reads'][0]:,} = {d['repeat_reads'][1]:,} tokens",
        f"images: {d['images']:,} for {d['render_or_capture_commands']:,} render/capture commands; "
        f"median {d['image_tokens_median']:,} tokens (long side {d['image_long_side_median']:,} px), "
        f"max {d['image_tokens_max']:,}, over 1,000 tokens: {d['images_over_1000_tokens']:,}",
    ]
    return "\n".join(out)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    for a in args:
        r = analyse(Path(a))
        print(json.dumps(r, ensure_ascii=False, indent=1) if "--json" in sys.argv else render(r))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
