# Where the tokens go in real video-creation sessions

Date: 2026-11-09. Script: `bench/session_breakdown.py`.

Every other file in `bench/` measures a synthetic task, and all of them are
about checking a finished video. This one measures four real Claude Code
sessions in which videos were actually built, to see what the cost is made of
during generation.

## Result

Re-reading the accumulated context is 55–72% of the cost. Images are 8–10%,
render logs 1–4%.

This differs from the short synthetic runs (`e2e-session.md`, `e2e-tasks.md`),
where first-time cache writes were the largest part. In a long session each
token is re-read 50–150 more times, so what a block costs depends on how many
calls it stays in context, not only on its size.

## Sessions

| | A: Remotion lab | B: Remotion project | C: Remotion reel | D: anatomy figure |
|---|---:|---:|---:|---:|
| API calls | 879 | 397 | 187 | 45 |
| Model | Opus | Sonnet | Opus, some Sonnet | Opus |
| Compactions | 5 | 3 | 0 | 0 |
| Render or capture commands | 205 | 30 | 46 | 0 |
| Context at the first call | 71,499 | 70,737 | 79,126 | 77,870 |
| Median context per call | 295,506 | 167,246 | 248,713 | 195,022 |
| Largest context | 693,672 | 266,973 | 395,707 | 234,921 |
| Cost: cache read | 72% | 62% | 72% | 55% |
| Cost: cache write | 15% | 28% | 14% | 26% |
| Cost: output | 13% | 10% | 14% | 19% |
| Attributed to categories | 93% | 97% | 98% | 104% |

The sessions are private; only aggregate numbers are published.

## Share of cost by what filled the context

Each share includes the block's first write, every later re-read, and, for
model output, the output price.

| Category | A | B | C | D |
|---|---:|---:|---:|---:|
| Baseline: system prompt, tool, skill and MCP listings, memory | 18.6% | 31.2% | 26.2% | 35.8% |
| Model output: code, commands, replies, thinking | 49.6% | 21.7% | 35.6% | 30.9% |
| Text of command results | 7.2% | 9.9% | 18.2% | 4.4% |
| of which render and media tool output | 1.2% | 2.1% | 3.8% | 0% |
| Images: frames read from disk and pasted screenshots | 8.3% | 7.5% | 10.0% | 9.6% |
| Skill and documentation text | 1.4% | 6.1% | 0.9% | 17.5% |
| Cache rebuilt after an idle gap | 2.3% | 13.6% | 3.0% | 0% |

## What the numbers say

**The baseline is the most stable item.** 70–79 thousand tokens are in every
call before any work starts. This is the user's environment (installed skills,
MCP servers, tool listings), not the video repository. A lean profile for
video sessions removes more than any change inside FrameDiet.

**Session length multiplies everything.** Context reached 694 thousand tokens
in session A. Splitting work into one session per scene, or compacting early,
cuts every row of the table at once.

**Whole-file rewrites.** In session A, 120 `Write` calls went over a file
already written in the same session: 250,380 output tokens. All 136 `Edit`
calls together were 27,958.

**Inline scripts.** In session A, 401 shell calls carried an inline script:
242,373 output tokens, against 57,916 for 533 short commands. A ready command
instead of a hand-written script is the mechanism FrameDiet already uses in
`qa`; this is where it has room to grow.

**Frames.** A frame costs a median of 1,242–1,533 tokens at a long side of
1,440–1,652 px and stays in context for 60–90 calls. By the `w*h/750` rule a
768 px frame is about 440 tokens, roughly 70% less, on an item that is 8–10%
of the total. Not measured, only computed.

**Skill text matters for anatomy, not for Remotion.** In session D the skill
and its references were 32,507 tokens read in 45 calls, the second largest
item. In the Remotion sessions the same category is 1–6%.

**Render logs are small.** 1.2–3.8% including ffmpeg and ffprobe output. This
agrees with the earlier finding that the log hook saves cents.

## Method

For every block that entered the main conversation the script estimates
tokens (cl100k_base for text, `w*h/750` for images), then scales the
estimates by a least-squares fit against the real context growth between
consecutive API calls. A block's cost is its cache write, plus a cache read
for every later call until the next compaction, plus the output price if the
model wrote it. Subagent traffic is skipped.

Cost units are list-price ratios: 1-hour cache write ×2, 5-minute cache write
×1.25, cache read ×0.1, output ×5.

```
python bench/session_breakdown.py <session.jsonl> [--json]
```

## Limits

- The weights are price ratios. They were not checked against the dollar cost
  recorded in the transcripts.
- The text calibration factor is 1.38–1.51 in sessions B, C and D. Part of the
  context growth is invisible to the script and gets spread over the text
  categories, so their shares are estimates. In session A the factor is 0.87.
- Four sessions from one user and one machine. Session D is the only anatomy
  session and it is short.
- The 768 px frame saving is arithmetic, not a measured run.
